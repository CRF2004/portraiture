# Manual Label Audit

Date: 2026-06-28

This is a manual spot audit of high-risk proxy-label candidates in `data/processed/evaluation/relabel_candidates.jsonl`.
The goal is not to relabel the whole dataset, but to estimate where the proxy labels are reliable and where they are brittle.

## Audit scope

- 12 high-risk candidates were reviewed by hand.
- The sample was drawn from `state_under_specified`, `action_selection_error`, `reasoning_mismatch`, and `persona_misalignment`.
- The sample was intentionally concentrated on boundary cases, so it should be interpreted as a failure-mode audit, not a random sample estimate.

## Manual verdicts

### Clear label errors

- `baseline:replay_ep_6a22b30c-371c-83ec-8585-6e15f49fc36f_000_005_001:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: this is a continuation of the same writing task, closer to `request_how_to` or `follow_up_clarification`.
- `baseline:replay_ep_6a22b30c-371c-83ec-8585-6e15f49fc36f_000_005_002:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: same thread, still task continuation rather than topic shift.
- `baseline:replay_ep_6a22bfff-598c-83ec-ac8a-e1f6d943b10b_000_003_002:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: chapter refinement within the same outline task.
- `baseline:replay_ep_6a22bfff-598c-83ec-ac8a-e1f6d943b10b_000_003_003:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: same issue as above, still within the same chapter-refinement thread.
- `baseline:replay_ep_6a1f8eea-2c04-83ec-a096-b441d55b9531_000_000_001:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: follow-up clarification about a ResNet residual block, not a topic shift.
- `baseline:replay_ep_6a225e27-0870-83ec-ad4c-4b14e486c624_000_000_001:state_under_specified:goal_shift_missed`
  - Current label: `topic_shift`
  - Manual read: same gradient-clipping discussion, closer to follow-up clarification.

### Borderline cases

- `baseline:replay_ep_6a151b71-dfd4-83ec-a735-0d9c3c621a68_000_000_002:action_selection_error:ranking_error`
  - Current label: `follow_up_clarification`
  - Manual read: plausible, but the intent is partly a request for critique and partly a continuation of prior discussion.

### Acceptable labels

- `baseline:replay_ep_6a216d71-9e5c-83ec-aacf-6addfe35596d_000_000_001:action_selection_error:ranking_error`
  - Current label: `provide_more_context`
  - Manual read: acceptable, because the user is explicitly adding explanation before asking for help.
- `baseline:replay_ep_6a24e9f3-6fec-83ec-82e5-170368e61898_000_000_002:action_selection_error:ranking_error`
  - Current label: `follow_up_clarification`
  - Manual read: correct, the user is refining an earlier request about a figure.
- `baseline:replay_ep_6a179a3c-e27c-83ec-a2b6-12658a2f0d32_000_000_003:reasoning_mismatch:wrong_intent_inference`
  - Current label: `compare_options`
  - Manual read: correct, the user is comparing Rust and C++.
- `baseline:replay_ep_6a13e0cb-0e34-83ec-9947-39773b21c70d_000_000_001:action_selection_error:ranking_error`
  - Current label: `provide_more_context`
  - Manual read: acceptable, because the user is adding installation context and shell output around the Claude Code question.
- `baseline:replay_ep_6a13c0fa-b484-83ec-832b-89158f32cf1c_000_003_001:action_selection_error:ranking_error`
  - Current label: `follow_up_clarification`
  - Manual read: correct, the user is asking for a reference image after a prior visualization request.

## Summary

- Clear errors: 6 / 12
- Borderline: 1 / 12
- Acceptable: 5 / 12

## Post-relabel check

After tightening the `topic_shift` rule and rebuilding the replay set, the previous overuse cases were no longer labeled as `topic_shift`. The current replay label distribution is balanced between `follow_up_clarification` and `topic_shift` at 77 examples each, which is a much healthier boundary than the earlier skewed version.

## Failure modes

1. `topic_shift` was overused for same-thread refinements, especially when the user continues the same chapter, figure, or explanation.
2. `follow_up_clarification` and `provide_more_context` form the most common boundary pair.
3. `compare_options` looked comparatively stable in the reviewed sample.
4. The proxy labeler is more brittle at episode boundaries than within-topic clarification, but the stricter relabel rule now prevents the worst `topic_shift` swallowing errors.

## Audit takeaway

The proxy labels are useful for a benchmark-style replay task, but they are not clean enough to support a strong claim of semantic ground truth.
The paper should continue to describe the task as proxy-labeled replay evaluation and should not overstate exact-intent correctness. The new semantic baseline result is a good reminder that strong text semantics can still beat state routing when the labels become less noisy.
