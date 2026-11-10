"""Employee profile, RBAC, access control and payroll helpers/UI for Selva Motors.

All persistence is delegated to the existing Google Sheets gateway. This module
never creates a second employee/login store and never exposes sheet contents to
client-side HTML. Mutations are append-only snapshots wherever practical.
"""
from __future__ import annotations

import base64
import json
import math
import re
import uuid
from datetime import date, datetime
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

ROLES = [
    "Super Admin", "Admin", "Manager", "Accountant", "Service Manager",
    "Service Advisor", "Technician", "Sales Executive", "Receptionist", "Custom Role",
]
PERMISSIONS = {
    "dashboard": "Dashboard", "customer_details": "Customer Details",
    "vehicle_details": "Vehicle Details", "service_records": "Service Records",
    "extra_fittings": "Extra Fittings Invoice", "letter_pad": "Letter Pad",
    "ocr_scanner": "OCR Scanner", "stock_management": "Stock Management",
    "sales_records": "Sales Records", "salary_management": "Salary Management",
    "employee_profiles": "Employee Profiles", "reports": "Reports",
    "settings": "Settings", "attendance": "Attendance",
    "upload_invoice": "Upload Invoice", "manual_invoice": "Manual Invoice",
    "delete_invoice_request": "Delete Invoice Request",
    "employee_access_management": "Employee Access Management",
    "photo_upload": "Profile Photo Upload", "photo_view_all": "View Other Employee Photos",
}
DEFAULT_ROLE_PERMISSIONS = {
    "Super Admin": list(PERMISSIONS), "Admin": list(PERMISSIONS),
    "Manager": ["dashboard", "customer_details", "vehicle_details", "service_records", "extra_fittings", "letter_pad", "stock_management", "sales_records", "employee_profiles", "reports", "attendance", "manual_invoice"],
    "Accountant": ["dashboard", "sales_records", "salary_management", "reports", "employee_profiles"],
    "Service Manager": ["dashboard", "customer_details", "vehicle_details", "service_records", "extra_fittings", "stock_management", "reports", "attendance", "employee_profiles"],
    "Service Advisor": ["dashboard", "customer_details", "vehicle_details", "service_records", "extra_fittings", "attendance", "upload_invoice", "employee_profiles"],
    "Technician": ["attendance", "upload_invoice", "reports", "manual_invoice", "delete_invoice_request", "employee_profiles"],
    "Sales Executive": ["dashboard", "customer_details", "vehicle_details", "sales_records", "manual_invoice", "employee_profiles"],
    "Receptionist": ["dashboard", "customer_details", "vehicle_details", "attendance", "employee_profiles"],
    "Custom Role": [],
    "Prathisha / System Staff": ["dashboard", "reports", "extra_fittings", "attendance", "employee_profiles"],
}

PROFILE_COLUMNS = ["User ID", "Designation", "Department", "Mobile Number", "Joining Date", "Photo Data", "Photo MIME", "Photo View Policy", "Photo Upload Allowed", "Updated By", "Updated At"]
ROLE_COLUMNS = ["Role Name", "Permissions JSON", "Enabled", "Updated By", "Updated At"]
EMP_PERMISSION_COLUMNS = ["User ID", "Permission", "Allowed", "Updated By", "Updated At"]
SALARY_COLUMNS = ["Record ID", "User ID", "Employee Name", "Salary Month", "Monthly Salary", "Calculation Days", "Working Days", "Present Days", "Leave Days", "Payable Days", "Per Day Salary", "Earned Salary", "Overtime Amount", "Incentives", "Advance Amount", "Deductions", "Bonus", "Final Salary", "Payment Status", "Payment Date", "Admin Remarks", "Policy Version", "Created At", "Created By"]
SALARY_HISTORY_COLUMNS = SALARY_COLUMNS + ["Revision Type", "Revision Date"]
ACCESS_LOG_COLUMNS = ["Log ID", "Timestamp", "Actor User ID", "Target User ID", "Action", "Details"]
POLICY_COLUMNS = ["Policy Version", "Policy Name", "Calculation Days", "Payable Day Policy", "Updated By", "Updated At"]


