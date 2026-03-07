# Release Channels

This repository uses a practical two-channel model.

## Stable channel
- Source of truth: `main` branch.
- Intended for normal users.
- Changes are validated via repository test gates before tagging.

## Next/Canary channel
- Source of truth: `next` branch.
- Intended for early adopters and pre-release validation.
- May include migration notes and breaking changes not yet promoted to stable.

## Promotion flow
1. Develop and validate on `next`.
2. Document noteworthy changes in add-on and integration docs.
3. Cherry-pick or merge validated changes to `main`.
4. Tag stable version from `main`.

## User guidance
- If you want predictable updates, follow stable (`main`/release tags).
- If you want earliest features, follow next/canary (`next`) and expect occasional churn.
