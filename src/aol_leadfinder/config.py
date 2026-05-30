"""Configuration loading: paths, YAML config, .env feature flags.

All tunable behaviour (categories, sources, scoring, filters) lives in the
``config/`` YAML files at the repo root so non-developers can change it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# config.py -> aol_leadfinder -> src -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]

_TRUE = {"1", "true", "yes", "on"}


def _as_bool(value: str | None) -> bool:
    return str(value).strip().lower() in _TRUE if value is not None else False


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name)
    return Path(val).expanduser() if val else default


@lru_cache(maxsize=1)
def _load_dotenv_once() -> None:
    if load_dotenv is not None:
        env_file = REPO_ROOT / ".env"
        if env_file.exists():
            load_dotenv(env_file)


@dataclass
class Settings:
    repo_root: Path = REPO_ROOT
    config_dir: Path = field(default_factory=lambda: _env_path("AOL_CONFIG_DIR", REPO_ROOT / "config"))
    data_dir: Path = field(default_factory=lambda: _env_path("AOL_DATA_DIR", REPO_ROOT / "data"))
    default_country: str = "Egypt"
    default_region: str = "EG"

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "leads.db"

    @property
    def export_dir(self) -> Path:
        d = self.data_dir / "exports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def feature_flag(self, name: str) -> bool:
        """Return True only if the FEATURE_* env flag is explicitly enabled."""
        return _as_bool(os.environ.get(name, "false"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv_once()
    return Settings(
        default_country=os.environ.get("DEFAULT_COUNTRY", "Egypt"),
        default_region=os.environ.get("DEFAULT_REGION", "EG"),
    )


def load_yaml(name: str) -> dict:
    path = get_settings().config_dir / name
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_categories() -> list[dict]:
    return load_yaml("categories.yaml").get("categories", [])


def get_sources() -> dict[str, dict]:
    return load_yaml("sources.yaml").get("sources", {})


def get_scoring() -> dict:
    return load_yaml("scoring.yaml")


def get_filters() -> dict:
    return load_yaml("filters.yaml")
