"""Tests for machine-readable direct API contract."""

from __future__ import annotations

import json
from pathlib import Path


def _load_contract() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "pythonista_job_runner" / "api" / "openapi.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def test_openapi_contract_has_expected_routes() -> None:
    contract = _load_contract()
    paths = contract["paths"]

    expected_paths = {
        "/",
        "/index.html",
        "/health",
        "/info.json",
        "/stats.json",
        "/jobs.json",
        "/job/{job_id}.json",
        "/tail/{job_id}.json",
        "/stdout/{job_id}.txt",
        "/stderr/{job_id}.txt",
        "/result/{job_id}.zip",
        "/run",
        "/purge",
        "/cancel/{job_id}",
        "/job/{job_id}",
    }
    assert expected_paths.issubset(set(paths.keys()))


def test_openapi_contract_covers_major_error_cases() -> None:
    contract = _load_contract()
    run_responses = contract["paths"]["/run"]["post"]["responses"]
    purge_responses = contract["paths"]["/purge"]["post"]["responses"]

    for code in ("400", "401", "411", "413", "415"):
        assert code in run_responses

    for code in ("200", "400", "401", "413", "415"):
        assert code in purge_responses

    assert "RunnerToken" in contract["components"]["securitySchemes"]


def test_openapi_contract_includes_client_required_response_shapes() -> None:
    contract = _load_contract()

    run_202 = contract["paths"]["/run"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]
    assert run_202 == {"$ref": "#/components/schemas/RunAcceptedResponse"}

    run_schema = contract["components"]["schemas"]["RunAcceptedResponse"]
    assert set(run_schema.get("required", [])) >= {"job_id", "tail_url", "result_url", "jobs_url"}

    job_200 = contract["paths"]["/job/{job_id}.json"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert job_200 == {"$ref": "#/components/schemas/JobStatus"}

    job_schema = contract["components"]["schemas"]["JobStatus"]
    assert set(job_schema.get("required", [])) >= {"job_id", "state", "phase", "runner_version", "limits"}

    tail_200 = contract["paths"]["/tail/{job_id}.json"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert tail_200 == {"$ref": "#/components/schemas/TailResponse"}

    tail_schema = contract["components"]["schemas"]["TailResponse"]
    assert set(tail_schema.get("required", [])) >= {"status", "tail"}
