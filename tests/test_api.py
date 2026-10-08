from app.main import app


def test_required_api_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "get" in paths["/health"]
    assert "post" in paths["/auth/register"]
    assert "post" in paths["/documents"]
    assert "post" in paths["/tests"]
    assert "post" in paths["/attempts/{attempt_id}/answers"]
    assert "post" in paths["/chat"]
