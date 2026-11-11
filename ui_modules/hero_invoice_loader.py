"""Central Hero-themed loading overlay for Selva Motors Streamlit workflows.

Use ``hero_loading_context`` around synchronous work that genuinely takes time.
The overlay is always removed, including when the wrapped operation raises.
This module is presentation-only: it performs no network or Google Sheets I/O.
"""
from __future__ import annotations

import base64
import html
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LOGO_PATH = _PROJECT_ROOT / "assets" / "hero_logo.png"


@dataclass
class _LoaderState:
    """Execution-context-local loader handle with nested-use protection."""

    placeholder: Any
    depth: int = 1
    hidden: bool = False
    token: Token | None = None


_ACTIVE_LOADER: ContextVar[_LoaderState | None] = ContextVar(
    "selva_motors_active_hero_loader", default=None
)


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    """Cache the local logo bytes once per process; no external access."""
    try:
        encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""


def _loader_markup(message: str, wait_text: str, logo_uri: str) -> str:
    safe_message = html.escape(str(message or "Working..."))
    safe_wait_text = html.escape(str(wait_text or "Please wait while this operation completes."))
    logo = (
        f'<img class="hero-global-logo" src="{logo_uri}" alt="Hero Selva Motors" />'
        if logo_uri
        else '<div class="hero-global-wordmark">HERO <span>SELVA MOTORS</span></div>'
    )
    return f"""
    <style>
      .hero-global-overlay {{
        position:fixed; inset:0; z-index:2147483000; display:flex;
        align-items:center; justify-content:center; box-sizing:border-box;
        padding:20px; background:
          radial-gradient(circle at 50% 18%, rgba(190,24,48,.22), transparent 36%),
          linear-gradient(145deg, rgba(4,7,13,.985), rgba(13,17,25,.99));
        backdrop-filter:blur(8px);
      }}
      .hero-global-card {{
        width:min(440px,100%); box-sizing:border-box; padding:30px 28px 26px;
        text-align:center; border:1px solid rgba(255,255,255,.12); border-radius:22px;
        background:linear-gradient(155deg,rgba(25,30,40,.98),rgba(9,12,18,.99));
        box-shadow:0 28px 90px rgba(0,0,0,.52),0 0 38px rgba(190,24,48,.12);
        color:#f8fafc; overflow:hidden; font-family:Arial,sans-serif;
      }}
      .hero-global-logo-wrap {{ display:inline-flex; align-items:center; justify-content:center;
        max-width:100%; margin:0 auto 23px; padding:7px 12px; border-radius:12px; background:#fff; }}
      .hero-global-logo {{ display:block; width:min(275px,72vw); height:auto; }}
      .hero-global-wordmark {{ color:#e31837; font-size:27px; font-weight:900; letter-spacing:2px; }}
      .hero-global-wordmark span {{ display:block; color:#1f2937; font-size:10px; letter-spacing:3px; }}
      .hero-global-eyebrow {{ color:#f87171; font-size:10px; font-weight:800;
        letter-spacing:3px; text-transform:uppercase; margin-bottom:12px; }}
      .hero-global-spinner {{ position:relative; width:66px; height:66px; margin:0 auto 19px;
        border:4px solid rgba(255,255,255,.10); border-top-color:#e31837;
        border-right-color:#e31837; border-radius:50%; animation:heroGlobalSpin .85s linear infinite;
        box-shadow:0 0 22px rgba(227,24,55,.17); }}
      .hero-global-spinner:after {{ content:""; position:absolute; inset:10px;
        border:2px solid rgba(227,24,55,.25); border-bottom-color:#fca5a5;
        border-radius:50%; animation:heroGlobalSpin 1.35s linear infinite reverse; }}
      .hero-global-title {{ margin:0; color:#fff; font-size:22px; font-weight:850; }}
      .hero-global-subtitle {{ margin:8px 0 21px; color:#aeb7c5; font-size:13px; line-height:1.5; }}
      .hero-global-progress {{ height:4px; width:100%; overflow:hidden; border-radius:10px;
        background:rgba(255,255,255,.10); }}
      .hero-global-progress:before {{ content:""; display:block; width:38%; height:100%;
        border-radius:inherit; background:linear-gradient(90deg,#991b1b,#ef4444,#fecaca);
        animation:heroGlobalProgress 1.45s ease-in-out infinite; }}
      .hero-global-foot {{ margin-top:15px; color:#778292; font-size:10px; letter-spacing:1.6px; }}
      @keyframes heroGlobalSpin {{ to {{ transform:rotate(360deg); }} }}
      @keyframes heroGlobalProgress {{ 0% {{ transform:translateX(-110%); }} 100% {{ transform:translateX(290%); }} }}
      @media(max-width:480px) {{ .hero-global-card {{ padding:25px 19px 22px; border-radius:18px; }}
        .hero-global-title {{ font-size:19px; }} .hero-global-subtitle {{ font-size:12px; }} }}
      @media(prefers-reduced-motion:reduce) {{ .hero-global-spinner,
        .hero-global-spinner:after,.hero-global-progress:before {{ animation-duration:3s; }} }}
    </style>
    <div class="hero-global-overlay" role="status" aria-live="polite" aria-label="Selva Motors processing">
      <div class="hero-global-card">
        <div class="hero-global-logo-wrap">{logo}</div>
        <div class="hero-global-eyebrow">Selva Motors · Hero Automotive</div>
        <div class="hero-global-spinner" aria-hidden="true"></div>
        <h2 class="hero-global-title">{safe_message}</h2>
        <p class="hero-global-subtitle">{safe_wait_text}</p>
        <div class="hero-global-progress" aria-hidden="true"></div>
        <div class="hero-global-foot">PLEASE KEEP THIS WINDOW OPEN</div>
      </div>
    </div>
    """


