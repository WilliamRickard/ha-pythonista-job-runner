# Offline wheelhouse install example

This job does not bundle the wheel inside the zip.
Instead, it expects the wheel to be copied into `/config/wheel_uploads/` first.

Check `package/package_diagnostics.json` for `install_source: local_wheelhouse` or `local_only_status: ok`.

Generated sizes:
- `energy_dashboard.csv` -> `768 Bytes`
- `sensor_history.json` -> `2.0 kB`
- `year_end_archive.zip` -> `3.6 MB`
