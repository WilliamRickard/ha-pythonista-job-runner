Version: 0.1.0

# Architecture

Three layers:

1. `ghkit/`: core logic (GitHub REST/GraphQL, workflows, file formats). Must not import Pythonista modules.
2. `ghkit_pythonista/`: Pythonista adapters (Share Sheet, keychain, UI). Must not contain GitHub API logic.
3. `pythonista_wrappers/`: thin entrypoints only.

Rules:
- No `appex`, `ui`, `console`, `keychain` imports in `ghkit/`.
- All network calls live in `ghkit/http/` and `ghkit/github/`.
- Commands will return a uniform result and produce a run directory (to be implemented next).
