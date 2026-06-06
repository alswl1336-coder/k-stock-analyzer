from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)


def load_project_env() -> bool:
    return load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8-sig")


load_project_env()


def _get_streamlit_secret(key: str) -> Any:
    try:
        import streamlit as st

        return st.secrets.get(key)
    except Exception:
        return None


def get_secret(key: str, default=None):
    value = _get_streamlit_secret(key)
    if value not in (None, ""):
        return value

    value = os.getenv(key)
    if value not in (None, ""):
        return value

    return default


def get_bool_env(key: str, default: bool = False) -> bool:
    value = get_secret(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_cloud_environment() -> bool:
    app_env = str(get_secret("APP_ENV", "")).strip().lower()
    if app_env in {"production", "prod", "cloud", "render", "railway", "fly"}:
        return True
    cloud_keys = ["STREAMLIT_SHARING", "RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "PORT"]
    return any(bool(os.getenv(key)) for key in cloud_keys)


def get_secret_status(key: str) -> bool:
    return bool(str(get_secret(key, "")).strip())


def get_app_config() -> dict:
    keys = ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "DART_API_KEY", "KRX_ID", "KRX_PW", "APP_PASSWORD"]
    return {
        "app_env": get_secret("APP_ENV", "local"),
        "debug_mode": get_bool_env("DEBUG_MODE", False),
        "is_cloud_environment": is_cloud_environment(),
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "secrets": {key: get_secret_status(key) for key in keys},
    }
