"""SELVA MOTORS ERP - GitHub-discovered Technician Job Card printer.

Repository discovery order:
1. Existing GitHub environment variables / existing Streamlit secrets.
2. Existing local git remote named ``origin`` in the deployed checkout.

No new repository URL, token, secret, or image path is required. If the deployed
runtime does not expose repository metadata, the module reports that fact and
uses the Job Card asset already shipped in this project as a clearly-labelled
fallback (when present).
"""
from __future__ import annotations

import base64
import configparser
import io
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image
import streamlit.components.v1 as components


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Existing project asset found in the uploaded ERP ZIP. Used only as a
# transparent fallback when GitHub metadata/API is not available.
_LOCAL_JOBCARD_CANDIDATES = (
    PROJECT_ROOT / "assets" / "selva_motors_jobcard.png.jpeg",
    PROJECT_ROOT / "assets" / "selva_motors_jobcard.jpg",
    PROJECT_ROOT / "assets" / "jobcard.png",
    PROJECT_ROOT / "assets" / "jobcard.jpg",
)
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_GITHUB_API = "https://api.github.com"


def _safe_secret(key: str) -> str:
    """Read an already-existing Streamlit secret without requiring one."""
    value = ""
    try:
        value = str(st.secrets.get(key, "") or "").strip()
    except Exception:
        pass
    return value


def _existing_config() -> dict[str, str]:
    """Discover only existing deployment/git configuration; never invent a repo."""
    config: dict[str, str] = {}

    # Environment values supplied by an existing CI/deployment integration.
    for key in (
        "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_OWNER", "GITHUB_REPOSITORY_NAME",
        "GITHUB_BRANCH", "GITHUB_REF_NAME", "GITHUB_REMOTE_URL", "GIT_URL",
        "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            config[key] = value

    # Reuse only matching existing secrets if the app already has them.
    for key in (
        "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_OWNER", "GITHUB_REPOSITORY_NAME",
        "GITHUB_BRANCH", "GITHUB_REMOTE_URL", "GIT_REMOTE_URL", "GITHUB_TOKEN",
        "GH_TOKEN", "GITHUB_PAT",
    ):
        if key not in config:
            value = _safe_secret(key)
            if value:
                config[key] = value

    # If a grouped [github] secret already exists, read its known fields too.
    try:
        github_section = st.secrets.get("github", {})
        if hasattr(github_section, "get"):
            for dest, source in (("GITHUB_REPOSITORY", "repository"),
                                 ("GITHUB_REMOTE_URL", "remote_url"),
                                 ("GITHUB_BRANCH", "branch"),
                                 ("GITHUB_TOKEN", "token")):
                if not config.get(dest):
                    value = str(github_section.get(source, "") or "").strip()
                    if value:
                        config[dest] = value
    except Exception:
        pass

    # Runtime .git metadata is preferred over assumptions about the repo name.
    remote = ""
    branch = ""
    try:
        remote_result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if remote_result.returncode == 0:
            remote = remote_result.stdout.strip()
    except Exception:
        pass
    if not remote:
        # Parse .git/config directly, including ordinary .git directories.
        git_config = PROJECT_ROOT / ".git" / "config"
        if git_config.is_file():
            parser = configparser.ConfigParser()
            try:
                parser.read(git_config, encoding="utf-8")
                remote = parser.get('remote "origin"', "url", fallback="").strip()
            except Exception:
                pass
    if remote:
        config.setdefault("GITHUB_REMOTE_URL", remote)

    for command in (
        ["git", "-C", str(PROJECT_ROOT), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "-C", str(PROJECT_ROOT), "branch", "--show-current"],
    ):
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=2, check=False)
            if result.returncode == 0 and result.stdout.strip():
                branch = result.stdout.strip().split("/", 1)[-1]
                break
        except Exception:
            pass
    if branch:
        config.setdefault("GITHUB_BRANCH", branch)

    return config


