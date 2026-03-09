<!-- Version: 0.6.12-docs.10 -->
# Release channels

This repository uses a simple two-channel model.

## Stable

- Source of truth: `main`
- Intended for normal users
- Best choice when you want predictable updates and the lowest change risk

## Next

- Source of truth: `next`
- Intended for pre-release validation and earlier feedback
- May contain changes that are not ready for wider use yet

## Promotion flow

1. Develop and validate on `next`.
2. Update user docs and release notes for any user-facing change.
3. Merge or cherry-pick validated changes to `main`.
4. Tag the stable release from `main`.

## Which one should you follow?

- Choose **Stable** when you want the default recommendation.
- Choose **Next** when you want earlier features and are happy to test rougher edges.
