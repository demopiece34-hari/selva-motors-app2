"""GitHub-backed SELVA MOTORS job-card preview and browser printing.

The image is fetched server-side from a public GitHub raw URL and cached for
60 seconds. Printing runs entirely in the browser; this module does not call
Google Sheets or Google Drive.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, UnidentifiedImageError


# ---------------------------------------------------------------------------
# GITHUB IMAGE CONFIGURATION
# ---------------------------------------------------------------------------
# Replace the placeholders with the actual GitHub owner, repository, branch,
# and image path. Example:
# https://raw.githubusercontent.com/selva-motors/erp/main/assets/jobcard.png
#
# Streamlit secrets / environment variable JOBCARD_IMAGE_URL overrides this
# default without requiring a code change.
GITHUB_JOB_CARD_IMAGE_URL = (
    "https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/"
    "YOUR_REPOSITORY/main/assets/selva_motors_jobcard.png"
)

IMAGE_CACHE_TTL_SECONDS = 60
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB safety limit


def _configured_image_url() -> str:
    """Read URL from environment/Streamlit secrets, then use module default."""
    value = os.getenv("JOBCARD_IMAGE_URL", "").strip()
    if not value:
        try:
            value = str(st.secrets.get("JOBCARD_IMAGE_URL", "")).strip()
        except Exception:
            value = ""
    return value or GITHUB_JOB_CARD_IMAGE_URL


@st.cache_data(ttl=IMAGE_CACHE_TTL_SECONDS, max_entries=4, show_spinner=False)
def _download_github_image(image_url: str) -> Tuple[bytes, str, int, int]:
    """Download and validate the image; cached to avoid repeated requests."""
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The Job Card image URL must be a valid HTTPS URL.")

    request = Request(
        image_url,
        headers={
            "User-Agent": "SELVA-MOTORS-ERP-JobCard-Printer/1.0",
            "Accept": "image/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=20) as response:
            image_bytes = response.read(MAX_IMAGE_SIZE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise FileNotFoundError(
                "GitHub could not find the configured image. Check the repository, "
                "branch, and exact file path."
            ) from exc
        raise RuntimeError(f"GitHub image request failed (HTTP {exc.code}).") from exc
    except URLError as exc:
        raise RuntimeError(
            "Could not connect to GitHub. Check the deployed app's internet access."
        ) from exc

    if not image_bytes:
        raise ValueError("GitHub returned an empty image file.")
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError("The Job Card image is larger than the 20 MB limit.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = (image.format or "PNG").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(
            "The configured GitHub file is not a supported image. "
            "Use PNG, JPEG, or WEBP."
        ) from exc

    mime_type = Image.MIME.get(image_format, "image/png")
    if mime_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise ValueError("Use a PNG, JPEG, WEBP, or GIF Job Card image.")

    return image_bytes, mime_type, int(width), int(height)


def _jobcard_page_html(image_bytes: bytes, mime_type: str, width: int, height: int) -> str:
    """Build the isolated preview + copy selector + browser print action."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    image_data_uri = f"data:{mime_type};base64,{encoded}"

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: transparent; color: #161616;
                  font-family: Inter, Arial, sans-serif; }}
    .jobcard-app {{ width: 100%; max-width: 900px; margin: 0 auto; padding: 8px 10px 20px; }}
    .heading {{ margin: 0 0 4px; font-size: 25px; line-height: 1.2; font-weight: 900;
                letter-spacing: -.5px; }}
    .subheading {{ margin: 0 0 16px; color: #737373; font-size: 13px; }}
    .preview-row {{ display: flex; justify-content: center; width: 100%; }}
    .paper {{ width: min(100%, 430px); aspect-ratio: 210 / 297; display: flex;
              align-items: center; justify-content: center; overflow: hidden;
              background: #fff; border: 1px solid #e5e5e5; border-radius: 8px;
              box-shadow: 0 12px 32px rgba(0,0,0,.12); }}
    .paper img {{ display: block; width: 100%; height: 100%; object-fit: contain;
                  object-position: center; }}
    .controls {{ width: min(100%, 430px); margin: 16px auto 0; }}
    .label {{ display: block; margin: 0 0 8px; font-size: 13px; font-weight: 900;
              letter-spacing: .65px; }}
    .copy-input {{ width: 100%; height: 48px; padding: 0 13px; border: 1px solid #d4d4d4;
                   border-radius: 12px; background: #fff; color: #111; font-size: 17px;
                   font-weight: 700; outline: none; }}
    .copy-input:focus {{ border-color: #e31837; box-shadow: 0 0 0 3px rgba(227,24,55,.12); }}
    .print-button {{ width: 100%; min-height: 52px; margin-top: 12px; border: 0;
                     border-radius: 13px; color: #fff; background: linear-gradient(135deg,#e31837,#9f001d);
                     font-size: 15px; font-weight: 900; letter-spacing: .55px;
                     cursor: pointer; box-shadow: 0 12px 24px rgba(227,24,55,.22); }}
    .print-button:hover {{ filter: brightness(1.06); }}
    .print-button:disabled {{ opacity: .6; cursor: wait; }}
    .helper {{ min-height: 18px; margin: 8px 0 0; color: #737373; font-size: 12px; }}
    @media (max-width: 520px) {{
        .jobcard-app {{ padding-left: 2px; padding-right: 2px; }}
        .heading {{ font-size: 21px; }}
        .paper {{ width: min(100%, 380px); }}
    }}
</style>
</head>
<body>
<div class="jobcard-app">
    <h2 class="heading">SELVA MOTORS — JOBCARD</h2>
    <p class="subheading">Latest configured image from GitHub · Original aspect ratio · A4 portrait preview</p>
    <div class="preview-row">
        <div class="paper">
            <img src="{image_data_uri}" alt="SELVA MOTORS Technician Job Card preview"
                 width="{width}" height="{height}">
        </div>
    </div>
    <div class="controls">
        <label class="label" for="copy-count">NUMBER OF COPIES</label>
        <input class="copy-input" id="copy-count" type="number" min="1" max="100"
               step="1" value="1" inputmode="numeric">
        <button class="print-button" id="print-jobcard" type="button">PRINT JOBCARD</button>
        <p class="helper" id="print-status" aria-live="polite">Each copy will print as one A4 portrait page.</p>
    </div>
</div>
<script>
(() => {{
    const imageBase64 = "{encoded}";
    const mimeType = "{mime_type}";
    const copyInput = document.getElementById("copy-count");
    const printButton = document.getElementById("print-jobcard");
    const status = document.getElementById("print-status");

    printButton.addEventListener("click", async () => {{
        const copies = Number.parseInt(copyInput.value, 10);
        if (!Number.isInteger(copies) || copies < 1 || copies > 100) {{
            status.textContent = "Enter a whole number from 1 to 100.";
            copyInput.focus();
            return;
        }}

        // Open synchronously from this real click to avoid popup blockers.
        const printWindow = window.open("about:blank", "_blank");
        if (!printWindow) {{
            status.textContent = "Popup blocked. Allow pop-ups for this ERP page and try again.";
            return;
        }}

        printButton.disabled = true;
        status.textContent = `Preparing ${{copies}} A4 page(s)…`;

        try {{
            const binary = atob(imageBase64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const imageBlob = new Blob([bytes], {{ type: mimeType }});
            const imageUrl = URL.createObjectURL(imageBlob);

            const printDoc = printWindow.document;
            printDoc.open();
            printDoc.write("<!doctype html><html><head><meta charset='utf-8'><title>SELVA MOTORS Job Card</title></head><body></body></html>");
            printDoc.close();

            const style = printDoc.createElement("style");
            style.textContent = `
                @page {{ size: A4 portrait; margin: 0; }}
                * {{ box-sizing: border-box; }}
                html, body {{ margin: 0 !important; padding: 0 !important;
                              width: 210mm; background: #fff; }}
                .jobcard-sheet {{ width: 210mm; height: 297mm; margin: 0;
                                  padding: 0; display: flex; align-items: center;
                                  justify-content: center; overflow: hidden;
                                  break-after: page; page-break-after: always; }}
                .jobcard-sheet:last-child {{ break-after: auto; page-break-after: auto; }}
                .jobcard-sheet img {{ display: block; width: 100%; height: 100%;
                                      margin: 0; padding: 0; object-fit: contain;
                                      object-position: center; }}
                @media screen {{
                    html, body {{ width: 100%; background: #e5e5e5; }}
                    .jobcard-sheet {{ margin: 12px auto; background: #fff;
                                      box-shadow: 0 2px 16px rgba(0,0,0,.16); }}
                }}
            `;
            printDoc.head.appendChild(style);

            const imageLoads = [];
            for (let i = 0; i < copies; i++) {{
                const page = printDoc.createElement("section");
                page.className = "jobcard-sheet";
                const image = printDoc.createElement("img");
                image.alt = "SELVA MOTORS Technician Job Card";
                image.src = imageUrl;
                page.appendChild(image);
                printDoc.body.appendChild(page);
                imageLoads.push(image.decode());
            }}

            await Promise.all(imageLoads);
            status.textContent = "Print preview opened. Choose your printer in the browser dialog.";
            printWindow.focus();
            printWindow.print();
            // Keep the dedicated preview tab open after printing so the user
            // can inspect it or print again. The Blob URL stays valid there.
        }} catch (error) {{
            try {{ printWindow.close(); }} catch (_) {{}}
            status.textContent = "Could not prepare the print preview. Please reload the page and try again.";
        }} finally {{
            printButton.disabled = false;
        }}
    }});
}})();
</script>
</body>
</html>'''


def show_jobcard_print() -> None:
    """Render GitHub Job Card preview and browser print controls."""
    st.markdown(
        "<div style='padding:4px 0 10px 0;'>"
        "<span style='font-size:12px;font-weight:900;letter-spacing:2px;color:#e31837;'>"
        "SELVA MOTORS / PRINT CENTER</span></div>",
        unsafe_allow_html=True,
    )

    image_url = _configured_image_url()
    if "YOUR_GITHUB_USERNAME" in image_url or "YOUR_REPOSITORY" in image_url:
        st.error("GitHub Job Card image URL is not configured yet.")
        st.markdown(
            "Set `JOBCARD_IMAGE_URL` in this file or in Streamlit Secrets. "
            "Use the raw GitHub URL for the committed Job Card image."
        )
        return

    try:
        with st.spinner("Loading the latest configured Job Card image from GitHub…"):
            image_bytes, mime_type, width, height = _download_github_image(image_url)
    except FileNotFoundError as exc:
        st.error("Job Card image was not found on GitHub.")
        st.caption(str(exc))
        return
    except Exception as exc:
        st.error("Unable to load the Job Card image.")
        st.caption(str(exc))
        return

    st.caption(f"Image source: GitHub · Original image: {width} × {height} px")
    components.html(
        _jobcard_page_html(image_bytes, mime_type, width, height),
        height=900,
        scrolling=True,
    )


__all__ = ["show_jobcard_print"]
