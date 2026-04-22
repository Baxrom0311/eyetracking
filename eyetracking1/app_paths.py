from __future__ import annotations

import os
import sys
from pathlib import Path

from app_meta import APP_NAME


MODULE_DIR = Path(__file__).resolve().parent
BUNDLED_MODELS_DIR = MODULE_DIR / "models"
BUNDLED_FACE_LANDMARKER_MODEL = BUNDLED_MODELS_DIR / "face_landmarker.task"
PORTABLE_RUNTIME_ROOT = MODULE_DIR / ".runtime"


def _user_data_root() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        base = Path(os.getenv("LOCALAPPDATA") or (home / "AppData" / "Local"))
        return base / APP_NAME
    base = Path(os.getenv("XDG_DATA_HOME") or (home / ".local" / "share"))
    return base / APP_NAME


def _user_cache_root() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Caches" / APP_NAME
    if sys.platform.startswith("win"):
        base = Path(os.getenv("LOCALAPPDATA") or (home / "AppData" / "Local"))
        return base / APP_NAME / "Cache"
    base = Path(os.getenv("XDG_CACHE_HOME") or (home / ".cache"))
    return base / APP_NAME


def _usable_root(preferred: Path, fallback: Path) -> Path:
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


APP_SUPPORT_DIR = _usable_root(_user_data_root(), PORTABLE_RUNTIME_ROOT / "support")
APP_CACHE_DIR = _usable_root(_user_cache_root(), PORTABLE_RUNTIME_ROOT / "cache")
USER_MODELS_DIR = APP_SUPPORT_DIR / "models"
USER_FACE_LANDMARKER_MODEL = USER_MODELS_DIR / "face_landmarker.task"
CALIBRATION_FILE = APP_SUPPORT_DIR / "calibration.json"
TTS_CACHE_PATH = APP_CACHE_DIR / "tts"


def ensure_runtime_dirs() -> None:
    for path in (APP_SUPPORT_DIR, APP_CACHE_DIR, USER_MODELS_DIR, TTS_CACHE_PATH):
        path.mkdir(parents=True, exist_ok=True)


def resolve_face_landmarker_model() -> Path:
    override = os.getenv("GAZESPEAK_FACE_LANDMARKER_MODEL")
    if override:
        return Path(override).expanduser()
    if BUNDLED_FACE_LANDMARKER_MODEL.exists():
        return BUNDLED_FACE_LANDMARKER_MODEL
    return USER_FACE_LANDMARKER_MODEL


def runtime_snapshot() -> dict[str, str]:
    return {
        "support_dir": str(APP_SUPPORT_DIR),
        "cache_dir": str(APP_CACHE_DIR),
        "bundled_model": str(BUNDLED_FACE_LANDMARKER_MODEL),
        "active_model": str(resolve_face_landmarker_model()),
        "calibration_file": str(CALIBRATION_FILE),
        "tts_cache_dir": str(TTS_CACHE_PATH),
    }


ensure_runtime_dirs()
