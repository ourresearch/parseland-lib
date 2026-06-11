import json
import subprocess
import sys
from pathlib import Path


def test_workflow_claim_accepts_onboarding_status(tmp_path):
    workflow_dir = tmp_path / "workflow"
    workflow_dir.mkdir()
    queue_path = workflow_dir / "publisher-field-queue.v2.ndjson"
    queue_path.write_text(
        json.dumps(
            {
                "task_id": "v2_ssrn_pdf_url",
                "publisher_id": "ssrn",
                "field": "pdf_url",
                "queue_type": "onboarding",
                "status": "onboarding",
                "priority": 72.5,
            }
        )
        + "\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/workflow_claim.py",
            "--run-id",
            "test-run",
            "--workflow-dir",
            str(workflow_dir),
            "--agent-id",
            "agent-onboarding",
            "--queue-type",
            "onboarding",
            "--field",
            "pdf_url",
            "--publisher",
            "ssrn",
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload["claimed_count"] == 1
    assert payload["tasks"][0]["task_id"] == "v2_ssrn_pdf_url"

    updated = json.loads(queue_path.read_text().strip())
    assert updated["assigned_agent"] == "agent-onboarding"
    assert updated["status"] == "in_progress"

    claims = [json.loads(line) for line in (workflow_dir / "task-claims.ndjson").read_text().splitlines()]
    assert claims == [
        {
            "run_id": "test-run",
            "task_id": "v2_ssrn_pdf_url",
            "publisher_id": "ssrn",
            "field": "pdf_url",
            "queue_type": "onboarding",
            "agent_id": "agent-onboarding",
            "claimed_at": claims[0]["claimed_at"],
            "status": "in_progress",
        }
    ]
