from pathlib import Path

import httpx

from app.config import Settings
from app.services import storage


def test_local_storage_round_trip(tmp_path, monkeypatch):
    settings = Settings(storage_backend="local", upload_dir=tmp_path)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)

    path = storage.store_pdf(42, b"%PDF test")

    assert path.startswith(str(tmp_path))
    assert storage.read_pdf(path) == b"%PDF test"
    storage.delete_pdf(path)
    assert not Path(path).exists()


def test_supabase_storage_round_trip(monkeypatch):
    settings = Settings(
        storage_backend="supabase",
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="server-secret",
        supabase_storage_bucket="private-pdfs",
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(
            200,
            content=b"%PDF test" if method == "GET" else b"{}",
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(storage.httpx, "request", fake_request)

    path = storage.store_pdf(42, b"%PDF test")
    assert path.startswith("supabase://private-pdfs/42/")
    assert storage.read_pdf(path) == b"%PDF test"
    storage.delete_pdf(path)

    assert [call[0] for call in calls] == ["POST", "GET", "DELETE"]
    assert all(call[2]["headers"]["Authorization"] == "Bearer server-secret" for call in calls)
    assert calls[0][2]["content"] == b"%PDF test"
    assert calls[2][2]["json"] == {"prefixes": [path.removeprefix("supabase://private-pdfs/")]}
