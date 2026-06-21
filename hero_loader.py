from __future__ import annotations

import time
import streamlit as st


def show_loader(message: str = "Loading...", wait_text: str = "Please wait", duration: float = 1.0) -> None:
    duration = max(0.4, min(float(duration), 2.5))
    placeholder = st.empty()
    placeholder.markdown(
        f"""
        <div style="
            position:fixed;inset:0;z-index:999999;
            background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(255,245,245,.98));
            display:flex;align-items:center;justify-content:center;
            backdrop-filter:blur(6px);">
            <div style="
                width:min(92vw,420px);
                border-radius:30px;
                border:1px solid rgba(239,68,68,.18);
                box-shadow:0 30px 80px rgba(127,29,29,.22);
                background:white;
                padding:28px 24px;
                text-align:center;">
                <div style="font-size:15px;letter-spacing:4px;font-weight:900;color:#ef4444;margin-bottom:6px;">HERO</div>
                <div style="font-size:30px;font-weight:1000;letter-spacing:-.8px;color:#111827;">{message}</div>
                <div style="margin:18px auto 16px auto;width:68px;height:68px;border-radius:50%;
                    border:7px solid #fee2e2;border-top-color:#ef4444;animation:heroSpin .85s linear infinite;"></div>
                <div style="font-size:14px;color:#475569;font-weight:700;">{wait_text}</div>
                <div style="font-size:12px;color:#94a3b8;margin-top:8px;">Auto closing...</div>
            </div>
        </div>
        <style>@keyframes heroSpin{{to{{transform:rotate(360deg)}}}}</style>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(duration)
    placeholder.empty()
