"""GitHub-hosted SELVA MOTORS Technician Job Card preview and printing.

Configure the GitHub repository owner, repository name, branch, and image path.
The RAW image address is built internally; no image URL needs to be pasted or shown.
This module intentionally does not import or call the ERP Google Sheets layer.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request
from typing import Tuple
from urllib.parse import quote, urlparse

from PIL import Image
import streamlit as st

# ---------------------------------------------------------------------------
# GITHUB REPOSITORY CONFIGURATION
# Set these four values. Do not paste a RAW URL.
# Example image path: assets/selva_motors_jobcard.jpg
# You can alternatively set the same keys in Streamlit Cloud → Settings → Secrets.
# ---------------------------------------------------------------------------
GITHUB_OWNER = "YOUR_GITHUB_USERNAME"
GITHUB_REPOSITORY = "YOUR_REPOSITORY_NAME"
GITHUB_BRANCH = "main"
JOBCARD_IMAGE_PATH = "assets/selva_motors_jobcard.jpg"

IMAGE_CACHE_TTL_SECONDS = 60
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 20


def _config_value(key: str, default: str) -> str:
    """Read a setting from Streamlit Secrets, env, then this module."""
    secret_value = ""
    try:
        secret_value = str(st.secrets.get(key, "") or "").strip()
    except Exception:
        # Secrets may not be configured in local development.
        secret_value = ""
    env_value = str(os.getenv(key, "") or "").strip()
    return secret_value or env_value or str(default or "").strip()


def _configured_image_url() -> str:
    """Build an internal GitHub RAW address from repository path settings."""
    owner = _config_value("GITHUB_OWNER", GITHUB_OWNER)
    repository = _config_value("GITHUB_REPOSITORY", GITHUB_REPOSITORY)
    branch = _config_value("GITHUB_BRANCH", GITHUB_BRANCH)
    image_path = _config_value("JOBCARD_IMAGE_PATH", JOBCARD_IMAGE_PATH).lstrip("/")

    if not owner or owner == "YOUR_GITHUB_USERNAME":
        return ""
    if not repository or repository == "YOUR_REPOSITORY_NAME":
        return ""
    if not branch or not image_path:
        return ""
    if ".." in image_path.split("/"):
        return ""

    # The address is generated internally. It is never displayed in the UI.
    return (
        "https://raw.githubusercontent.com/"
        f"{quote(owner, safe='')}/{quote(repository, safe='')}/"
        f"{quote(branch, safe='/')}/{quote(image_path, safe='/')}"
    )

@st.cache_data(ttl=IMAGE_CACHE_TTL_SECONDS, max_entries=4, show_spinner=False)
def _download_jobcard_image(image_url: str) -> Tuple[bytes, str]:
    """Download and validate the committed image; cache the original bytes."""
    parsed = urlparse(image_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("The configured Job Card image URL is not a valid HTTP(S) URL.")

    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": "SELVA-MOTORS-ERP/1.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=IMAGE_DOWNLOAD_TIMEOUT_SECONDS) as response:
            image_bytes = response.read()
            content_type = (response.headers.get_content_type() or "").lower()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError("The Job Card image was not found in GitHub. Check the RAW URL and committed file path.") from None
        raise RuntimeError(f"GitHub could not provide the Job Card image (HTTP {exc.code}).") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("Could not connect to GitHub. Check the internet connection and RAW image URL.") from None

    if not image_bytes:
        raise RuntimeError("GitHub returned an empty Job Card image.")

    # Validate the downloaded bytes without resizing, recompressing, or changing them.
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except Exception:
        raise RuntimeError("The configured GitHub file is not a supported, valid image.") from None

    if content_type and not content_type.startswith("image/"):
        # GitHub can occasionally omit or mislabel the MIME type; trust Pillow
        # only when the bytes are genuinely an image.
        content_type = ""

    mime_by_format = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
    }
    mime_type = content_type or mime_by_format.get(image_format, "image/jpeg")
    return image_bytes, mime_type


def _preview_html(data_uri: str) -> str:
    """Responsive A4-like on-screen preview using the unmodified image bytes."""
    safe_data_uri = json.dumps(data_uri)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: transparent; }}
.preview-wrap {{ width: 100%; display: flex; justify-content: center; padding: 8px 0 16px; }}
.a4-preview {{
  width: min(100%, 540px); aspect-ratio: 210 / 297; background: #fff;
  display: flex; align-items: center; justify-content: center;
  padding: 5mm; box-shadow: 0 12px 34px rgba(15,23,42,.16);
  border: 1px solid #e5e7eb; overflow: hidden;
}}
.a4-preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
@media (max-width: 560px) {{ .a4-preview {{ width: 100%; }} }}
</style>
</head>
<body>
  <div class="preview-wrap">
    <div class="a4-preview">
      <img id="jobcard-preview" alt="SELVA MOTORS Technician Job Card preview" src={safe_data_uri}>
    </div>
  </div>
</body>
</html>"""


