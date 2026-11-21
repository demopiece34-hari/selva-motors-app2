SELVA MOTORS ERP - REPORTS ENTRY COMPATIBILITY FIX

WHAT WAS FIXED
1. app.py now checks the imported render_report_center() signature before calling it.
2. If report_center.py is an older/incompatible version, the app shows a clear on-screen file-version warning instead of raising a TypeError at the report call.
3. If the Reports UI itself raises another exception, the app logs the full error and displays its exact exception/traceback in Streamlit's Technical details expander.
4. app.py, report_center.py and report_engine.py are included from the same matching project snapshot.

FILES MODIFIED
- app.py
- tests/test_report_entry_contract.py (new compatibility checks)

REPORT MODULE FILES INCLUDED AS A MATCHED SET
- app.py
- report_center.py
- report_engine.py

INSTALLATION
1. Download and extract this ZIP.
2. Open the extracted folder. Its app.py, report_center.py and report_engine.py must be directly at the repository root (same folder as requirements.txt).
3. Upload/replace all extracted project files in the EXISTING GitHub repository. Do not upload the ZIP itself.
4. Commit the changes.
5. In Streamlit Cloud, verify repository, branch and main file path (app.py), then choose Reboot.
6. In the browser, press Ctrl+F5.

IMPORTANT
- Replace app.py, report_center.py and report_engine.py together. Do not mix these files with an older copy.
- This package does not modify Google Sheets data, worksheet names, columns or source records.
- Automated code tests and Python compilation passed in the build environment. Live Streamlit Cloud and live Google Sheets execution cannot be guaranteed from this package build.
