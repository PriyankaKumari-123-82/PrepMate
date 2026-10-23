from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

import httpx

from app.config import Settings, get_settings


def _supabase_settings(settings: Settings) -> tuple[str, dict[str, str], str]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase PDF storage requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    base_url = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    return base_url, headers, settings.supabase_storage_bucket


def _object_path(storage_path: str, bucket: str) -> str:
    parsed = urlsplit(storage_path)
    key = unquote(parsed.path.lstrip("/"))
    if parsed.scheme != "supabase" or parsed.netloc != bucket or not key:
        raise ValueError("Invalid Supabase storage path")
    if any(part in {".", ".."} for part in key.split("/")):
        raise ValueError("Invalid Supabase storage path")
    return key


def _object_url(base_url: str, bucket: str, key: str) -> str:
    return f"{base_url}/storage/v1/object/{quote(bucket, safe='')}/{quote(key, safe='/')}"


def store_pdf(user_id: int, data: bytes) -> str:
    settings = get_settings()
    key = f"{user_id}/{uuid4().hex}.pdf"
    if settings.storage_backend == "supabase":
        base_url, headers, bucket = _supabase_settings(settings)
        httpx.request(
            "POST",
            _object_url(base_url, bucket, key),
            content=data,
            headers={**headers, "Content-Type": "application/pdf", "x-upsert": "false"},
            timeout=60,
        ).raise_for_status()
        return f"supabase://{bucket}/{key}"

    directory = settings.upload_dir / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.pdf"
    path.write_bytes(data)
    return str(path)


def read_pdf(storage_path: str) -> bytes:
    if not storage_path.startswith("supabase://"):
        return Path(storage_path).read_bytes()

    base_url, headers, bucket = _supabase_settings(get_settings())
    key = _object_path(storage_path, bucket)
    response = httpx.request(
        "GET", _object_url(base_url, bucket, key), headers=headers, timeout=60
    )
    response.raise_for_status()
    return response.content


def delete_pdf(storage_path: str) -> None:
    if storage_path.startswith("supabase://"):
        base_url, headers, bucket = _supabase_settings(get_settings())
        key = _object_path(storage_path, bucket)
        response = httpx.request(
            "DELETE",
            f"{base_url}/storage/v1/object/{quote(bucket, safe='')}",
            json={"prefixes": [key]},
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        return

    path = Path(storage_path).resolve()
    upload_root = get_settings().upload_dir.resolve()
    if path.is_relative_to(upload_root) and path.is_file():
        path.unlink()
