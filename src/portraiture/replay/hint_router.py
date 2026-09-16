from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _context_text(example: dict[str, Any], turns_by_id: dict[str, dict[str, Any]], messages_by_id: dict[str, dict[str, Any]]) -> str:
    texts: list[str] = []
    for turn_id in example.get("context_turn_ids", []):
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        user_message_id = turn.get("user_message_id")
        if not user_message_id:
            continue
        text = messages_by_id.get(user_message_id, {}).get("content_text", "").strip()
        if text:
            texts.append(text)
    return " \n ".join(texts)


def _word_features(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _char_ngrams(text: str, *, min_n: int = 2, max_n: int = 4) -> list[str]:
    compact = re.sub(r"\s+", "", text.lower())
    if not compact:
        return []
    features: list[str] = []
    for n in range(min_n, max_n + 1):
        if len(compact) < n:
            continue
        for idx in range(len(compact) - n + 1):
            features.append(compact[idx : idx + n])
    return features


def _extract_features(text: str) -> Counter[str]:
    normalized = _normalize_text(text)
    features = Counter(_word_features(normalized))
    features.update(_char_ngrams(normalized))
    return features


def _split_state_label(label: str) -> tuple[str | None, str | None]:
    if "||" not in label:
        return label or None, None
    state_type, state_value = label.split("||", 1)
    return state_type or None, state_value or None


@dataclass
class TextHintRouter:
    label_counts: dict[str, int]
    feature_counts: dict[str, Counter[str]]
    total_feature_counts: dict[str, int]
    vocabulary: set[str]
    alpha: float = 1.0
    min_probability: float = 0.0
    model_name: str = "text_hint_router_v1"

    @classmethod
    def fit(
        cls,
        samples: list[tuple[str, str]],
        *,
        alpha: float = 1.0,
        min_probability: float = 0.0,
        model_name: str = "text_hint_router_v1",
    ) -> "TextHintRouter":
        label_counts: dict[str, int] = defaultdict(int)
        feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        total_feature_counts: dict[str, int] = defaultdict(int)
        vocabulary: set[str] = set()

        for text, label in samples:
            if not label:
                continue
            features = _extract_features(text)
            label_counts[label] += 1
            for feature, count in features.items():
                feature_counts[label][feature] += count
                total_feature_counts[label] += count
                vocabulary.add(feature)

        return cls(
            label_counts=dict(label_counts),
            feature_counts={label: Counter(counts) for label, counts in feature_counts.items()},
            total_feature_counts=dict(total_feature_counts),
            vocabulary=vocabulary,
            alpha=alpha,
            min_probability=min_probability,
            model_name=model_name,
        )

    @classmethod
    def fit_state_router(
        cls,
        train_examples: list[dict[str, Any]],
        turns_by_id: dict[str, dict[str, Any]],
        messages_by_id: dict[str, dict[str, Any]],
        *,
        alpha: float = 1.0,
        min_probability: float = 0.0,
    ) -> "TextHintRouter":
        samples: list[tuple[str, str]] = []
        for example in train_examples:
            state_type = example.get("observed_state_type")
            state_value = example.get("observed_state_value")
            if not state_type:
                continue
            label = state_type if not state_value else f"{state_type}||{state_value}"
            samples.append((_context_text(example, turns_by_id, messages_by_id), label))
        return cls.fit(samples, alpha=alpha, min_probability=min_probability, model_name="state_hint_router_v1")

    def _score_label(self, label: str, features: Counter[str]) -> float:
        label_count = self.label_counts.get(label, 0)
        if label_count == 0:
            return float("-inf")

        vocab_size = max(len(self.vocabulary), 1)
        total = self.total_feature_counts.get(label, 0)
        denom = total + self.alpha * vocab_size
        log_prob = math.log(label_count / sum(self.label_counts.values()))

        for feature, count in features.items():
            feature_count = self.feature_counts.get(label, Counter()).get(feature, 0)
            log_prob += count * math.log((feature_count + self.alpha) / denom)
        return log_prob

    def predict(self, context_texts: list[str]) -> dict[str, Any]:
        if not self.label_counts:
            return {
                "state_type": None,
                "state_value": None,
                "confidence": 0.0,
                "reason": f"{self.model_name}: no labels were fit",
                "label": None,
                "candidates": [],
            }

        text = " \n ".join(text for text in context_texts if text).strip()
        if not text:
            return {
                "state_type": None,
                "state_value": None,
                "confidence": 0.0,
                "reason": f"{self.model_name}: empty context",
                "label": None,
                "candidates": [],
            }

        features = _extract_features(text)
        scored: list[tuple[str, float]] = []
        for label in self.label_counts:
            scored.append((label, self._score_label(label, features)))
        scored.sort(key=lambda item: (-item[1], item[0]))

        log_scores = [score for _, score in scored]
        max_score = max(log_scores)
        exp_scores = [math.exp(score - max_score) for score in log_scores]
        total = sum(exp_scores) or 1.0
        probs = [score / total for score in exp_scores]

        top_label, top_score = scored[0]
        top_prob = probs[0]
        candidates = []
        for (label, score), prob in zip(scored[:3], probs[:3]):
            state_type, state_value = _split_state_label(label)
            candidates.append(
                {
                    "label": label,
                    "state_type": state_type,
                    "state_value": state_value,
                    "score": score,
                    "probability": prob,
                }
            )

        state_type, state_value = _split_state_label(top_label)
        if top_prob < self.min_probability:
            return {
                "state_type": None,
                "state_value": None,
                "confidence": float(top_prob),
                "reason": f"{self.model_name}: top probability below threshold",
                "label": top_label,
                "candidates": candidates,
            }

        return {
            "state_type": state_type,
            "state_value": state_value,
            "confidence": float(top_prob),
            "reason": f"{self.model_name}: top={top_label} score={top_score:.3f}",
            "label": top_label,
            "candidates": candidates,
        }