def show_hero_loader(
    message: str = "Working on your request...",
    wait_text: str = "Please wait while Selva Motors completes this operation.",
) -> _LoaderState:
    """Display the shared overlay and return a handle for ``hide_hero_loader``.

    Nested calls reuse the current overlay rather than creating a second one.
    """
    active = _ACTIVE_LOADER.get()
    if active is not None and not active.hidden:
        active.depth += 1
        return active

    placeholder = st.empty()
    placeholder.markdown(
        _loader_markup(message, wait_text, _logo_data_uri()),
        unsafe_allow_html=True,
    )
    state = _LoaderState(placeholder=placeholder)
    state.token = _ACTIVE_LOADER.set(state)
    return state


def hide_hero_loader(loader: _LoaderState | None = None) -> None:
    """Remove the overlay safely; repeated or unmatched hides are harmless."""
    state = loader or _ACTIVE_LOADER.get()
    if state is None or state.hidden:
        return
    state.depth -= 1
    if state.depth > 0:
        return
    try:
        state.placeholder.empty()
    finally:
        state.hidden = True
        if _ACTIVE_LOADER.get() is state:
            try:
                if state.token is not None:
                    _ACTIVE_LOADER.reset(state.token)
                else:
                    _ACTIVE_LOADER.set(None)
            except (ValueError, RuntimeError):
                _ACTIVE_LOADER.set(None)


@contextmanager
def hero_loading_context(
    message: str = "Working on your request...",
    wait_text: str = "Please wait while Selva Motors completes this operation.",
) -> Iterator[None]:
    """Show the Hero loader for exactly the wrapped work; always clean up.

    No artificial sleep or minimum display duration is used. Quick operations
    finish immediately and long operations keep the overlay active naturally.
    """
    loader = show_hero_loader(message, wait_text)
    try:
        yield
    finally:
        hide_hero_loader(loader)


__all__ = ["show_hero_loader", "hide_hero_loader", "hero_loading_context"]
