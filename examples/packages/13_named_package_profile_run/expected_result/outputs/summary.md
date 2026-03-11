# Named package profile run example

This job expects the add-on to attach the `demo_formatsize_profile` package profile.
It does not ship its own `requirements.txt`.

Check `package/package_diagnostics.json` for `profile_name` and `install_source: profile_venv`.

Generated sizes:
- `buyout_summary.csv` -> `1.0 kB`
- `liability_curve.json` -> `2.8 kB`
- `trustee_pack.zip` -> `5.2 MB`
