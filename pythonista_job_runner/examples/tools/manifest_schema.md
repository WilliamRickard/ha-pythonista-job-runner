Version: 0.6.13-examples.1

# Manifest schema notes

The examples manifest is stored in `../manifest.json`.

Top-level keys:
- `_version`: manifest file revision string
- `schema_version`: integer schema version
- `examples_version`: integer examples suite version
- `tracks`: list of track metadata
- `examples`: list of example metadata entries

Each example entry must contain:
- `id`: folder name such as `01_hello_world`
- `order`: numeric sort order matching the folder prefix
- `track`: `core` or `toolchain`
- `title`: user-facing title
- `status`: `scaffold`, `implemented`, or `validated`
- `requires_toolchain`: boolean
- `folder`: relative path to the example folder
- `readme`: relative path to the example README
- `job_src`: relative path to the source folder used to build the zip
- `job_zip`: relative path to the built zip file
- `notes`: short implementation note

The Phase 1 validator enforces this shape directly in Python so it stays dependency-light.
