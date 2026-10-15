from app.main import app


def test_required_api_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "get" in paths["/health"]
    assert "post" in paths["/auth/register"]
    assert "post" in paths["/documents"]
    assert "delete" in paths["/documents/{document_id}"]
    assert "get" in paths["/documents/{document_id}/chunks"]
    assert "post" in paths["/tests"]
    assert "post" in paths["/attempts/{attempt_id}/answers"]
    assert "post" in paths["/chat"]
    assert "post" in paths["/artifacts/generate"]
    assert "post" in paths["/artifacts/{artifact_id}/review"]
    assert "post" in paths["/artifacts/{artifact_id}/approve"]
    assert "post" in paths["/courses"]
    assert "get" in paths["/runs/{run_id}"]
    assert "get" in paths["/settings"]
    assert "put" in paths["/settings/models"]
    assert "post" in paths["/settings/api-keys"]
    assert "delete" in paths["/settings/api-keys/{credential_id}"]
