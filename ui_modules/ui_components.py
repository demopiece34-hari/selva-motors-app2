"""Small reusable presentation components for Selva Motors ERP.

All functions render static/local UI only. No Google Sheets access is permitted here.
"""
from __future__ import annotations

from html import escape
import streamlit as st


def render_page_header(title: str, subtitle: str, chip: str = "") -> None:
    safe_title, safe_subtitle, safe_chip = map(escape, (str(title), str(subtitle), str(chip)))
    chip_html = f"<span class='status-chip'>◆ {safe_chip}</span>" if safe_chip else ""
    st.markdown(
        f"<section class='hero-panel'>{chip_html}<h1>{safe_title}</h1><p>{safe_subtitle}</p></section>",
        unsafe_allow_html=True,
    )


def render_section_title(title: str, subtitle: str = "") -> None:
    safe_title, safe_subtitle = escape(str(title)), escape(str(subtitle))
    st.markdown(
        f"<div class='ui-section-heading'><div>{safe_title}</div><p>{safe_subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def render_home_landing(employee_name: str, user_role: str) -> None:
    """Static landing page: no metrics, business-data reads, or API-backed widgets."""
    render_page_header(
        "Selva Motors Workspace",
        "A focused service operations workspace. Choose a task from the navigation to continue.",
        "HERO CONNECT",
    )
    safe_name = escape(str(employee_name or "Team Member"))
    safe_role = escape(str(user_role or "Staff"))
    st.markdown(
        "<div class='home-welcome-panel'>"
        "<div class='home-eyebrow'>WELCOME BACK</div>"
        f"<div class='home-user-title'>{safe_name}</div>"
        f"<div class='home-role-chip'>{safe_role}</div>"
        "<div class='home-divider'></div>"
        "<div class='home-guidance-title'>WORKSPACE READY</div>"
        "<div class='home-guidance-copy'>Use the left navigation to open Attendance, Invoice Entry, Reports, or your other permitted tools. "
        "Business records are not loaded on this page.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    render_section_title("Your workspace", "Direct access to the tools enabled for your account.")
    st.markdown(
        "<div class='home-feature-grid'>"
        "<div class='home-feature-card'><span>01</span><b>Attendance</b><small>GPS-based attendance entry</small></div>"
        "<div class='home-feature-card'><span>02</span><b>Invoice Entry</b><small>Upload or create service invoices</small></div>"
        "<div class='home-feature-card'><span>03</span><b>Reports</b><small>Generate reports when requested</small></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Lightweight landing page • No spreadsheet data is fetched to display this screen.")
