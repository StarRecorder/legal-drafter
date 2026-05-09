from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

APP_NAME = "legal-drafter"
ENV_HOME = "LEGAL_DRAFTER_HOME"
ENV_INDEX_PATH = "LEGAL_DRAFTER_INDEX_PATH"
ENV_ARTIFACT_ROOT = "LEGAL_DRAFTER_ARTIFACT_ROOT"
ENV_FILE = "LEGAL_DRAFTER_ENV_FILE"


def get_runtime_home() -> Path:
    override = _read_path_from_env(ENV_HOME)
    if override is not None:
        return override
    return Path(user_data_dir(APP_NAME))


def get_default_index_path() -> Path:
    override = _read_path_from_env(ENV_INDEX_PATH)
    if override is not None:
        return override
    return get_runtime_home() / "law_index.sqlite3"


def get_default_artifact_root() -> Path:
    override = _read_path_from_env(ENV_ARTIFACT_ROOT)
    if override is not None:
        return override
    return Path(user_cache_dir(APP_NAME)) / "artifacts"


def load_env_value(key: str) -> str | None:
    direct = os.getenv(key)
    if direct and direct.strip():
        return direct.strip()

    for env_path in iter_env_files():
        if not env_path.exists():
            continue
        value = _read_env_file(env_path, key)
        if value:
            os.environ.setdefault(key, value)
            return value
    return None


def iter_env_files(start_dir: Path | None = None) -> tuple[Path, ...]:
    candidates: list[Path] = []
    explicit = _read_path_from_env(ENV_FILE)
    if explicit is not None:
        candidates.append(explicit)

    current = (start_dir or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidates.append(directory / ".env")

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return tuple(unique)


def _read_path_from_env(key: str) -> Path | None:
    value = os.getenv(key)
    if not value or not value.strip():
        return None
    return Path(value.strip()).expanduser()


def _read_env_file(path: Path, key: str) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != key:
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            return cleaned
    return None
