"""Shared Streamlit helpers."""
from __future__ import annotations

import streamlit as st

from aol_leadfinder.config import get_settings
from aol_leadfinder.storage.db import get_engine, init_db


@st.cache_resource
def get_ready_engine():
    """A process-wide SQLite engine with tables created."""
    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)
    return engine