def _apply_employee_theme() -> None:
    st.markdown("""
    <style>
      .employee-module-title { color:#d71920; font-weight:900; letter-spacing:.4px; }
      [data-testid="stMetric"] { background:#fff; border:1px solid #e5e5e5; border-left:4px solid #d71920; border-radius:12px; padding:12px 14px; }
      [data-testid="stTabs"] button[aria-selected="true"] { color:#d71920 !important; border-bottom-color:#d71920 !important; }
      [data-testid="stForm"] { border:1px solid #e4e4e7; border-radius:14px; padding:14px; background:#fff; }
      .employee-dark-card { background:#111827; color:#fff; border-radius:16px; padding:16px; border-top:4px solid #d71920; }
      .employee-dark-card small { color:#d1d5db; }
    </style>
    """, unsafe_allow_html=True)


def _money(value: Any) -> float:
    try:
        n = float(str(value or "0").replace(",", "").replace("₹", "").strip())
        if not math.isfinite(n) or n < 0:
            raise ValueError
        return round(n, 2)
    except Exception as exc:
        raise ValueError("Enter a valid non-negative amount.") from exc


def calculate_salary(monthly_salary: Any, calculation_days: Any, payable_days: Any,
                     overtime: Any = 0, incentives: Any = 0, bonus: Any = 0,
                     advance: Any = 0, deductions: Any = 0) -> dict[str, float]:
    monthly = _money(monthly_salary)
    days = int(calculation_days)
    payable = float(payable_days)
    if days <= 0 or days > 31 or payable < 0 or payable > days:
        raise ValueError("Calculation days must be 1–31 and payable days must be within that range.")
    per_day = round(monthly / days, 2)
    earned = round(per_day * payable, 2)
    overtime_v, incentives_v, bonus_v = _money(overtime), _money(incentives), _money(bonus)
    advance_v, deductions_v = _money(advance), _money(deductions)
    final = round(earned + overtime_v + incentives_v + bonus_v - advance_v - deductions_v, 2)
    if final < 0:
        raise ValueError("Deductions and advance cannot make final salary negative.")
    return {"Per Day Salary": per_day, "Earned Salary": earned,
            "Final Salary": final, "Overtime Amount": overtime_v,
            "Incentives": incentives_v, "Bonus": bonus_v,
            "Advance Amount": advance_v, "Deductions": deductions_v}


