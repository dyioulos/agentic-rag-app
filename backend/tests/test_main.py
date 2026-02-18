from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_upload_code_creates_workspace_project():
    project_name = f"pytest-upload-{uuid.uuid4().hex[:8]}"
    client = TestClient(app)

    response = client.post(
        "/uploads/code",
        data={"project_name": project_name},
        files={"file": ("sample.py", io.BytesIO(b"print('hello')\n"), "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "sample.py"
    assert payload["size"] == len(b"print('hello')\n")

    project_path = Path(payload["project_path"])
    assert project_path.exists()
    assert (project_path / "sample.py").read_text() == "print('hello')\n"

    projects = client.get("/projects")
    assert projects.status_code == 200
    assert str(project_path.parent) in projects.json()["projects"]
