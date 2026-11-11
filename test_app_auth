import importlib
import sys
import types
import unittest

import pandas as pd


class StreamlitImportStub(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.secrets = {}

    def set_page_config(self, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def cache_data(self, *args, **kwargs):
        return lambda fn: fn

    def error(self, *args, **kwargs):
        return None


# The build environment does not install Streamlit. Stub its import-time UI calls
# so we can test the app's authentication and access wrappers without a live server.
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = StreamlitImportStub()
app = importlib.import_module("app")


class AppAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.original_reader = app.read_auth_sheet

    def tearDown(self):
        app.read_auth_sheet = self.original_reader

    def test_pbkdf2_login_returns_profile_without_password(self):
        app.read_auth_sheet = lambda: pd.DataFrame([{
            "User ID": "hari", "Password": app._password_hash("secure-test-password"),
            "Employee Name": "Hari", "Role": "Admin", "Status": "Active",
        }])
        profile = app.login_user("HARI", "secure-test-password")
        self.assertEqual(profile, {"User ID": "hari", "Employee Name": "Hari", "Role": "Admin"})
        self.assertNotIn("Password", profile)

    def test_legacy_plaintext_password_remains_compatible(self):
        app.read_auth_sheet = lambda: pd.DataFrame([{
            "User ID": "old-user", "Password": "old-pass",
            "Employee Name": "Old User", "Role": "Technician", "Status": "Active",
        }])
        profile = app.login_user("old-user", "old-pass")
        self.assertEqual(profile["Role"], "Technician")

    def test_inactive_or_wrong_password_users_cannot_login(self):
        app.read_auth_sheet = lambda: pd.DataFrame([{
            "User ID": "inactive", "Password": "test",
            "Employee Name": "Inactive User", "Role": "Technician", "Status": "Inactive",
        }])
        self.assertIsNone(app.login_user("inactive", "test"))
        self.assertIsNone(app.login_user("inactive", "wrong"))

    def test_report_read_cache_reuses_session_snapshot_and_force_refreshes(self):
        original_reader = app.sheets_read_sheet
        original_ensure = app._ensure_sheets_gateway
        original_state = dict(app.st.session_state)
        calls = []
        def fake_reader(sheet_name, *, purpose, columns):
            calls.append((sheet_name, purpose, list(columns)))
            return pd.DataFrame([{column: "value" for column in columns}])
        try:
            app.st.session_state.clear()
            app.sheets_read_sheet = fake_reader
            app._ensure_sheets_gateway = lambda: None
            first = app.read_report_sheet("invoices", columns=["Date", "Technician Name"])
            second = app.read_report_sheet("invoices", columns=["Date", "Technician Name"])
            self.assertEqual(len(calls), 1)
            self.assertFalse(first.attrs["sheets_cache_reused"])
            self.assertTrue(second.attrs["sheets_cache_reused"])
            self.assertEqual(first.attrs["sheets_fetched_at"], second.attrs["sheets_fetched_at"])
            app.read_report_sheet("invoices", force_refresh=True, columns=["Date", "Technician Name"])
            self.assertEqual(len(calls), 2)
        finally:
            app.sheets_read_sheet = original_reader
            app._ensure_sheets_gateway = original_ensure
            app.st.session_state.clear()
            app.st.session_state.update(original_state)

    def test_business_read_wrappers_deny_normal_pages(self):
        with self.assertRaises(PermissionError):
            app.read_sheet("invoices")
        self.assertFalse(hasattr(app, "google_read_sheet"))


if __name__ == "__main__":
    unittest.main()
