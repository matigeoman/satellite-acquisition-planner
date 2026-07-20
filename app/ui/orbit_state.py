from __future__ import annotations

import streamlit as st

from app.ui.app_context import get_public_orbit_service


PUBLIC_ORBIT_SNAPSHOT_STATE_KEY = "public_orbit_snapshot"


def load_public_orbit_snapshot(
    *,
    allow_network: bool = True,
    force_refresh: bool = False,
):
    """Pobiera konstelację i zachowuje snapshot w bieżącej sesji UI."""

    snapshot = get_public_orbit_service().load_default_constellation(
        allow_network=allow_network,
        force_refresh=force_refresh,
    )
    st.session_state[PUBLIC_ORBIT_SNAPSHOT_STATE_KEY] = snapshot
    return snapshot


def get_public_orbit_snapshot():
    return st.session_state.get(PUBLIC_ORBIT_SNAPSHOT_STATE_KEY)