def _latest_rows(df: pd.DataFrame, key: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if df is None or df.empty or key not in df.columns:
        return result
    for _, row in df.iterrows():
        k = str(row.get(key, "")).strip()
        if k:
            result[k] = row.to_dict()
    return result


def load_access_context(read_sheet: Callable, user_id: str, role: str) -> dict[str, Any]:
    """Load the latest role and per-user permission snapshots after login."""
    if role in {"Admin", "Super Admin"}:
        return {"permissions": list(PERMISSIONS), "role": role, "is_admin": True}
    try:
        roles_df = read_sheet("employee_roles", purpose="access_config")
        role_rows = _latest_rows(roles_df, "Role Name")
        role_row = role_rows.get(role, {})
        if role_row and str(role_row.get("Enabled", "TRUE")).upper() not in {"TRUE", "YES", "1", "ACTIVE"}:
            return {"permissions": [], "role": role, "is_admin": False, "disabled_role": True}
        try:
            base = json.loads(str(role_row.get("Permissions JSON", ""))) if role_row else DEFAULT_ROLE_PERMISSIONS.get(role, [])
        except Exception:
            base = []
        if not isinstance(base, list):
            base = []
        allowed = set(p for p in base if p in PERMISSIONS)
        overrides = read_sheet("employee_permissions", purpose="access_config")
        if not overrides.empty:
            own = overrides[overrides["User ID"].astype(str).str.casefold() == user_id.casefold()]
            latest_overrides = {}
            for _, row in own.iterrows():
                p = str(row.get("Permission", ""))
                if p in PERMISSIONS:
                    latest_overrides[p] = str(row.get("Allowed", "")).upper()
            for p, setting in latest_overrides.items():
                if setting in {"TRUE", "YES", "1", "ALLOW"}:
                    allowed.add(p)
                elif setting in {"FALSE", "NO", "0", "DENY"}:
                    allowed.discard(p)
        return {"permissions": sorted(allowed), "role": role, "is_admin": False}
    except Exception:
        # Fail closed: no elevated permissions if access configuration cannot load.
        return {"permissions": [], "role": role, "is_admin": False, "load_error": True}


def is_admin_user() -> bool:
    return str(st.session_state.get("role", "")) in {"Admin", "Super Admin"}


def has_permission(permission: str) -> bool:
    ctx = st.session_state.get("_employee_access", {})
    if ctx.get("is_admin") or st.session_state.get("role") in {"Admin", "Super Admin"}:
        return True
    return permission in set(ctx.get("permissions", []))


def require_permission(permission: str) -> bool:
    if has_permission(permission):
        return True
    st.error(f"Access denied: {PERMISSIONS.get(permission, permission)} permission is not enabled for your account.")
    return False


def _append_audit(append_row: Callable, actor: str, target: str, action: str, details: str) -> None:
    append_row("employee_access_logs", {
        "Log ID": str(uuid.uuid4()), "Timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "Actor User ID": actor, "Target User ID": target, "Action": action, "Details": details[:500],
    })


def _profile_photo(uploaded) -> tuple[str, str]:
    if uploaded is None:
        return "", ""
    raw = uploaded.getvalue()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Profile photo must be 2 MB or smaller.")
    try:
        image = Image.open(BytesIO(raw))
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Only JPG, PNG or WEBP images are accepted.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((180, 180))
        out = BytesIO()
        image.save(out, format="JPEG", quality=55, optimize=True)
        data = out.getvalue()
        if len(data) > 38_000:
            out = BytesIO()
            image.save(out, format="JPEG", quality=35, optimize=True)
            data = out.getvalue()
        if len(data) > 38_000:
            raise ValueError("Could not compress this photo below the secure 38 KB limit.")
        return base64.b64encode(data).decode("ascii"), "image/jpeg"
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc


def _show_photo(profile: dict, caption: str = "") -> None:
    encoded = str(profile.get("Photo Data", "") or "")
    if encoded:
        try:
            st.image(BytesIO(base64.b64decode(encoded, validate=True)), width=150, caption=caption or None)
            return
        except Exception:
            pass
    st.markdown("<div style='width:116px;height:116px;border-radius:50%;background:#171717;border:3px solid #d71920;display:flex;align-items:center;justify-content:center;color:white;font-size:42px;font-weight:900'>SM</div>", unsafe_allow_html=True)


def render_user_profile(read_sheet: Callable, current_user: dict, append_row: Callable | None = None) -> None:
    _apply_employee_theme()
    if not require_permission("employee_profiles"):
        return
    uid = str(current_user.get("User ID", ""))
    profiles = read_sheet("employee_profiles", purpose="self_profile")
    profile_map = _latest_rows(profiles, "User ID")
    profile = profile_map.get(uid, {})
    st.markdown("<h1 style='color:#d71920'>USER PROFILE</h1><p style='color:#777'>Your employee information and account access</p>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        _show_photo(profile, "Employee photo")
    with c2:
        st.subheader(str(current_user.get("Employee Name", "Employee")))
        st.caption(f"Employee ID: {uid}  •  Role: {current_user.get('Role', '')}")
        status = str(current_user.get("Status", "Active"))
        st.markdown(f"**Account status:** {'🟢' if status.lower() == 'active' else '🔴'} {status}")
    details = [
        ("Designation", profile.get("Designation", "—")), ("Department", profile.get("Department", "—")),
        ("Mobile Number", profile.get("Mobile Number", "—")), ("Joining Date", profile.get("Joining Date", "—")),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, details):
        with col:
            st.metric(label, str(value or "—"))
    access = st.session_state.get("_employee_access", {})
    st.subheader("My Access Permissions")
    names = [PERMISSIONS[p] for p in access.get("permissions", []) if p in PERMISSIONS]
    st.write(" • ".join(names) if names else "No additional page permissions are enabled.")
    if has_permission("photo_upload"):
        with st.expander("Update My Profile Photo"):
            own_upload = st.file_uploader("Choose a new photo (JPG / PNG / WEBP)", type=["jpg", "jpeg", "png", "webp"], key="own_profile_photo")
            if st.button("SAVE MY PHOTO"):
                try:
                    if own_upload is None:
                        raise ValueError("Choose a photo before saving.")
                    data, mime = _profile_photo(own_upload)
                    if append_row:
                        append_row("employee_profiles", {**{k: profile.get(k, "") for k in PROFILE_COLUMNS}, "User ID": uid, "Photo Data": data, "Photo MIME": mime, "Updated By": uid, "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                        st.success("Your profile photo has been updated.")
                    else:
                        st.error("Photo update is not available in this session. Contact Admin.")
                except Exception as exc:
                    st.error(str(exc))
    if has_permission("photo_view_all"):
        st.subheader("Authorized Team Photos")
        for _, team_row in profiles.iterrows():
            team_id = str(team_row.get("User ID", ""))
            if team_id and team_id.casefold() != uid.casefold() and team_row.get("Photo Data"):
                with st.expander(f"Employee {team_id}"):
                    _show_photo(team_row.to_dict())

    st.divider()
    st.subheader("MY SALARY")
    if not has_permission("salary_management") and not uid:
        st.info("Salary details are not available.")
        return
    try:
        salary_df = read_sheet("employee_salary", purpose="self_profile")
        mine = salary_df[salary_df["User ID"].astype(str).str.casefold() == uid.casefold()] if not salary_df.empty else salary_df
        if mine.empty:
            st.info("No salary record has been published for your account yet.")
        else:
            latest = mine.iloc[-1].to_dict()
            a, b, c = st.columns(3)
            a.metric("Monthly Salary", f"₹{_money(latest.get('Monthly Salary')):,.2f}")
            b.metric("Per Day Salary", f"₹{_money(latest.get('Per Day Salary')):,.2f}")
            c.metric("Final Salary", f"₹{_money(latest.get('Final Salary')):,.2f}")
            st.caption(f"Salary month: {latest.get('Salary Month', '—')}  |  Payment: {latest.get('Payment Status', '—')}")
            salary_fields = ["Working Days", "Present Days", "Leave Days", "Incentives", "Overtime Amount", "Advance Amount", "Deductions", "Bonus", "Earned Salary"]
            st.dataframe(pd.DataFrame([{"Item": x, "Value": latest.get(x, "—")} for x in salary_fields]), hide_index=True, use_container_width=True)
            st.caption(f"Calculation: ₹{_money(latest.get('Monthly Salary')):,.2f} ÷ {latest.get('Calculation Days')} days × {latest.get('Payable Days')} payable days.")
            st.subheader("My Salary History")
            st.dataframe(mine[[c for c in ["Salary Month", "Monthly Salary", "Final Salary", "Payment Status", "Payment Date"] if c in mine.columns]], hide_index=True, use_container_width=True)
    except PermissionError:
        st.info("Salary profile access is not configured yet.")


def render_employee_access_management(read_sheet: Callable, append_row: Callable,
                                      update_sheet_range: Callable, password_hash: Callable,
                                      current_user: dict, append_rows_atomic: Callable | None = None) -> None:
    _apply_employee_theme()
    if not is_admin_user():
        st.error("Access denied: Employee Access Management is Admin-only.")
        return
    st.markdown("<h1 style='color:#d71920'>EMPLOYEE ACCESS MANAGEMENT</h1><p>Admin-controlled employee accounts, roles, photo access and permissions.</p>", unsafe_allow_html=True)
    employees = read_sheet("employees", purpose="employee_admin")
    profiles = read_sheet("employee_profiles", purpose="employee_admin")
    roles_df = read_sheet("employee_roles", purpose="employee_admin")
    perms_df = read_sheet("employee_permissions", purpose="employee_admin")
    logs = read_sheet("employee_access_logs", purpose="employee_admin")
    employee_records = employees.to_dict("records") if not employees.empty else []
    employee_options = {f"{r.get('Employee Name','')} ({r.get('User ID','')})": r for r in employee_records}
    tab_add, tab_roles, tab_access, tab_logs = st.tabs(["Employees", "Manage Roles", "Access & Photos", "Activity Log"])
    with tab_add:
        st.subheader("Add Employee")
        with st.form("employee_add_form"):
            a, b = st.columns(2)
            new_uid = a.text_input("Employee ID / User ID")
            new_name = b.text_input("Employee Name")
            new_password = a.text_input("Temporary Password", type="password")
            role_options = list(dict.fromkeys(ROLES + [str(x) for x in roles_df.get("Role Name", pd.Series(dtype=str)).tolist() if str(x)]))
            new_role = b.selectbox("Assigned Role", role_options)
            designation = a.text_input("Designation")
            department = b.text_input("Department")
            mobile = a.text_input("Mobile Number")
            joining = b.date_input("Joining Date", value=date.today())
            photo = st.file_uploader("Profile Photo (JPG / PNG / WEBP, max 2 MB)", type=["jpg", "jpeg", "png", "webp"], key="new_employee_photo")
            save = st.form_submit_button("CREATE EMPLOYEE", type="primary", use_container_width=True)
        if save:
            if not all([new_uid.strip(), new_name.strip(), new_password]):
                st.error("Employee ID, name and password are required.")
            elif any(str(x.get("User ID", "")).casefold() == new_uid.strip().casefold() for x in employee_records):
                st.error("This Employee ID already exists.")
            else:
                try:
                    photo_data, photo_mime = _profile_photo(photo)
                    employee_row = {"User ID": new_uid.strip(), "Password": password_hash(new_password), "Employee Name": new_name.strip(), "Role": new_role, "Status": "Active"}
                    profile_row = {"User ID": new_uid.strip(), "Designation": designation, "Department": department, "Mobile Number": mobile, "Joining Date": joining.isoformat(), "Photo Data": photo_data, "Photo MIME": photo_mime, "Photo View Policy": "SELF_AND_AUTHORIZED", "Photo Upload Allowed": "FALSE", "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")}
                    audit_row = {"Log ID": str(uuid.uuid4()), "Timestamp": datetime.now().astimezone().isoformat(timespec="seconds"), "Actor User ID": current_user["User ID"], "Target User ID": new_uid.strip(), "Action": "EMPLOYEE_CREATED", "Details": f"Role={new_role}; profile created"}
                    if append_rows_atomic:
                        ok = append_rows_atomic([("employees", employee_row), ("employee_profiles", profile_row), ("employee_access_logs", audit_row)])
                    else:
                        ok = append_row("employees", employee_row) and append_row("employee_profiles", profile_row)
                    if ok:
                        st.success("Employee account and profile created. Verify the employee in the register before sharing login credentials.")
                except Exception as exc:
                    st.error(str(exc))
        st.divider()
        st.subheader("Existing Employees")
        if employee_records:
            view = [{k: r.get(k, "") for k in ["User ID", "Employee Name", "Role", "Status"]} for r in employee_records]
            st.dataframe(pd.DataFrame(view), use_container_width=True, hide_index=True)
            st.caption("Creation checks the current employee register; account uniqueness still depends on this snapshot and concurrent admins should not create the same ID simultaneously.")
    with tab_roles:
        st.subheader("Create / Update Custom Role")
        role_names = list(dict.fromkeys(ROLES + [str(x) for x in roles_df.get("Role Name", pd.Series(dtype=str)).tolist() if str(x)]))
        chosen = st.selectbox("Role", role_names, key="managed_role_choice")
        role_action = st.selectbox("Role action", ["Edit permissions", "Create role", "Rename role", "Disable role"])
        new_role_name = st.text_input("New role name (for create / rename)", placeholder="e.g. Workshop Supervisor")
        save_role_name = new_role_name.strip() if role_action in {"Create role", "Rename role"} else chosen
        current = _latest_rows(roles_df, "Role Name").get(chosen, {})
        try:
            current_perms = json.loads(current.get("Permissions JSON", "[]")) if current else DEFAULT_ROLE_PERMISSIONS.get(chosen, [])
        except Exception:
            current_perms = []
        selected = st.multiselect("Permissions", list(PERMISSIONS), default=[p for p in current_perms if p in PERMISSIONS], format_func=lambda p: PERMISSIONS[p])
        enabled = st.checkbox("Role enabled", value=str(current.get("Enabled", "TRUE")).upper() not in {"FALSE", "NO", "0", "DISABLED"})
        if st.button("SAVE ROLE CHANGE", type="primary"):
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            if role_action in {"Create role", "Rename role"} and not save_role_name:
                st.error("Enter a new role name.")
            elif role_action == "Create role" and save_role_name in role_names:
                st.error("That role name already exists.")
            elif role_action == "Rename role" and chosen in {"Admin", "Super Admin"}:
                st.error("Built-in administrator roles cannot be renamed.")
            elif save_role_name in {"Super Admin", "Admin"} and not set(selected) >= set(PERMISSIONS):
                st.error("Admin roles must retain all permissions to prevent accidental lockout.")
            elif role_action == "Disable role" and chosen in {"Admin", "Super Admin"}:
                st.error("Built-in administrator roles cannot be disabled.")
            else:
                if role_action == "Rename role":
                    append_row("employee_roles", {"Role Name": chosen, "Permissions JSON": json.dumps(current_perms), "Enabled": "FALSE", "Updated By": current_user["User ID"], "Updated At": now})
                if role_action == "Disable role":
                    append_row("employee_roles", {"Role Name": chosen, "Permissions JSON": json.dumps(selected), "Enabled": "FALSE", "Updated By": current_user["User ID"], "Updated At": now})
                    saved_name = chosen
                else:
                    append_row("employee_roles", {"Role Name": save_role_name, "Permissions JSON": json.dumps(selected), "Enabled": str(enabled).upper(), "Updated By": current_user["User ID"], "Updated At": now})
                    saved_name = save_role_name
                _append_audit(append_row, current_user["User ID"], saved_name, "ROLE_" + role_action.upper().replace(" ", "_"), json.dumps(selected))
                st.success("Role change saved. For rename, reassign existing employees from the disabled old role to the new role.")
    with tab_access:
        st.subheader("Employee Access, Account Lock & Photo Rules")
        if not employee_options:
            st.info("No employee accounts found.")
        else:
            selected_label = st.selectbox("Employee", list(employee_options))
            target = employee_options[selected_label]
            target_id = str(target.get("User ID", ""))
            row_number = employee_records.index(target) + 2
            profile = _latest_rows(profiles, "User ID").get(target_id, {})
            with st.form(f"edit_profile_{target_id}"):
                st.markdown("**Edit employee profile**")
                e1, e2 = st.columns(2)
                edit_name = e1.text_input("Employee Name", value=str(target.get("Employee Name", "")))
                employee_role_options = list(dict.fromkeys(ROLES + [str(x) for x in roles_df.get("Role Name", pd.Series(dtype=str)).tolist() if str(x)]))
                current_role_index = employee_role_options.index(str(target.get("Role", ""))) if str(target.get("Role", "")) in employee_role_options else 0
                edit_role = e2.selectbox("Assigned Role", employee_role_options, index=current_role_index)
                edit_designation = e1.text_input("Designation", value=str(profile.get("Designation", "")))
                edit_department = e2.text_input("Department", value=str(profile.get("Department", "")))
                edit_mobile = e1.text_input("Mobile Number", value=str(profile.get("Mobile Number", "")))
                edit_joining = e2.text_input("Joining Date (YYYY-MM-DD)", value=str(profile.get("Joining Date", "")))
                edit_saved = st.form_submit_button("SAVE EMPLOYEE PROFILE", type="primary")
            if edit_saved:
                if not edit_name.strip() or (edit_mobile and not re.fullmatch(r"[+0-9 ()-]{7,20}", edit_mobile)):
                    st.error("Enter a valid employee name and mobile number.")
                elif edit_joining and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", edit_joining):
                    st.error("Joining date must be YYYY-MM-DD.")
                else:
                    if update_sheet_range("employees", f"C{row_number}:E{row_number}", [[edit_name.strip(), edit_role, str(target.get("Status", "Active"))]]):
                        append_row("employee_profiles", {**{k: profile.get(k, "") for k in PROFILE_COLUMNS}, "User ID": target_id, "Designation": edit_designation, "Department": edit_department, "Mobile Number": edit_mobile, "Joining Date": edit_joining, "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                        _append_audit(append_row, current_user["User ID"], target_id, "PROFILE_UPDATED", "Employee details changed")
                        st.success("Employee profile updated.")
            status_options = ["Active", "Inactive", "Suspended"]
            new_status = st.selectbox("Account status", status_options, index=status_options.index(target.get("Status", "Active")) if target.get("Status", "Active") in status_options else 0)
            if st.button("SAVE ACCOUNT STATUS"):
                values = [[target.get("Password", ""), target.get("Employee Name", ""), target.get("Role", ""), new_status]]
                if update_sheet_range("employees", f"B{row_number}:E{row_number}", values):
                    _append_audit(append_row, current_user["User ID"], target_id, "ACCOUNT_STATUS_CHANGED", new_status)
                    st.success("Account status updated. The employee is checked against the register on each authenticated app rerun.")
            st.markdown("**Individual permission overrides**")
            existing = {}
            if not perms_df.empty:
                own = perms_df[perms_df["User ID"].astype(str) == target_id]
                for _, rr in own.iterrows():
                    existing[str(rr.get("Permission"))] = str(rr.get("Allowed", "")).upper() in {"TRUE", "YES", "1", "ALLOW"}
            for key, label in PERMISSIONS.items():
                default = existing.get(key, None)
                value = st.selectbox(label, ["Use role default", "Allow", "Deny"], index=0 if default is None else (1 if default else 2), key=f"perm_{target_id}_{key}")
                if st.button(f"Save {label}", key=f"save_perm_{target_id}_{key}"):
                    if value != "Use role default":
                        append_row("employee_permissions", {"User ID": target_id, "Permission": key, "Allowed": str(value == "Allow").upper(), "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                    _append_audit(append_row, current_user["User ID"], target_id, "PERMISSION_OVERRIDE", f"{key}={value}")
                    st.success("Permission saved. Updated permission takes effect on the next authenticated app rerun.")
            if st.button("RESET ALL INDIVIDUAL PERMISSIONS TO ROLE DEFAULTS", key=f"reset_access_{target_id}"):
                now = datetime.now().astimezone().isoformat(timespec="seconds")
                for permission in PERMISSIONS:
                    append_row("employee_permissions", {"User ID": target_id, "Permission": permission, "Allowed": "INHERIT", "Updated By": current_user["User ID"], "Updated At": now})
                _append_audit(append_row, current_user["User ID"], target_id, "ACCESS_RESET", "All individual overrides reset to role defaults")
                st.success("Individual permissions reset to role defaults. Updated permissions take effect on the next authenticated app rerun.")
            st.markdown("**Photo permissions**")
            photo_view = st.checkbox("Allow this employee to view other employee photos", value="photo_view_all" in existing and existing["photo_view_all"])
            photo_upload = st.checkbox("Allow this employee to upload/change profile photos", value="photo_upload" in existing and existing["photo_upload"])
            if st.button("SAVE PHOTO PERMISSIONS"):
                for key, val in [("photo_view_all", photo_view), ("photo_upload", photo_upload)]:
                    append_row("employee_permissions", {"User ID": target_id, "Permission": key, "Allowed": str(val).upper(), "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                _append_audit(append_row, current_user["User ID"], target_id, "PHOTO_ACCESS_UPDATED", f"view={photo_view}; upload={photo_upload}")
                st.success("Photo access settings saved.")
            uploaded = st.file_uploader("Replace profile photo", type=["jpg", "jpeg", "png", "webp"], key=f"photo_{target_id}")
            if st.button("UPLOAD / REPLACE PHOTO"):
                if not has_permission("photo_upload"):
                    st.error("Only authorized photo managers can upload photos.")
                elif not uploaded:
                    st.error("Choose a photo first.")
                else:
                    try:
                        data, mime = _profile_photo(uploaded)
                        append_row("employee_profiles", {**{k: profile.get(k, "") for k in PROFILE_COLUMNS}, "User ID": target_id, "Photo Data": data, "Photo MIME": mime, "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                        _append_audit(append_row, current_user["User ID"], target_id, "PHOTO_UPDATED", "Profile photo replaced")
                        st.success("Profile photo updated.")
                    except Exception as exc:
                        st.error(str(exc))
            if st.button("REMOVE PROFILE PHOTO"):
                append_row("employee_profiles", {**{k: profile.get(k, "") for k in PROFILE_COLUMNS}, "User ID": target_id, "Photo Data": "", "Photo MIME": "", "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
                _append_audit(append_row, current_user["User ID"], target_id, "PHOTO_REMOVED", "Profile photo cleared")
                st.success("Profile photo removed.")
    with tab_logs:
        st.subheader("Employee Access Activity")
        st.dataframe(logs.tail(250), use_container_width=True, hide_index=True) if not logs.empty else st.info("No access activity recorded yet.")


def render_salary_management(read_sheet: Callable, append_row: Callable, current_user: dict, append_rows_atomic: Callable | None = None) -> None:
    _apply_employee_theme()
    if not require_permission("salary_management"):
        return
    st.markdown("<h1 style='color:#d71920'>SALARY MANAGEMENT</h1><p>Restricted payroll workspace • employee-specific salary access</p>", unsafe_allow_html=True)
    employees = read_sheet("employees", purpose="payroll")
    salary_df = read_sheet("employee_salary", purpose="payroll")
    policies = read_sheet("salary_policies", purpose="payroll")
    history = read_sheet("salary_history", purpose="payroll")
    employee_rows = employees.to_dict("records") if not employees.empty else []
    if not employee_rows:
        st.info("No employee accounts are available.")
        return
    employee_map = {f"{r.get('Employee Name')} ({r.get('User ID')})": r for r in employee_rows}
    tab_entry, tab_history, tab_policy = st.tabs(["Salary Entry", "Salary History", "Salary Policy"])
    with tab_entry:
        st.subheader("Monthly Salary Entry / Revision")
        with st.form("salary_entry_form"):
            label = st.selectbox("Employee", list(employee_map))
            emp = employee_map[label]
            month = st.text_input("Salary Month (YYYY-MM)", value=date.today().strftime("%Y-%m"))
            policy_latest = policies.iloc[-1].to_dict() if not policies.empty else {"Calculation Days": "30", "Policy Version": "DEFAULT-30", "Payable Day Policy": "Present Days"}
            calculation_days = st.number_input("Calculation Days", min_value=1, max_value=31, value=int(float(policy_latest.get("Calculation Days", 30) or 30)))
            working = st.number_input("Working Days", min_value=0, max_value=31, value=26)
            present = st.number_input("Present Days", min_value=0, max_value=31, value=26)
            leave = st.number_input("Leave Days", min_value=0, max_value=31, value=max(0, int(working - present)))
            monthly = st.number_input("Monthly Salary (₹)", min_value=0.0, step=500.0)
            overtime = st.number_input("Overtime Amount (₹)", min_value=0.0, step=100.0)
            incentives = st.number_input("Incentives (₹)", min_value=0.0, step=100.0)
            bonus = st.number_input("Bonus (₹)", min_value=0.0, step=100.0)
            advance = st.number_input("Advance Amount (₹)", min_value=0.0, step=100.0)
            deductions = st.number_input("Deductions (₹)", min_value=0.0, step=100.0)
            payment_status = st.selectbox("Payment Status", ["Pending", "Paid", "Partially Paid", "On Hold"])
            payment_date = st.date_input("Payment Date", value=date.today())
            remarks = st.text_area("Admin Remarks")
            submitted = st.form_submit_button("SAVE SALARY RECORD", type="primary", use_container_width=True)
        if submitted:
            if not re.fullmatch(r"\d{4}-\d{2}", month.strip()):
                st.error("Salary month must use YYYY-MM format.")
            elif monthly <= 0:
                st.error("Monthly salary must be greater than zero.")
            elif present > working or working > calculation_days or leave > calculation_days:
                st.error("Present / working / leave days exceed the configured salary calculation days.")
            else:
                payable_days = float(present) if str(policy_latest.get("Payable Day Policy", "Present Days")) == "Present Days" else float(min(calculation_days, present + leave))
                try:
                    calc = calculate_salary(monthly, calculation_days, payable_days, overtime, incentives, bonus, advance, deductions)
                    now = datetime.now().astimezone().isoformat(timespec="seconds")
                    record = {"Record ID": str(uuid.uuid4()), "User ID": emp["User ID"], "Employee Name": emp["Employee Name"], "Salary Month": month.strip(), "Monthly Salary": monthly, "Calculation Days": calculation_days, "Working Days": working, "Present Days": present, "Leave Days": leave, "Payable Days": payable_days, **calc, "Payment Status": payment_status, "Payment Date": payment_date.isoformat(), "Admin Remarks": remarks[:500], "Policy Version": policy_latest.get("Policy Version", "DEFAULT-30"), "Created At": now, "Created By": current_user["User ID"]}
                    history_record = {**record, "Revision Type": "Created / Revised", "Revision Date": now}
                    if append_rows_atomic:
                        saved = append_rows_atomic([("employee_salary", record), ("salary_history", history_record)])
                    else:
                        saved = append_row("employee_salary", record) and append_row("salary_history", history_record)
                    if saved:
                        st.success(f"Salary saved. Per day: ₹{calc['Per Day Salary']:,.2f} • Earned: ₹{calc['Earned Salary']:,.2f} • Final: ₹{calc['Final Salary']:,.2f}")
                except Exception as exc:
                    st.error(str(exc))
    with tab_history:
        st.subheader("Employee-wise Salary History")
        search = st.text_input("Search Employee ID / Name")
        month_filter = st.text_input("Filter month (YYYY-MM)")
        data = history.copy()
        if search:
            mask = data["User ID"].astype(str).str.contains(search, case=False, na=False) | data["Employee Name"].astype(str).str.contains(search, case=False, na=False)
            data = data[mask]
        if month_filter:
            data = data[data["Salary Month"].astype(str) == month_filter]
        st.dataframe(data, use_container_width=True, hide_index=True) if not data.empty else st.info("No salary history matches these filters.")
    with tab_policy:
        st.subheader("Salary Calculation Policy")
        current_policy = policies.iloc[-1].to_dict() if not policies.empty else {}
        days = st.number_input("Default calculation days", min_value=1, max_value=31, value=int(float(current_policy.get("Calculation Days", 30) or 30)), key="policy_days")
        payable_policy = st.selectbox("Payable day policy", ["Present Days", "Present + Paid Leave"], index=0 if current_policy.get("Payable Day Policy", "Present Days") == "Present Days" else 1)
        st.caption("Policy changes apply only to salary records created after the change. Existing salary records remain unchanged.")
        if st.button("SAVE NEW SALARY POLICY", type="primary"):
            version = f"POL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            append_row("salary_policies", {"Policy Version": version, "Policy Name": "Custom", "Calculation Days": days, "Payable Day Policy": payable_policy, "Updated By": current_user["User ID"], "Updated At": datetime.now().astimezone().isoformat(timespec="seconds")})
            st.success(f"New policy {version} saved. Existing records were not changed.")
