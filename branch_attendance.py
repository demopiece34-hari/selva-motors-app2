"""Pure validation helpers for SELVA MOTORS multi-branch attendance."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

BRANCHES = ("Kilvelur", "Thirukkuvalai")
_BRANCH_LOOKUP = {name.casefold(): name for name in BRANCHES}


def normalize_branch(value: Any) -> Optional[str]:
    """Return a canonical branch name only for an exact allowed value."""
    return _BRANCH_LOOKUP.get(str(value or "").strip().casefold())


def validate_gps_config(latitude: Any, longitude: Any, radius: Any) -> tuple[Optional[dict[str, float]], str]:
    """Validate coordinate/radius values without inventing defaults."""
    try:
        lat = float(str(latitude).strip())
        lon = float(str(longitude).strip())
        allowed_radius = float(str(radius).strip())
    except (TypeError, ValueError):
        return None, "Latitude, Longitude and Allowed Radius are all required numeric values."
    if not (-90.0 <= lat <= 90.0):
        return None, "Latitude must be between -90 and 90."
    if not (-180.0 <= lon <= 180.0):
        return None, "Longitude must be between -180 and 180."
    if not (1.0 <= allowed_radius <= 100000.0):
        return None, "Allowed Radius must be between 1 and 100000 metres."
    return {"latitude": lat, "longitude": lon, "allowed_radius": allowed_radius}, ""


def resolve_gps_config(
    branch_value: Any,
    settings: Mapping[str, Mapping[str, Any]],
    legacy_kilvelur: Mapping[str, Any],
) -> tuple[Optional[dict[str, Any]], str]:
    """Resolve only the employee's assigned branch; legacy GPS applies only to Kilvelur."""
    branch = normalize_branch(branch_value)
    if not branch:
        return None, "Your employee Location is missing or invalid. Contact Admin to assign Kilvelur or Thirukkuvalai."

    record = settings.get(branch)
    if record is None:
        if branch == "Kilvelur":
            # Backward-compatible fallback to the exact existing app constants.
            cfg, error = validate_gps_config(
                legacy_kilvelur.get("latitude"),
                legacy_kilvelur.get("longitude"),
                legacy_kilvelur.get("allowed_radius"),
            )
            if cfg:
                return {"branch": branch, **cfg, "source": "legacy_code"}, ""
            return None, "Existing Kilvelur GPS values are invalid; Admin configuration is required."
        return None, "Your branch GPS settings are not configured. Contact Admin."

    cfg, error = validate_gps_config(
        record.get("Latitude"), record.get("Longitude"), record.get("Allowed Radius")
    )
    if not cfg:
        return None, f"{branch} GPS settings are incomplete or invalid. Contact Admin. {error}"
    return {"branch": branch, **cfg, "source": "google_sheets"}, ""


_ATTENDANCE_TIMEZONE = ZoneInfo("Asia/Kolkata")

def attendance_date_time_fields(now: Optional[datetime] = None) -> dict[str, str]:
    """Build attendance Date/Time values from one instant in India Standard Time.

    The returned mapping uses the existing worksheet headers exactly. Date and
    Time remain strings in the same formats used by the existing attendance
    workflow; no worksheet columns or storage schema are changed.
    """
    current = now or datetime.now(_ATTENDANCE_TIMEZONE)
    if current.tzinfo is None:
        # A naive value supplied by an existing caller is treated as local IST.
        current = current.replace(tzinfo=_ATTENDANCE_TIMEZONE)
    else:
        current = current.astimezone(_ATTENDANCE_TIMEZONE)
    return {
        "Date": current.strftime("%d-%m-%Y"),
        "Time": current.strftime("%I:%M:%S %p"),
    }
