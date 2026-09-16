from __future__ import annotations

from typing import Any


ACTION_TO_COARSE_LABEL = {
    "ask_definition": "clarify",
    "ask_why": "clarify",
    "ask_for_example": "expand",
    "provide_more_context": "expand",
    "request_how_to": "plan",
    "feasibility_check": "plan",
    "compare_options": "compare",
    "challenge_or_refine": "challenge",
    "follow_up_clarification": "clarify",
    "topic_shift": "shift",
}

STATE_TO_ACTION_HINT = {
    "current_goal": "request_how_to",
    "active_problem": "request_how_to",
    "blocking_issue": "feasibility_check",
    "time_pressure": "follow_up_clarification",
    "current_stance": "challenge_or_refine",
    "uncertainty_level": "ask_definition",
}

TOPIC_SHIFT_EXPLICIT_MARKERS = [
    "换个话题",
    "新话题",
    "另一个问题",
    "另外一个问题",
    "转到",
    "切到",
    "改问",
    "重新",
    "换一个",
    "新问题",
]

TOPIC_SHIFT_CONTINUATION_MARKERS = [
    "接下来",
    "下一步",
    "继续",
    "然后",
    "细化",
    "列个",
    "大纲",
    "整理",
    "补充",
    "我同意",
    "可以",
    "好，",
    "好。",
    "那就",
]


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def simple_tokenize(text: str) -> set[str]:
    token = []
    tokens: set[str] = set()
    for ch in text.lower():
        if ch.isalnum():
            token.append(ch)
        else:
            if token:
                tokens.add("".join(token))
                token = []
    if token:
        tokens.add("".join(token))
    return tokens


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = simple_tokenize(left)
    right_tokens = simple_tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def should_label_topic_shift(
    current_text: str,
    previous_text: str | None,
    similarity_threshold: float,
) -> bool:
    previous = normalize_text(previous_text or "")
    current = normalize_text(current_text)
    if not previous:
        return False

    similarity = jaccard_similarity(previous, current)
    lower = current.lower()
    if any(marker in lower for marker in TOPIC_SHIFT_EXPLICIT_MARKERS) and similarity < max(similarity_threshold, 0.04):
        return True

    if similarity < max(similarity_threshold * 0.5, 0.03):
        if any(marker in lower for marker in TOPIC_SHIFT_CONTINUATION_MARKERS):
            return False
        if "?" in current or "？" in current:
            return False
        if len(current) < 80 and any(marker in lower for marker in ["图", "章", "节", "大纲", "标题", "题注", "参考图"]):
            return False
        return True

    return False


def coarse_label_for_action(label: str | None) -> str | None:
    if label is None:
        return None
    return ACTION_TO_COARSE_LABEL.get(label, "other")


def infer_action_label(current_text: str, previous_text: str | None, similarity_threshold: float) -> str:
    text = normalize_text(current_text)
    previous = normalize_text(previous_text or "")
    similarity = jaccard_similarity(previous, text) if previous else 0.0

    example_markers = ["举例", "例子", "比如", "示例", "case", "example"]
    definition_markers = ["是什么", "什么意思", "怎么算", "定义", "含义", "原理"]
    why_markers = ["为什么", "为啥", "原因", "怎么会"]
    how_markers = ["怎么", "如何", "怎样", "哪里可以", "哪里能", "步骤", "配置", "设置", "进入", "创建", "打开", "查看", "修改"]
    compare_markers = ["区别", "对比", "vs", "还是", "哪个好", "差异"]
    context_expansion_markers = ["补充一下", "另外", "还有", "顺便", "我发现", "再补充", "还有个现象", "补个背景", "额外"]
    challenge_markers = ["我说的是", "你这里", "不对", "并不是", "不是在问", "不是这个意思"]
    feasibility_markers = ["可以吗", "能不能", "是否", "行吗", "可不可以"]

    if any(marker in text for marker in example_markers):
        return "ask_for_example"
    if any(marker in text for marker in definition_markers):
        return "ask_definition"
    if any(marker in text for marker in why_markers):
        return "ask_why"
    if any(marker in text for marker in compare_markers):
        return "compare_options"
    if any(marker in text for marker in feasibility_markers):
        return "feasibility_check"
    if any(marker in text for marker in how_markers):
        return "request_how_to"
    if any(marker in text for marker in context_expansion_markers):
        return "provide_more_context"
    if any(marker in text for marker in challenge_markers):
        return "challenge_or_refine"
    if len(text) >= 120 and "?" not in text and "？" not in text:
        return "provide_more_context"
    if should_label_topic_shift(text, previous_text, similarity_threshold):
        return "topic_shift"
    return "follow_up_clarification"


