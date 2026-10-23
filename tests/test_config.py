from app.config import normalize_database_url


def test_normalize_database_url_escapes_at_in_password():
    url = "postgresql+psycopg://postgres:secret@1@db.example.com:5432/postgres"

    assert normalize_database_url(url) == (
        "postgresql+psycopg://postgres:secret%401@db.example.com:5432/postgres"
    )


def test_normalize_database_url_preserves_encoded_password():
    url = "postgresql+psycopg://postgres:secret%401@db.example.com:5432/postgres"

    assert normalize_database_url(url) == url


def test_normalize_database_url_preserves_sqlite_url():
    url = "sqlite:///./prepmate.db"

    assert normalize_database_url(url) == url
