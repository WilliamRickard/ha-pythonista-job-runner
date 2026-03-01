# Pythonista Job Runner Add-ons

This is a Home Assistant add-on repository containing the **Pythonista Job Runner** add-on.

## Add this repository to Home Assistant

In Home Assistant:
1. Settings -> Add-ons -> Add-on Store
2. Top-right menu (three dots) -> Repositories
3. Add this URL:
   `https://github.com/WilliamRickard/ha-pythonista-job-runner`

Tip: you can also create a My Home Assistant link once your repo URL is final:
- https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=<URL_ENCODED_REPO_URL>

## Add-ons

- `pythonista_job_runner`: Runs Python jobs sent from Pythonista and returns results as a zip.

## Development workflow

- Make changes under `pythonista_job_runner/`
- Bump `pythonista_job_runner/config.yaml` version for each release
- Push to GitHub
- In Home Assistant: open the add-on and click **Update** (or **Rebuild** for local changes)

## Support

- File issues in this repository.
