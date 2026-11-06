"""SELVA MOTORS official letter pad.

A date-only A4 print page protected by an application-generated, six-digit OTP.
The OTP is generated and verified by this app; MSG91 is used only to transport the
SMS. No PDF is generated, stored, offered, or exposed by this module.

Production note: this transaction store is SQLite on the app host. Deploy a single
Streamlit process/replica, or replace the store with a shared transactional database
before running multiple replicas.
"""

from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components


# Fixed destination requested for this module. Keep the number in international
# format for MSG91; it is not a credential.
OTP_DESTINATION = "919842538709"
OTP_DESTINATION_MASKED = "+91 ******8709"
OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
INDIA_TZ = ZoneInfo("Asia/Kolkata")
MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow"
LETTERHEAD_PATH = Path(__file__).resolve().parent / "assets" / "selva_letterpad_bg.jpg"


def _today_india() -> date:
    return datetime.now(INDIA_TZ).date()


def _get_config() -> dict[str, Any]:
    """Read secrets only from Streamlit Secrets; never from source-code constants."""
    try:
        section = st.secrets.get("letter_pad", {})
        return dict(section) if section else {}
    except Exception:
        return {}


def _database_path(config: dict[str, Any] | None = None) -> Path:
    """Resolve the private SQLite path; credentials are never stored in this DB."""
    config = config or {}
    configured = str(config.get("database_path", "") or os.environ.get("SELVA_LETTER_PAD_DB_PATH", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".selva_motors" / "letter_pad_otp.sqlite3").resolve()


def _connect_db(config: dict[str, Any] | None = None) -> sqlite3.Connection:
    path = _database_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS letter_pad_otp (
            transaction_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            destination TEXT NOT NULL,
            letter_date TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            resend_after INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            verified_at INTEGER,
            consumed_at INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_letter_pad_destination_time "
        "ON letter_pad_otp(destination, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_letter_pad_session "
        "ON letter_pad_otp(session_id, created_at DESC)"
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return conn


def _db(config: dict[str, Any] | None = None):
    """Always close a SQLite connection after use."""
    return closing(_connect_db(config))


def _require_security_config(config: dict[str, Any]) -> tuple[str, str, str]:
    auth_key = str(config.get("msg91_auth_key", "") or "").strip()
    template_id = str(config.get("msg91_template_id", "") or "").strip()
    pepper = str(config.get("otp_hmac_secret", "") or "")
    if not auth_key or not template_id or len(pepper.encode("utf-8")) < 32:
        raise RuntimeError("Letter Pad OTP configuration is incomplete.")
    return auth_key, template_id, pepper


def _otp_digest(transaction_id: str, otp: str, pepper: str) -> str:
    message = f"{transaction_id}:{otp}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _send_sms_msg91(otp: str, auth_key: str, template_id: str) -> None:
    """Send an app-generated OTP using MSG91's SMS Flow API (transport only)."""
    payload = {
        "template_id": template_id,
        "recipients": [
            {
                "mobiles": OTP_DESTINATION,
                "VAR1": otp,
            }
        ],
    }
    request = Request(
        MSG91_FLOW_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authkey": auth_key,
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read(8192)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Do not surface provider response text or request data; neither may contain
        # credentials/OTP in user-visible output.
        raise RuntimeError("SMS delivery request failed.") from exc

    if status_code < 200 or status_code >= 300:
        raise RuntimeError("SMS gateway rejected the delivery request.")
    try:
        result = json.loads(response_body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("SMS gateway returned an unreadable response.")
    if not isinstance(result, dict):
        raise RuntimeError("SMS gateway returned an unexpected response.")
    response_type = str(result.get("type", "")).strip().lower()
    response_status = str(result.get("status", "")).strip().lower()
    if response_type and response_type != "success":
        raise RuntimeError("SMS gateway did not accept the message.")
    if response_status and response_status not in {"success", "queued", "accepted"}:
        raise RuntimeError("SMS gateway did not accept the message.")
    if result.get("success") is False or not (response_type == "success" or response_status in {"success", "queued", "accepted"}):
        raise RuntimeError("SMS gateway did not confirm message acceptance.")


def _create_otp_transaction(
    session_id: str,
    letter_date: date,
    otp: str,
    pepper: str,
    config: dict[str, Any],
) -> tuple[str | None, int]:
    """Create a pending OTP atomically, invalidating any prior destination OTP."""
    now = int(time.time())
    transaction_id = uuid.uuid4().hex
    digest = _otp_digest(transaction_id, otp, pepper)

    with _db(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """UPDATE letter_pad_otp SET status='expired'
                   WHERE destination=? AND status IN ('pending','active','authorized')
                     AND expires_at <= ?""",
                (OTP_DESTINATION, now),
            )
            latest = conn.execute(
                "SELECT created_at FROM letter_pad_otp WHERE destination=? "
                "ORDER BY created_at DESC LIMIT 1",
                (OTP_DESTINATION,),
            ).fetchone()
            if latest:
                available_at = int(latest["created_at"]) + OTP_RESEND_COOLDOWN_SECONDS
                if now < available_at:
                    conn.execute("ROLLBACK")
                    return None, available_at - now

            # Only one current OTP for the fixed destination is valid. The DB lock
            # makes concurrent requests serialize before a new OTP is created.
            conn.execute(
                """UPDATE letter_pad_otp SET status='invalidated'
                   WHERE destination=? AND status IN ('pending','active','authorized')""",
                (OTP_DESTINATION,),
            )
            conn.execute(
                """INSERT INTO letter_pad_otp
                   (transaction_id, session_id, destination, letter_date, otp_hash,
                    created_at, expires_at, resend_after, attempts, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending')""",
                (
                    transaction_id,
                    session_id,
                    OTP_DESTINATION,
                    letter_date.isoformat(),
                    digest,
                    now,
                    now + OTP_TTL_SECONDS,
                    now + OTP_RESEND_COOLDOWN_SECONDS,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return transaction_id, 0


def _set_sms_result(transaction_id: str, sent: bool, config: dict[str, Any]) -> None:
    with _db(config) as conn:
        conn.execute(
            "UPDATE letter_pad_otp SET status=? WHERE transaction_id=? AND status='pending'",
            ("active" if sent else "send_failed", transaction_id),
        )


def _get_transaction(transaction_id: str, session_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    now = int(time.time())
    with _db(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM letter_pad_otp WHERE transaction_id=? AND session_id=?",
            (transaction_id, session_id),
        ).fetchone()
        if row:
            status = str(row["status"])
            otp_expired = status in ("pending", "active") and now >= int(row["expires_at"])
            authorization_expired = (
                status == "authorized"
                and row["verified_at"] is not None
                and now >= int(row["verified_at"]) + OTP_TTL_SECONDS
            )
            if otp_expired or authorization_expired:
                conn.execute(
                    "UPDATE letter_pad_otp SET status='expired' WHERE transaction_id=?",
                    (transaction_id,),
                )
                row = conn.execute(
                    "SELECT * FROM letter_pad_otp WHERE transaction_id=? AND session_id=?",
                    (transaction_id, session_id),
                ).fetchone()
        conn.execute("COMMIT")
    return dict(row) if row else None


def _invalidate_transaction(transaction_id: str, session_id: str, config: dict[str, Any]) -> None:
    with _db(config) as conn:
        conn.execute(
            """UPDATE letter_pad_otp SET status='invalidated'
               WHERE transaction_id=? AND session_id=?
                 AND status IN ('pending','active','authorized')""",
            (transaction_id, session_id),
        )


def _verify_otp(
    transaction_id: str,
    session_id: str,
    supplied_otp: str,
    pepper: str,
    config: dict[str, Any],
) -> tuple[str, int]:
    """Verify once using a serialized transaction; never trust client state."""
    now = int(time.time())
    clean_otp = supplied_otp.strip()
    with _db(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM letter_pad_otp WHERE transaction_id=? AND session_id=?",
                (transaction_id, session_id),
            ).fetchone()
            if not row:
                conn.execute("COMMIT")
                return "invalidated", 0
            status = str(row["status"])
            if status != "active":
                conn.execute("COMMIT")
                return status, max(0, OTP_MAX_ATTEMPTS - int(row["attempts"]))
            if now >= int(row["expires_at"]):
                conn.execute(
                    "UPDATE letter_pad_otp SET status='expired' WHERE transaction_id=? AND status='active'",
                    (transaction_id,),
                )
                conn.execute("COMMIT")
                return "expired", 0

            attempts = int(row["attempts"])
            if attempts >= OTP_MAX_ATTEMPTS:
                conn.execute(
                    "UPDATE letter_pad_otp SET status='locked' WHERE transaction_id=?",
                    (transaction_id,),
                )
                conn.execute("COMMIT")
                return "locked", 0

            expected = str(row["otp_hash"])
            actual = _otp_digest(transaction_id, clean_otp, pepper) if clean_otp.isdigit() and len(clean_otp) == OTP_LENGTH else "0" * 64
            if hmac.compare_digest(expected, actual):
                updated = conn.execute(
                    """UPDATE letter_pad_otp SET status='authorized', verified_at=?
                       WHERE transaction_id=? AND session_id=? AND status='active'""",
                    (now, transaction_id, session_id),
                )
                conn.execute("COMMIT")
                return ("authorized", OTP_MAX_ATTEMPTS - attempts) if updated.rowcount == 1 else ("used", 0)

            attempts += 1
            next_status = "locked" if attempts >= OTP_MAX_ATTEMPTS else "active"
            conn.execute(
                "UPDATE letter_pad_otp SET attempts=?, status=? WHERE transaction_id=? AND status='active'",
                (attempts, next_status, transaction_id),
            )
            conn.execute("COMMIT")
            return next_status if next_status == "locked" else "incorrect", OTP_MAX_ATTEMPTS - attempts
        except Exception:
            conn.execute("ROLLBACK")
            raise


def _consume_print_authorization(
    transaction_id: str,
    session_id: str,
    letter_date: date,
    config: dict[str, Any],
) -> bool:
    """Atomically consume the authorization before a single browser print call."""
    now = int(time.time())
    with _db(config) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM letter_pad_otp WHERE transaction_id=? AND session_id=?",
                (transaction_id, session_id),
            ).fetchone()
            if not row or row["status"] != "authorized":
                conn.execute("COMMIT")
                return False
            verified_at = int(row["verified_at"] or 0)
            authorization_expired = not verified_at or now >= verified_at + OTP_TTL_SECONDS
            if authorization_expired or str(row["letter_date"]) != letter_date.isoformat():
                conn.execute(
                    "UPDATE letter_pad_otp SET status='expired' WHERE transaction_id=? AND status='authorized'",
                    (transaction_id,),
                )
                conn.execute("COMMIT")
                return False
            updated = conn.execute(
                """UPDATE letter_pad_otp SET status='consumed', consumed_at=?
                   WHERE transaction_id=? AND session_id=? AND status='authorized'""",
                (now, transaction_id, session_id),
            )
            conn.execute("COMMIT")
            return updated.rowcount == 1
        except Exception:
            conn.execute("ROLLBACK")
            raise


def _image_data_uri() -> str:
    if not LETTERHEAD_PATH.is_file():
        raise FileNotFoundError("The official letterhead image is missing from assets.")
    encoded = base64.b64encode(LETTERHEAD_PATH.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _build_print_document(letter_date: date, image_uri: str) -> str:
    """Create an A4-only HTML print document with the original image undistorted."""
    safe_date = letter_date.strftime("%d-%m-%Y")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SELVA MOTORS Letter Pad</title>
<style>
  @page {{ size: A4 portrait; margin: 0; }}
  * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
  html, body {{ margin: 0; padding: 0; width: 210mm; height: 297mm; overflow: hidden; background: #fff; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #111; }}
  .sheet {{ position: relative; width: 210mm; height: 297mm; overflow: hidden; page-break-after: avoid; break-after: avoid-page; background: #fff; }}
  .letterhead {{ position: absolute; inset: 0; display: block; width: 210mm; height: 297mm; object-fit: contain; object-position: center center; }}
  .letter-date {{ position: absolute; top: 48mm; right: 20mm; z-index: 2; font-size: 11pt; line-height: 1.2; font-weight: 600; color: #111; white-space: nowrap; }}
  @media print {{
    html, body, .sheet {{ width: 210mm !important; height: 297mm !important; margin: 0 !important; padding: 0 !important; }}
    .sheet {{ page-break-after: avoid !important; break-after: avoid-page !important; }}
  }}
</style>
</head>
<body>
  <main class="sheet" aria-label="SELVA MOTORS official letter pad">
    <img class="letterhead" src="{image_uri}" alt="Official SELVA MOTORS and Hero letterhead">
    <div class="letter-date">Date: {safe_date}</div>
  </main>
</body>
</html>"""


def _print_launcher_html(print_document: str, transaction_id: str) -> str:
    """A hidden, one-shot iframe invokes the native print dialog; no file URL exists."""
    document_b64 = base64.b64encode(print_document.encode("utf-8")).decode("ascii")
    # transaction_id is a server-generated hex UUID and therefore safe in this script.
    return f"""<!doctype html><html><body><script>
(function () {{
  const launchKey = "selvaLetterPadPrint_{transaction_id}";
  if (window[launchKey]) return;
  window[launchKey] = true;
  const frame = document.createElement("iframe");
  frame.setAttribute("aria-hidden", "true");
  frame.style.position = "fixed";
  frame.style.left = "-10000px";
  frame.style.top = "0";
  frame.style.width = "210mm";
  frame.style.height = "297mm";
  frame.style.border = "0";
  frame.style.opacity = "0";
  let printStarted = false;
  const doPrint = function () {{
    if (printStarted || !frame.isConnected) return;
    printStarted = true;
    setTimeout(function () {{
      try {{
        frame.contentWindow.focus();
        frame.contentWindow.print();
      }} finally {{
        setTimeout(function () {{ frame.remove(); }}, 1500);
      }}
    }}, 250);
  }};
  frame.addEventListener("load", doPrint, {{ once: true }});
  frame.srcdoc = atob("{document_b64}");
  document.body.appendChild(frame);
  // Fallback for browsers that do not dispatch the expected load event.
  setTimeout(doPrint, 1600);
}})();
</script></body></html>"""


def _request_new_otp(letter_date: date, session_id: str, config: dict[str, Any]) -> tuple[bool, int, str | None]:
    """Generate, persist, and send one fresh OTP. The clear OTP is never persisted."""
    auth_key, template_id, pepper = _require_security_config(config)
    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    transaction_id, wait_seconds = _create_otp_transaction(session_id, letter_date, otp, pepper, config)
    if not transaction_id:
        return False, wait_seconds, None
    try:
        _send_sms_msg91(otp, auth_key, template_id)
    except Exception:
        _set_sms_result(transaction_id, sent=False, config=config)
        return False, 0, transaction_id
    _set_sms_result(transaction_id, sent=True, config=config)
    return True, 0, transaction_id


def render_letter_pad_page() -> None:
    """Render the manager-only LETTER PAD page, isolated from other app modules."""
    st.title("SELVA MOTORS – LETTER PAD")
    st.caption("Official letterhead • A4 portrait • One-time OTP-authorized printing")
    flash_notice = st.session_state.pop("lp_notice", None)
    if flash_notice:
        level, message = flash_notice
        getattr(st, level, st.info)(message)

    config = _get_config()
    try:
        # Initialize/validate the local transactional store without touching Sheets.
        with _db(config):
            pass
    except Exception:
        st.error("The Letter Pad security store is unavailable. Contact the app administrator.")
        return

    if not LETTERHEAD_PATH.is_file():
        st.error("The official letterhead image is missing. Restore assets/selva_letterpad_bg.jpg.")
        return

    if "lp_session_id" not in st.session_state:
        st.session_state["lp_session_id"] = secrets.token_urlsafe(32)
    session_id = str(st.session_state["lp_session_id"])

    selected_date = st.date_input(
        "Letter Date",
        value=st.session_state.get("lp_letter_date", _today_india()),
        key="lp_letter_date",
    )
    if isinstance(selected_date, datetime):
        selected_date = selected_date.date()

    transaction_id = st.session_state.get("lp_transaction_id")
    transaction: dict[str, Any] | None = None
    if transaction_id:
        try:
            transaction = _get_transaction(str(transaction_id), session_id, config)
        except Exception:
            st.error("Unable to check the OTP transaction. Contact the app administrator.")
            return

        if transaction and transaction["letter_date"] != selected_date.isoformat() and transaction["status"] in {
            "pending", "active", "authorized"
        }:
            _invalidate_transaction(str(transaction_id), session_id, config)
            transaction = _get_transaction(str(transaction_id), session_id, config)
            st.session_state.pop("lp_transaction_id", None)
            st.info("The letter date changed. Request a new OTP for the selected date.")
            transaction = None

    status = str(transaction["status"]) if transaction else "none"
    cooldown_left = max(0, int(transaction["resend_after"]) - int(time.time())) if transaction else 0

    if status in {"none", "consumed", "expired", "locked", "invalidated", "send_failed"}:
        if status == "consumed":
            st.success("The one-time print authorization has been consumed. It cannot be reused.")
            st.button("PRINT LETTER", disabled=True, use_container_width=True, key=f"lp_consumed_{transaction_id}")
        elif status == "expired":
            st.warning("The OTP has expired. Request a new OTP to print.")
        elif status == "locked":
            st.error("Five incorrect verification attempts were made. This OTP is locked.")
        elif status == "send_failed":
            st.error("The SMS gateway did not accept the OTP. Check the gateway setup and request a new OTP after the cooldown.")
        elif status == "invalidated":
            st.info("The previous OTP is no longer valid. Request a new OTP.")

        button_label = "PRINT LETTER" if status == "none" else "REQUEST NEW OTP"
        if st.button(button_label, type="primary", use_container_width=True, key="lp_request_otp"):
            try:
                sent, wait_seconds, new_transaction_id = _request_new_otp(selected_date, session_id, config)
                if sent and new_transaction_id:
                    st.session_state["lp_transaction_id"] = new_transaction_id
                    st.success(f"OTP sent to {OTP_DESTINATION_MASKED}. It expires in 5 minutes.")
                    st.rerun()
                elif wait_seconds:
                    st.warning(f"Please wait {wait_seconds} seconds before requesting or resending another OTP.")
                else:
                    st.error("Unable to send OTP. Check the Streamlit Secrets and SMS gateway configuration.")
                    if new_transaction_id:
                        st.session_state["lp_transaction_id"] = new_transaction_id
            except RuntimeError:
                st.error("Letter Pad OTP is not configured. Contact the app administrator.")
            except Exception:
                st.error("The OTP request could not be completed. Contact the app administrator.")
        return

    if status == "pending":
        st.info("The SMS request is being processed. Refresh this page to check its status.")
        return

    if status == "active":
        remaining = max(0, int(transaction["expires_at"]) - int(time.time()))
        st.info(f"OTP sent to {OTP_DESTINATION_MASKED}. It expires in about {remaining // 60}:{remaining % 60:02d}.")
        otp_widget_key = f"lp_otp_input_{transaction_id}"
        with st.form(f"lp_verify_otp_form_{transaction_id}", clear_on_submit=True):
            supplied_otp = st.text_input(
                "Enter 6-digit OTP",
                type="password",
                max_chars=OTP_LENGTH,
                placeholder="6-digit OTP",
                key=otp_widget_key,
            )
            verify_clicked = st.form_submit_button("VERIFY OTP", type="primary", use_container_width=True)

        if verify_clicked:
            try:
                _, _, pepper = _require_security_config(config)
                result, attempts_left = _verify_otp(
                    str(transaction_id), session_id, supplied_otp, pepper, config
                )
                if result == "authorized":
                    st.success("OTP verified. One print operation is now authorized.")
                    st.rerun()
                elif result == "incorrect":
                    st.error(f"Incorrect OTP. {attempts_left} verification attempt(s) remaining.")
                elif result == "locked":
                    st.session_state["lp_notice"] = ("error", "Maximum verification attempts reached. This OTP is locked.")
                    st.rerun()
                elif result == "expired":
                    st.session_state["lp_notice"] = ("warning", "OTP expired. Request a new OTP.")
                    st.rerun()
                else:
                    st.session_state["lp_notice"] = ("error", "This OTP is no longer valid. Request a new OTP.")
                    st.rerun()
            except Exception:
                st.error("OTP verification could not be completed. Contact the app administrator.")
        if cooldown_left:
            st.caption(f"Resend available in {cooldown_left} seconds.")
        elif st.button("RESEND OTP", use_container_width=True, key="lp_resend_otp"):
            try:
                sent, wait_seconds, new_transaction_id = _request_new_otp(selected_date, session_id, config)
                if sent and new_transaction_id:
                    st.session_state["lp_transaction_id"] = new_transaction_id
                    st.success(f"A new OTP was sent to {OTP_DESTINATION_MASKED}. The previous OTP is invalid.")
                    st.rerun()
                elif wait_seconds:
                    st.warning(f"Please wait {wait_seconds} seconds before resending.")
                else:
                    st.error("Unable to resend OTP. Check the SMS gateway configuration.")
            except Exception:
                st.error("The resend request could not be completed. Contact the app administrator.")
        return

    if status == "authorized":
        st.success("OTP verified. Click PRINT LETTER to use this authorization once.")
        st.caption("The one-time print authorization remains valid for 5 minutes after verification.")
        if st.button("PRINT LETTER", type="primary", use_container_width=True, key=f"lp_print_{transaction_id}"):
            try:
                consumed = _consume_print_authorization(
                    str(transaction_id), session_id, selected_date, config
                )
                if not consumed:
                    st.error("This print authorization is expired, invalid, or already used.")
                    st.rerun()
                else:
                    image_uri = _image_data_uri()
                    document = _build_print_document(selected_date, image_uri)
                    launcher = _print_launcher_html(document, str(transaction_id))
                    components.html(
                        launcher,
                        height=1,
                        width=1,
                        scrolling=False,
                    )
                    st.success("The one-time print action was dispatched. This OTP cannot be reused.")
                    st.button("PRINT LETTER", disabled=True, use_container_width=True, key=f"lp_print_disabled_{transaction_id}")
            except Exception:
                # The authorization has already been consumed if document rendering
                # failed. This deliberate fail-closed behavior prevents replays.
                st.error("The print action could not be opened. The OTP has been consumed; request a new OTP to try again.")
        return


def main() -> None:
    """Optional standalone entry point for testing this module directly."""
    render_letter_pad_page()


if __name__ == "__main__":
    main()