def _parse_github_repo(config: dict[str, str]) -> tuple[str, str] | None:
    repo_pair = config.get("GITHUB_REPOSITORY", "").strip()
    if repo_pair and "/" in repo_pair:
        owner, repo = repo_pair.strip("/").split("/", 1)
        repo = repo.removesuffix(".git")
        if owner and repo:
            return owner, repo

    owner = config.get("GITHUB_REPOSITORY_OWNER", "").strip()
    repo = config.get("GITHUB_REPOSITORY_NAME", "").strip()
    if owner and repo:
        return owner, repo.removesuffix(".git")

    remote = config.get("GITHUB_REMOTE_URL", config.get("GIT_REMOTE_URL", "")).strip()
    if not remote:
        return None

    # Supports https://github.com/owner/repo.git and git@github.com:owner/repo.git.
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?$", remote)
    if not match:
        return None
    return match.group(1), match.group(2).removesuffix(".git")


def _github_headers(token: str, accept: str = "application/vnd.github+json") -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "Selva-Motors-ERP-JobCard-Printer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_github_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(15 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError("GitHub repository, branch, or image was not found (404).") from None
        if exc.code in (401, 403):
            raise RuntimeError(
                "GitHub denied access. The repository may be private or the existing token may lack read access."
            ) from None
        raise RuntimeError(f"GitHub request failed (HTTP {exc.code}).") from None
    except Exception as exc:
        raise RuntimeError(f"GitHub connection failed: {type(exc).__name__}.") from None
    if len(payload) > 15 * 1024 * 1024:
        raise RuntimeError("GitHub response was unexpectedly large; image lookup was stopped.")
    try:
        data = json.loads(payload.decode("utf-8"))
    except Exception:
        raise RuntimeError("GitHub returned an invalid API response.") from None
    if not isinstance(data, dict):
        raise RuntimeError("GitHub returned an unexpected response format.")
    return data


@st.cache_data(ttl=60, show_spinner=False)
def _get_default_branch(owner: str, repo: str, token: str) -> str:
    data = _github_json(f"{_GITHUB_API}/repos/{owner}/{repo}", token)
    branch = str(data.get("default_branch", "")).strip()
    if not branch:
        raise RuntimeError("GitHub repository did not report a default branch.")
    return branch


@st.cache_data(ttl=60, show_spinner=False)
def _get_repo_tree(owner: str, repo: str, branch: str, token: str) -> list[dict[str, Any]]:
    encoded_branch = urllib.parse.quote(branch, safe="")
    data = _github_json(
        f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/{encoded_branch}?recursive=1",
        token,
    )
    tree = data.get("tree", [])
    if data.get("truncated"):
        raise RuntimeError("GitHub repository is too large for a complete automatic image search.")
    if not isinstance(tree, list):
        raise RuntimeError("GitHub repository tree response is invalid.")
    return tree


def _candidate_score(path: str) -> int:
    lower = path.lower()
    normal = re.sub(r"[^a-z0-9]", "", lower)
    if "jobcard" not in normal:
        return -1
    name = Path(lower).name
    score = 100
    if "technician" in normal:
        score += 100
    if "jobcard" in name.replace("_", "").replace("-", ""):
        score += 60
    parent_names = "/".join(Path(lower).parts[:-1])
    if "jobcard" in re.sub(r"[^a-z0-9]", "", parent_names):
        score += 50
    if "selva" in normal and "motors" in normal:
        score += 20
    if "assets" in Path(lower).parts:
        score += 10
    if any(word in normal for word in ("backup", "oldversion", "draft", "thumbnail", "thumb")):
        score -= 80
    return score


def _select_jobcard_path(tree: list[dict[str, Any]]) -> tuple[str, str]:
    candidates: list[tuple[int, str, str]] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = str(item.get("path", ""))
        if Path(path).suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        score = _candidate_score(path)
        if score >= 0 and item.get("sha"):
            candidates.append((score, path, str(item["sha"])))
    if not candidates:
        raise RuntimeError("No Job Card image was found in the GitHub repository (searched Job Card image filenames and folders).")
    candidates.sort(key=lambda item: (-item[0], item[1].lower()))
    highest = candidates[0][0]
    best = [item for item in candidates if item[0] == highest]
    if len(best) > 1:
        names = ", ".join(item[1] for item in best[:5])
        raise RuntimeError(f"More than one equally likely Job Card image was found: {names}. Keep one clearly named Technician Job Card image.")
    return best[0][1], best[0][2]


