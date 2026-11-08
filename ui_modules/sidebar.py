"""Role-aware premium sidebar for Selva Motors ERP.

This module only renders navigation and session metadata. It never reads Sheets,
loads business records, refreshes data, or triggers automatic reruns.
"""
from __future__ import annotations

from pathlib import Path
from html import escape
import streamlit as st


def render_sidebar(*, is_admin: bool, is_manager: bool, is_technician: bool,
                   is_prathisha: bool, employee_name: str, user_role: str) -> str:
    """Render the existing role navigation plus a static Home landing page."""
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "hero_logo.png"
    with st.sidebar:
        if logo_path.is_file():
            st.image(str(logo_path), use_container_width=True)
        st.markdown(
            "<div class='sidebar-brand-caption'>HERO CONNECT <span>•</span> SELVA MOTORS ERP</div>",
            unsafe_allow_html=True,
        )
        safe_name = escape(str(employee_name or "Team Member"))
        safe_role = escape(str(user_role or "Staff"))
        st.markdown(
            "<div class='sidebar-user-card'>"
            f"<div class='sidebar-user-name'>{safe_name}</div>"
            f"<div class='sidebar-user-role'>{safe_role}</div>"
            "<div class='sidebar-session-state'><i></i> SECURE SESSION</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("LOG OUT", use_container_width=True, key="hero_sidebar_logout"):
            retained = {
                key: value for key, value in st.session_state.items()
                if key.startswith(("attendance_saved_", "invoice_jobcard_saved_", "delete_request_sent_"))
            }
            st.session_state.clear()
            st.session_state.update(retained)
            st.rerun()

        if is_admin:
            pages = ["Home", "Reports", "Attendance", "Admin Panel", "Hero Bikes", "Manual Invoice Generator", "Extra Fittings"]
        elif is_manager:
            pages = ["Home", "Attendance", "Reports", "Manual Invoice Generator", "Hero Bikes", "LETTER PAD", "Extra Fittings"]
        elif is_technician:
            pages = ["Home", "Attendance", "Upload Invoice", "Daily Service Report", "Manual Invoice Generator", "Delete Invoice Request", "Hero Bikes"]
        elif is_prathisha:
            pages = ["Home", "Attendance", "Reports", "Hero Bikes", "Extra Fittings"]
        else:
            pages = ["Home", "Attendance"]

        icons = {
            "Home": "⌂", "Reports": "▤", "Attendance": "◎", "Admin Panel": "⚙",
            "Hero Bikes": "◈", "Manual Invoice Generator": "▧", "Extra Fittings": "＋",
            "Upload Invoice": "⇧", "Daily Service Report": "▤",
            "Delete Invoice Request": "⌫", "LETTER PAD": "▤",
        }
        st.markdown("<div class='sidebar-nav-label'>WORKSPACE</div>", unsafe_allow_html=True)
        labels = [f"{icons.get(page, '•')}  {page}" for page in pages]
        selected = st.radio("Workspace", labels, label_visibility="collapsed", key="hero_workspace_nav")
        return selected.split("  ", 1)[1]
