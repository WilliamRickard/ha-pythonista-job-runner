# Cached per-job requirements example

This job uses per-job requirements with a vendored wheel so it stays offline-safe.

Run it twice. The second run should normally show package reuse in the add-on diagnostics.

Check these add-on result files after each run:
- `package/package_diagnostics.json`
- `summary.txt`
- `result_manifest.json`

Generated sizes:
- `backup_snapshot.tar` -> `512 Bytes`
- `camera_archive.zip` -> `1.5 kB`
- `grafana_export.json` -> `1.2 MB`