def _print_controls_html(data_uri: str) -> str:
    """Render a real browser-gesture button so popup blockers allow printing."""
    safe_data_uri = json.dumps(data_uri)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: transparent; }}
.panel {{ width: 100%; padding: 8px 2px 12px; display: flex; flex-wrap: wrap; align-items: end; gap: 14px; }}
.field {{ display: flex; flex-direction: column; gap: 7px; min-width: 190px; }}
.field label {{ font-size: 13px; font-weight: 900; letter-spacing: .7px; color: #202020; }}
.field input {{ height: 44px; width: 190px; border: 1px solid #d1d5db; border-radius: 10px; padding: 0 12px; font-size: 16px; font-weight: 700; color: #111827; background: #fff; }}
button {{ height: 44px; min-width: 210px; border: 0; border-radius: 10px; padding: 0 22px; color: #fff; background: linear-gradient(135deg,#ed1b36,#b5122a); font-size: 14px; font-weight: 900; letter-spacing: .4px; cursor: pointer; box-shadow: 0 7px 17px rgba(180,18,42,.22); }}
button:hover {{ filter: brightness(.96); }}
button:disabled {{ opacity: .65; cursor: wait; }}
#status {{ flex-basis: 100%; min-height: 16px; color: #64748b; font-size: 12px; }}
@media(max-width:520px) {{ .panel {{ align-items: stretch; }} .field, .field input, button {{ width: 100%; }} }}
</style>
</head>
<body>
<div class="panel">
  <div class="field">
    <label for="copy-count">NUMBER OF COPIES</label>
    <input id="copy-count" type="number" min="1" max="100" step="1" value="1" inputmode="numeric">
  </div>
  <button id="print-jobcard" type="button">PRINT JOBCARD</button>
  <div id="status" role="status" aria-live="polite"></div>
</div>
<script>
(() => {{
  const imageDataUri = {safe_data_uri};
  const input = document.getElementById('copy-count');
  const button = document.getElementById('print-jobcard');
  const status = document.getElementById('status');

  button.addEventListener('click', async () => {{
    const copies = Number(input.value);
    if (!Number.isInteger(copies) || copies < 1 || copies > 100) {{
      status.textContent = 'Enter a whole number from 1 to 100.';
      input.focus();
      return;
    }}

    // window.open runs directly inside this click event to avoid popup blocking.
    const printWindow = window.open('', '_blank', 'popup=yes,width=1050,height=900');
    if (!printWindow) {{
      status.textContent = 'Pop-up blocked. Allow pop-ups for this ERP site and click PRINT JOBCARD again.';
      return;
    }}

    button.disabled = true;
    status.textContent = 'Preparing ' + copies + ' A4 print page(s)…';

    const pages = Array.from({{length: copies}}, (_, index) =>
      '<section class="sheet"><img src="' + imageDataUri + '" alt="SELVA MOTORS Technician Job Card copy ' + (index + 1) + '"></section>'
    ).join('');

    const printDocument = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SELVA MOTORS Job Card Print Preview</title>
<style>
@page {{ size: A4 portrait; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; width: 100%; background: #e5e7eb; }}
.sheet {{
  width: 210mm; height: 297mm; margin: 12px auto; padding: 5mm;
  display: flex; align-items: center; justify-content: center;
  background: #fff; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.16);
  break-after: page; page-break-after: always;
}}
.sheet:last-child {{ break-after: auto; page-break-after: auto; }}
.sheet img {{ display: block; max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; }}
@media print {{
  html, body {{ width: 210mm; margin: 0 !important; padding: 0 !important; background: #fff !important; }}
  .sheet {{ margin: 0 !important; box-shadow: none !important; break-after: page; page-break-after: always; }}
  .sheet:last-child {{ break-after: auto; page-break-after: auto; }}
}}
@media screen {{ .sheet {{ max-width: calc(100vw - 24px); }} }}
</style>
</head>
<body>${{pages}}</body>
</html>`;

    try {{
      printWindow.document.open();
      printWindow.document.write(printDocument);
      printWindow.document.close();
      const images = Array.from(printWindow.document.images);
      await Promise.all(images.map((image) => image.decode().catch(() => undefined)));
      status.textContent = 'Print preview ready: ' + copies + ' A4 page(s).';
      window.setTimeout(() => {{
        try {{
          printWindow.focus();
          printWindow.print();
        }} catch (error) {{
          status.textContent = 'The browser could not open the print dialog. Please try again.';
          button.disabled = false;
        }}
      }}, 300);
    }} catch (error) {{
      try {{ printWindow.close(); }} catch (_) {{}}
      status.textContent = 'Could not prepare the print preview. Please try again.';
      button.disabled = false;
    }}
  }});
}})();
</script>
</body>
</html>"""


def show_jobcard_print() -> None:
    """Show GitHub Job Card preview and browser-based multi-copy printing."""
    st.markdown(
        """
        <div style="padding:18px 20px;border-radius:16px;background:linear-gradient(120deg,#111111,#3b0711);color:#fff;margin-bottom:14px;">
          <div style="font-size:12px;font-weight:800;letter-spacing:2px;color:#ffb6c1;">SELVA MOTORS</div>
          <div style="font-size:27px;font-weight:900;line-height:1.2;margin-top:4px;">TECHNICIAN JOBCARD</div>
          <div style="font-size:13px;color:#e5e7eb;margin-top:5px;">A4 portrait preview and printing</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    image_url = _configured_image_url()
    if not image_url:
        st.warning(
            "GitHub image location is not configured. Set GITHUB_OWNER, "
            "GITHUB_REPOSITORY, GITHUB_BRANCH and JOBCARD_IMAGE_PATH in "
            "ui_modules/jobcard_print.py or Streamlit Cloud → Settings → Secrets."
        )
        return

    try:
        with st.spinner("Loading the latest committed Job Card image from GitHub…"):
            image_bytes, mime_type = _download_jobcard_image(image_url)
    except Exception as exc:
        st.error("The Job Card image could not be loaded.")
        st.caption(str(exc))
        st.info("Check that the GitHub repository is public and JOBCARD_IMAGE_PATH matches the committed image path exactly (including upper/lowercase).")
        return

    data_uri = "data:" + mime_type + ";base64," + base64.b64encode(image_bytes).decode("ascii")

    st.markdown(
        "<div style='text-align:center;font-weight:900;letter-spacing:1px;color:#202020;margin:8px 0 2px;'>JOBCARD PREVIEW · A4 PORTRAIT</div>",
        unsafe_allow_html=True,
    )
    st.iframe(_preview_html(data_uri), width="stretch", height=820, tab_index=-1)

    st.markdown(
        "<div style='font-size:15px;font-weight:900;letter-spacing:.6px;color:#202020;margin:4px 0 0;'>PRINT SETTINGS</div>",
        unsafe_allow_html=True,
    )
    st.iframe(_print_controls_html(data_uri), width="stretch", height=112, tab_index=-1)
    st.caption(
        "One copy prints on one A4 portrait page. In the browser print dialog, "
        "choose your printer and turn off browser Headers and footers if they are enabled."
    )


__all__ = ["show_jobcard_print"]
