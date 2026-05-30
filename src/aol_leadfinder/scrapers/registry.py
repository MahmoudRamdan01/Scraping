"""Resolve which scrapers are available/instantiated, driven by sources.yaml.

DEFERRED (RED-zone) sources are gated behind FEATURE_* flags: they are neither
listed nor instantiated unless their flag is explicitly enabled.
"""
from __future__ import annotations

import importlib

from ..config import get_settings, get_sources
from ..logging_setup import get_logger
from .base import BaseScraper

log = get_logger("registry")


class SourceUnavailable(Exception):
    pass


def available_sources() -> dict[str, dict]:
    """Sources to show in the UI: enabled and (if deferred) flag-permitted."""
    settings = get_settings()
    out: dict[str, dict] = {}
    for key, meta in get_sources().items():
        if not meta.get("enabled"):
            continue
        flag = meta.get("requires_flag")
        if flag and not settings.feature_flag(flag):
            continue
        out[key] = meta
    return out


def _load_class(key: str, meta: dict) -> type[BaseScraper]:
    module = meta.get("module")
    if not module:
        raise SourceUnavailable(f"{key}: no module configured")
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - surfaced to caller
        raise SourceUnavailable(f"{key}: import failed ({exc})") from exc
    cls = BaseScraper.registry.get(key)
    if cls is None:
        raise SourceUnavailable(f"{key}: no scraper registered under key '{key}'")
    return cls


def instantiate(source_keys: list[str]) -> dict[str, BaseScraper]:
    """Instantiate the requested scrapers, skipping any that are unavailable."""
    settings = get_settings()
    sources = get_sources()
    out: dict[str, BaseScraper] = {}
    for key in source_keys:
        meta = sources.get(key)
        if not meta:
            log.warning("unknown source '%s' — skipping", key)
            continue
        flag = meta.get("requires_flag")
        if flag and not settings.feature_flag(flag):
            log.warning("source '%s' requires flag %s (off) — skipping", key, flag)
            continue
        try:
            cls = _load_class(key, meta)
        except SourceUnavailable as exc:
            log.warning("%s", exc)
            continue
        out[key] = cls(meta)
    return out
