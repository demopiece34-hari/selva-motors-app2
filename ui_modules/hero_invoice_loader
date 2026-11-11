"""Reusable Hero-themed loader for the Upload Invoice OCR workflow.

Use as a context manager around the synchronous work that should be covered:

    with show_hero_invoice_loader():
        text = extract_invoice_text(file_path)

The overlay is cleared in ``finally`` so it disappears on success and errors.
"""
from __future__ import annotations

import base64
import html
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import streamlit as st


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LOGO_PATH = _PROJECT_ROOT / "assets" / "hero_logo.png"
_DEFAULT_MIN_DISPLAY_SECONDS = 1.0


def _logo_data_uri() -> str:
    """Return the existing Hero/Selva logo as an embedded data URI."""
    try:
        encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""


def _loader_markup(message: str, wait_text: str, logo_uri: str) -> str:
    safe_message = html.escape(message)
    safe_wait_text = html.escape(wait_text)
    logo = (
        f'<img class="hero-invoice-logo" src="{logo_uri}" '
        'alt="Hero Selva Motors" />'
        if logo_uri
        else '<div class="hero-invoice-wordmark">HERO <span>SELVA MOTORS</span></div>'
    )

    return f"""
    <style>
      .hero-invoice-overlay {{
        position: fixed; inset: 0; z-index: 1000000;
        display: flex; align-items: center; justify-content: center;
        padding: 20px; box-sizing: border-box;
        background:
          radial-gradient(circle at 50% 18%, rgba(190,24,48,.22), transparent 34%),
          linear-gradient(145deg, rgba(4,7,13,.985), rgba(13,17,25,.99));
        backdrop-filter: blur(8px);
      }}
      .hero-invoice-card {{
        width: min(440px, 100%); box-sizing: border-box;
        padding: 30px 28px 26px; text-align: center;
        border: 1px solid rgba(255,255,255,.12); border-radius: 22px;
        background: linear-gradient(155deg, rgba(25,30,40,.98), rgba(9,12,18,.99));
        box-shadow: 0 28px 90px rgba(0,0,0,.52), 0 0 38px rgba(190,24,48,.12);
        color: #f8fafc; overflow: hidden;
      }}
      .hero-invoice-logo-wrap {{
        display: inline-flex; align-items: center; justify-content: center;
        max-width: 100%; margin: 0 auto 23px; padding: 7px 12px;
        border-radius: 12px; background: #fff;
      }}
      .hero-invoice-logo {{ display: block; width: min(275px, 72vw); height: auto; }}
      .hero-invoice-wordmark {{ color: #ef233c; font-size: 27px; font-weight: 900; letter-spacing: 2px; }}
      .hero-invoice-wordmark span {{ display: block; color: #e5e7eb; font-size: 10px; letter-spacing: 3px; }}
      .hero-invoice-eyebrow {{
        color: #f87171; font-size: 10px; font-weight: 800;
        letter-spacing: 3px; text-transform: uppercase; margin-bottom: 12px;
      }}
      .hero-invoice-spinner {{
        position: relative; width: 66px; height: 66px; margin: 0 auto 19px;
        border: 4px solid rgba(255,255,255,.10); border-top-color: #e31837;
        border-right-color: #e31837; border-radius: 50%;
        animation: heroInvoiceSpin .85s linear infinite;
        box-shadow: 0 0 22px rgba(227,24,55,.17);
      }}
      .hero-invoice-spinner:after {{
        content: ""; position: absolute; inset: 10px;
        border: 2px solid rgba(227,24,55,.25); border-bottom-color: #fca5a5;
        border-radius: 50%; animation: heroInvoiceSpin 1.35s linear infinite reverse;
      }}
      .hero-invoice-title {{ margin: 0; color: #fff; font-size: 22px; font-weight: 850; }}
      .hero-invoice-subtitle {{ margin: 8px 0 21px; color: #aeb7c5; font-size: 13px; }}
      .hero-invoice-progress {{
        height: 4px; width: 100%; overflow: hidden; border-radius: 10px;
        background: rgba(255,255,255,.10);
      }}
      .hero-invoice-progress:before {{
        content: ""; display: block; width: 38%; height: 100%;
        border-radius: inherit; background: linear-gradient(90deg, #991b1b, #ef4444, #fecaca);
        animation: heroInvoiceProgress 1.45s ease-in-out infinite;
      }}
      .hero-invoice-foot {{ margin-top: 15px; color: #778292; font-size: 10px; letter-spacing: 1.6px; }}
      @keyframes heroInvoiceSpin {{ to {{ transform: rotate(360deg); }} }}
      @keyframes heroInvoiceProgress {{
        0% {{ transform: translateX(-110%); }}
        100% {{ transform: translateX(290%); }}
      }}
      @media (max-width: 480px) {{
        .hero-invoice-card {{ padding: 25px 19px 22px; border-radius: 18px; }}
        .hero-invoice-title {{ font-size: 19px; }}
        .hero-invoice-subtitle {{ font-size: 12px; }}
      }}
      @media (prefers-reduced-motion: reduce) {{
        .hero-invoice-spinner, .hero-invoice-spinner:after,
        .hero-invoice-progress:before {{ animation-duration: 3s; }}
      }}
    </style>
    <div class="hero-invoice-overlay" role="status" aria-live="polite" aria-label="Invoice processing">
      <div class="hero-invoice-card">
        <div class="hero-invoice-logo-wrap">{logo}</div>
        <div class="hero-invoice-eyebrow">Selva Motors · Hero Automotive</div>
        <div class="hero-invoice-spinner" aria-hidden="true"></div>
        <h2 class="hero-invoice-title">{safe_message}</h2>
        <p class="hero-invoice-subtitle">{safe_wait_text}</p>
        <div class="hero-invoice-progress" aria-hidden="true"></div>
        <div class="hero-invoice-foot">PLEASE KEEP THIS WINDOW OPEN</div>
      </div>
    </div>
    """


@contextmanager
def show_hero_invoice_loader(
    message: str = "Processing Invoice...",
    wait_text: str = "Reading invoice details and extracting customer information",
    min_display_seconds: float = _DEFAULT_MIN_DISPLAY_SECONDS,
) -> Iterator[None]:
    """Show the invoice loader while work runs, then always remove it.

    Processing is never paused while it is running. Only when the wrapped work
    finishes in less than ``min_display_seconds`` is the remaining time used to
    meet the minimum visual display duration (1 second by default).
    """
    try:
        minimum = max(0.0, float(min_display_seconds))
    except (TypeError, ValueError):
        minimum = _DEFAULT_MIN_DISPLAY_SECONDS

    placeholder = st.empty()
    started_at = time.monotonic()
    try:
        placeholder.markdown(
            _loader_markup(message, wait_text, _logo_data_uri()),
            unsafe_allow_html=True,
        )
        yield
    finally:
        remaining = minimum - (time.monotonic() - started_at)
        if remaining > 0:
            time.sleep(remaining)
        placeholder.empty()
