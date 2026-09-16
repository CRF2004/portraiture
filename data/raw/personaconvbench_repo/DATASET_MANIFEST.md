# PERSONA-Bench / PersonaConvBench Raw Data

Downloaded from Hugging Face:

- Repository: `PERSONABench/PERSONA-Bench`
- File: `Raw_Data_Postized.json`
- License: MIT, as declared in the dataset card
- Download date: 2026-06-28

## File Integrity

- Path: `data/raw/personaconvbench_repo/Raw_Data_Postized.json`
- Size: 179,988,294 bytes
- SHA256: `59cea85862f6779f90dc905d7f4691b83b5521bc9234e9859b054d99645a609e`

The SHA256 matches the Git LFS pointer in the Hugging Face repository.

## Observed Structure

Top-level JSON type: list.

- Posts: 19,215
- Comments: 390,621, including nested replies
- Subreddits: 10
- Post authors: 2,796
- Comment authors: 102,688
- All observed authors: 102,688
- Maximum observed reply depth: 101

Post fields:

- `title`
- `author`
- `url`
- `score`
- `num_comments`
- `content`
- `timestamp`
- `comments`
- `__sub__`
- `__srcfile__`

Comment fields:

- `author`
- `body`
- `score`
- `timestamp`
- `replies`

## Adapter Implications

The current Portraiture pipeline expects personal GPT chat episodes and proxy next-action labels over user turns.
This dataset is Reddit post/comment-tree data, so it needs an adapter before it can be used as multi-user validation:

1. Flatten nested Reddit threads into ordered conversational paths.
2. Select users with enough authored turns for train/validation/test splits.
3. Rewrite proxy label rules for Reddit replies rather than GPT user requests.
4. Preserve subreddit, post, parent-comment, score, timestamp, and depth metadata.
5. Run leakage checks at user and thread boundaries.