@st.cache_data(ttl=300, show_spinner=False)
def _get_blob_bytes(owner: str, repo: str, blob_sha: str, token: str) -> bytes:
    data = _github_json(f"{_GITHUB_API}/repos/{owner}/{repo}/git/blobs/{blob_sha}", token)
    if data.get("encoding") != "base64" or not data.get("content"):
        raise RuntimeError("GitHub image blob did not contain downloadable image data.")
    try:
        return base64.b64decode(str(data["content"]))
    except Exception:
        raise RuntimeError("GitHub image data could not be decoded.") from None


def _validate_image(image_bytes: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Unsupported image format")
            return image.size
    except Exception:
        raise RuntimeError("The selected Job Card file is not a valid PNG, JPEG, or WebP image.") from None


def _load_local_fallback() -> tuple[bytes, str] | None:
    for path in _LOCAL_JOBCARD_CANDIDATES:
        if path.is_file():
            try:
                data = path.read_bytes()
                _validate_image(data)
                return data, str(path.relative_to(PROJECT_ROOT))
            except Exception:
                continue
    return None


def _load_jobcard() -> tuple[bytes, str, str]:
    """Return (bytes, source description, status) using GitHub first."""
    config = _existing_config()
    repo = _parse_github_repo(config)
    token = config.get("GITHUB_TOKEN", config.get("GH_TOKEN", config.get("GITHUB_PAT", "")))

    if repo:
        owner, repository = repo
        branch = config.get("GITHUB_BRANCH", config.get("GITHUB_REF_NAME", "")).strip()
        try:
            if not branch:
                branch = _get_default_branch(owner, repository, token)
            tree = _get_repo_tree(owner, repository, branch, token)
            path, blob_sha = _select_jobcard_path(tree)
            image_data = _get_blob_bytes(owner, repository, blob_sha, token)
            _validate_image(image_data)
            return image_data, path, "github"
        except Exception as exc:
            fallback = _load_local_fallback()
            if fallback:
                data, local_path = fallback
                return data, local_path, f"fallback:{exc}"
            raise

    fallback = _load_local_fallback()
    if fallback:
        data, local_path = fallback
        return data, local_path, "fallback:GitHub repository metadata was not found in this deployment."
    raise RuntimeError(
        "GitHub repository configuration was not found. This uploaded ZIP has no .git remote, "
        "and no existing GitHub repository metadata was available from the deployment environment or Streamlit Secrets. "
        "The project also has no local Job Card fallback image."
    )


def _build_print_html(image_data: bytes, copy_count: int) -> str:
    encoded = base64.b64encode(image_data).decode("ascii")
    mime = "image/png"
    try:
        with Image.open(io.BytesIO(image_data)) as image:
            if image.format == "JPEG":
                mime = "image/jpeg"
            elif image.format == "WEBP":
                mime = "image/webp"
    except Exception:
        pass
    # Keep the base64 payload only once even for 100 copies. The browser reuses
    # the same data URI for each page instead of receiving a huge repeated HTML.
    image_src_json = json.dumps(f"data:{mime};base64,{encoded}")
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SELVA MOTORS Job Card Print</title>
<style>
  @page {{ size: A4 portrait; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: #e5e7eb; }}
  .jobcard-page {{
    width: 210mm; height: 297mm; margin: 10px auto; padding: 0;
    background: #fff; display: flex; align-items: center; justify-content: center;
    overflow: hidden; page-break-after: always; break-after: page;
  }}
  .jobcard-page:last-child {{ page-break-after: auto; break-after: auto; }}
  .jobcard-page img {{
    display: block; width: 100%; height: 100%; object-fit: contain;
    object-position: center; image-rendering: auto;
  }}
  @media print {{
    html, body {{ width: 210mm; margin: 0 !important; padding: 0 !important; background: #fff !important; }}
    .jobcard-page {{ width: 210mm; height: 297mm; margin: 0 !important; padding: 0 !important; box-shadow: none; }}
  }}
  @media screen {{ .jobcard-page {{ box-shadow: 0 3px 18px rgba(0,0,0,.15); }} }}
</style></head>
<body><main id="pages"></main>
<script>
const imageSource = {image_src_json};
const copyCount = {int(copy_count)};
const pageContainer = document.getElementById('pages');
for (let i = 0; i < copyCount; i++) {{
  const page = document.createElement('section');
  page.className = 'jobcard-page';
  const image = document.createElement('img');
  image.alt = 'Technician Job Card';
  image.src = imageSource;
  page.appendChild(image);
  pageContainer.appendChild(page);
}}
(async function() {{
  const images = Array.from(document.images);
  try {{ await Promise.all(images.map(img => img.decode ? img.decode() : new Promise((resolve, reject) => {{ img.onload=resolve; img.onerror=reject; }}))); }}
  catch (e) {{ document.body.innerHTML = '<p style="font:16px Arial;padding:24px">Job Card image failed to load. Close this print view and try again.</p>'; return; }}
  if (document.readyState === 'complete') {{ setTimeout(() => window.print(), 350); }}
  else {{ window.addEventListener('load', () => setTimeout(() => window.print(), 350), {{ once: true }}); }}
}})();
</script></body></html>'''



def show_jobcard_print() -> None:
    """Render the independent Job Card preview and print workflow."""
    st.markdown(
        """
        <style>
        .jobcard-title {font-size:28px;font-weight:900;color:#111827;margin:0 0 4px 0;}
        .jobcard-subtitle {color:#64748b;font-size:13px;margin-bottom:18px;}
        div.stButton > button[kind="primary"] {background:#dc2626;color:#fff;border:0;font-weight:800;min-height:48px;}
        div.stButton > button[kind="primary"]:hover {background:#b91c1c;color:#fff;border:0;}
        </style>
        <div class="jobcard-title">SELVA MOTORS — JOBCARD</div>
        <div class="jobcard-subtitle">Technician Job Card preview and A4 printing</div>
        """,
        unsafe_allow_html=True,
    )

    if "jobcard_print_copy_count" not in st.session_state:
        st.session_state.jobcard_print_copy_count = 1

    try:
        with st.spinner("Loading Technician Job Card..."):
            image_data, source_name, source_status = _load_jobcard()
            image_size = _validate_image(image_data)
    except Exception as exc:
        st.error("Technician Job Card image could not be loaded.")
        st.warning(str(exc))
        if st.button("RETRY IMAGE LOAD", key="jobcard_retry"):
            _get_repo_tree.clear()
            _get_blob_bytes.clear()
            _get_default_branch.clear()
            st.rerun()
        return

    if source_status == "github":
        st.success("Latest matching Technician Job Card image loaded from the connected GitHub repository.")
    else:
        reason = source_status.removeprefix("fallback:")
        st.warning(
            "GitHub image could not be confirmed in this deployment. Showing the Job Card image already "
            f"included in the project instead. This fallback may not reflect a newer GitHub upload. Detail: {reason}"
        )

    st.markdown("**JOB CARD PREVIEW**")
    st.image(image_data, use_container_width=True)
    st.caption(f"Original image dimensions: {image_size[0]} × {image_size[1]} px")

    st.divider()
    col_input, col_action = st.columns([1, 1.5], vertical_alignment="bottom")
    with col_input:
        st.markdown("**NUMBER OF COPIES**")
        copies = st.number_input(
            "NUMBER OF COPIES", min_value=1, max_value=100, step=1,
            value=int(st.session_state.jobcard_print_copy_count),
            key="jobcard_copy_input", label_visibility="collapsed",
        )
        st.session_state.jobcard_print_copy_count = int(copies)
    with col_action:
        print_clicked = st.button(
            "PRINT JOBCARD", type="primary", use_container_width=True,
            key="jobcard_print_button",
        )

    if print_clicked:
        copy_count = int(st.session_state.jobcard_print_copy_count)
        if not 1 <= copy_count <= 100:
            st.error("Number of copies must be between 1 and 100.")
            return
        # Revalidate the bytes before generating the print document.
        _validate_image(image_data)
        html_doc = _build_print_html(image_data, copy_count)
        st.info(f"Preparing {copy_count} A4 Job Card page(s). Your browser print dialog will open.")
        components.html(html_doc, height=620, scrolling=True)

    if st.button("REFRESH GITHUB IMAGE", key="jobcard_refresh"):
        _get_repo_tree.clear()
        _get_blob_bytes.clear()
        _get_default_branch.clear()
        st.rerun()
