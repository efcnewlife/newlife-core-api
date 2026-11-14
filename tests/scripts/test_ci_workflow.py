"""
Offline checks for .github/workflows/ci.yml (EFC-311, ADR 0039): staging deployments are serialized and never
cancelled, only main and version tags reach Azure, and no job migrates a database, touches a firewall, or deploys
production. Reads the workflow file only; GitHub's own behaviour is verified by the operator.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
AZURE_JOBS = ["publish", "deploy-staging"]


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _runs(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_staging_deployments_run_one_at_a_time_and_are_never_cancelled(workflow):
    deploy = workflow["jobs"]["deploy-staging"]
    assert deploy["concurrency"] == {"group": "staging-api-deploy", "cancel-in-progress": False}
    assert set(deploy["needs"]) == {"image", "publish"}


def test_only_main_and_version_tags_publish_once_enabled(workflow):
    publish = workflow["jobs"]["publish"]
    assert publish["needs"] == "image"
    assert publish["if"] == "needs.image.outputs.publish == 'true' && vars.AZURE_CLIENT_ID != ''"
    target = next(step for step in workflow["jobs"]["image"]["steps"] if step.get("id") == "target")
    assert 'if [ "$EVENT" = pull_request ]; then\n  echo "publish=false"' in target["run"]
    assert "scripts/release-target.sh" in target["run"]


def test_only_azure_jobs_get_an_oidc_token_through_the_staging_environment(workflow):
    for name, job in workflow["jobs"].items():
        token = job.get("permissions", {}).get("id-token")
        if name in AZURE_JOBS:
            assert token == "write", name
            environment = job["environment"]
            assert (environment if isinstance(environment, str) else environment["name"]) == "staging", name
        else:
            assert token is None, name
            assert "environment" not in job, name
    assert workflow["permissions"] == {"contents": "read"}


def test_no_job_migrates_changes_firewalls_or_deploys_production(workflow):
    text = WORKFLOW.read_text()
    for forbidden in ["alembic", "firewall-rule", "init-all", "app-newlife-api-prod", "rollback"]:
        assert all(forbidden not in _runs(job) for job in workflow["jobs"].values()), forbidden
    assert "AZURE_CLIENT_SECRET" not in text and "client-secret" not in text


def test_piped_scripts_fail_their_step(workflow):
    assert workflow["defaults"]["run"]["shell"] == "bash"