def infer_state_hint_from_context(context_texts: list[str]) -> dict[str, Any]:
    recent_text = normalize_text(" ".join(context_texts[-3:]))
    if not recent_text:
        return {
            "state_type": None,
            "state_value": None,
            "confidence": 0.0,
            "reason": "empty_context",
        }

    text = recent_text.lower()
    previous_text = normalize_text(context_texts[-2]) if len(context_texts) >= 2 else ""
    transition_similarity = jaccard_similarity(previous_text, recent_text) if previous_text else 1.0

    time_pressure_markers = ["尽快", "马上", "立刻", "快速", "赶紧", "来不及", "deadline", "时间不多", "急"]
    blocking_markers = [
        "报错",
        "失败",
        "卡住",
        "无法",
        "不能",
        "出错",
        "问题",
        "阻塞",
        "错误",
        "error",
        "exception",
        "failed",
        "failure",
        "cannot",
        "can't",
        "unable",
        "not found",
        "connection",
        "timeout",
        "reset",
        "refused",
        "traceback",
        "cmdlet",
        "drive",
        "permission denied",
        "module not found",
        "buildkit",
        "docker",
        "curl",
        "proxy",
        "uvicorn",
    ]
    goal_markers = ["我想先", "先做", "先把", "目标", "计划", "方案", "框架", "步骤", "落地", "实现", "整理"]
    transition_markers = ["新想法", "另外", "顺便", "还有", "换个", "转到", "重新", "新的", "新问题", "帮我生成", "帮我看看", "我准备", "我想先"]
    stance_markers = ["我觉得", "我认为", "我倾向", "我偏向", "还是", "比较", "权衡", "选择"]
    uncertainty_markers = ["是否", "能不能", "可不可以", "行不行", "是不是", "不确定", "怎么判断"]

    if any(marker in text for marker in time_pressure_markers):
        return {
            "state_type": "time_pressure",
            "state_value": "need_fast_resolution",
            "confidence": 0.82,
            "reason": "time pressure markers detected in recent context",
        }
    if any(marker in text for marker in blocking_markers):
        return {
            "state_type": "blocking_issue",
            "state_value": "needs_troubleshooting",
            "confidence": 0.84,
            "reason": "blocking or error markers detected in recent context",
        }
    if transition_similarity < 0.18 and any(marker in text for marker in transition_markers):
        return {
            "state_type": "current_goal",
            "state_value": "topic_transition",
            "confidence": 0.86,
            "reason": "low similarity plus transition markers detected in recent context",
        }
    if any(marker in text for marker in goal_markers):
        return {
            "state_type": "current_goal",
            "state_value": "formalize_or_execute_next_step",
            "confidence": 0.78,
            "reason": "goal or planning markers detected in recent context",
        }
    if any(marker in text for marker in stance_markers):
        return {
            "state_type": "current_stance",
            "state_value": "evaluating_tradeoffs",
            "confidence": 0.73,
            "reason": "stance or comparison markers detected in recent context",
        }
    if any(marker in text for marker in uncertainty_markers):
        return {
            "state_type": "uncertainty_level",
            "state_value": "high_uncertainty",
            "confidence": 0.68,
            "reason": "uncertainty markers detected in recent context",
        }
    return {
        "state_type": "active_problem",
        "state_value": "needs_contextual_analysis",
        "confidence": 0.56,
        "reason": "fallback active problem state",
    }


def state_hint_to_action_label(state_type: str | None, state_value: str | None = None) -> str | None:
    if state_type is None:
        return None
    if state_type == "current_goal" and state_value == "topic_transition":
        return "topic_shift"
    if state_type in {"current_goal", "active_problem"}:
        return "request_how_to"
    if state_type == "blocking_issue" and state_value == "needs_troubleshooting":
        return "feasibility_check"
    if state_type == "blocking_issue":
        return "feasibility_check"
    if state_type == "time_pressure":
        return "follow_up_clarification"
    if state_type == "current_stance":
        return "challenge_or_refine"
    if state_type == "uncertainty_level":
        return "ask_definition"
    return None


def infer_state_subtype_from_text(
    text: str,
    *,
    ground_truth_label: str | None = None,
    predicted_label: str | None = None,
) -> str:
    normalized = normalize_text(text)
    lower = normalized.lower()

    blocking_markers = ["报错", "失败", "卡住", "无法", "不能", "出错", "问题", "阻塞", "错误", "error", "connect"]
    time_pressure_markers = ["尽快", "马上", "立刻", "快速", "赶紧", "来不及", "deadline", "时间不多", "急"]
    stance_markers = ["我觉得", "我认为", "我倾向", "我偏向", "还是", "比较", "权衡", "选择"]
    goal_markers = ["我想先", "先做", "先把", "目标", "计划", "方案", "框架", "步骤", "落地", "实现", "整理"]

    if any(marker in lower for marker in blocking_markers):
        return "blocking_issue_missed"
    if any(marker in lower for marker in time_pressure_markers):
        return "time_pressure_missed"
    if any(marker in lower for marker in stance_markers):
        return "stance_change_missed"
    if ground_truth_label == "topic_shift" or predicted_label == "topic_shift" or any(marker in lower for marker in goal_markers):
        return "goal_shift_missed"
    return "goal_shift_missed"
