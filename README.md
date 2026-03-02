Version: 0.1.0

# ghkit-pythonista

A GitHub API toolkit designed to run in Pythonista on iPhone.

This repository is scaffold-only. It sets up a clean structure so you can build:
- a pure-Python core library (`ghkit/`) with GitHub REST and GraphQL workflow logic
- a Pythonista integration layer (`ghkit_pythonista/`) for Share Sheet, keychain, and UI
- thin wrapper entrypoints (`pythonista_wrappers/`) for running on-device

## Quick start (desktop)

    python -m pip install -U pip
    python -m pip install pytest
    python -m pytest -q

## Quick start (Pythonista)

For now, run:

- `pythonista_wrappers/GhKit.py`

It currently provides a minimal console menu to prove imports and folder layout.

## Licence

See LICENSE.
