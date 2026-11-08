# Selva Motors ERP - Testing Results

## Verification performed

**Result: 22/22 automated tests passed.** Command executed from the project root:

```text
python -m unittest discover -s tests -v
Ran 22 tests in 1.342s
OK
```

### Coverage

| Test area | Checks performed | Result |
|---|---|---|
| Authentication | PBKDF2 password verification, legacy-password compatibility, inactive-user rejection, returned profile excludes password | PASS |
| Session report cache | Reuses a session snapshot, marks cache reuse, and force-refresh performs a new read | PASS |
| Read policy | Normal business reads are denied; authentication is limited to employees; reports cannot read disallowed worksheets or implicit full-sheet ranges | PASS |
| Write behavior | Append calls direct `append_row` without a worksheet data read; targeted updates and invoice row deletion use write operations | PASS |
| Delete approval | One atomic spreadsheet batch write deletes the invoice row and marks the request Approved | PASS |
| Architecture guards | No legacy whole-sheet read APIs or Excel storage calls; Google client methods are confined to the gateway; disabled pages are absent from navigation; no Streamlit `pages/` auto-discovery directory; report generation is behind explicit button guards | PASS |
| PDF generation | Daily report spans multiple pages, preserves branding/page numbering, excludes `Total Amount`; wide service report uses landscape A4; Indian rupee grouping | PASS |

## Syntax verification

All **13 active Python files** compiled successfully with `py_compile`, including the app, Google Sheets gateway, report/PDF modules, active UI modules, Extra Fittings module, tests, and devcontainer entry point. A smoke import of the app, gateway, report/PDF modules, both active UI modules, and Extra Fittings also passed using a lightweight Streamlit stub. The maintained `assets/hero_logo.png` asset is checked by its actual image encoding when embedded on the login page, so its MIME type remains correct even though the supplied file content is JPEG-encoded.

## Not performed / deployment checks still required

- **No live Google Sheets API test was performed.** The supplied ZIP did not contain a Google service-account credential or configured `SHEET_ID`.
- **No live Streamlit server/browser acceptance test was performed.** Streamlit is not installed in the build environment; app authentication/access wrappers were imported with a test stub, while all Python modules passed syntax compilation.
- Before production use, configure `.streamlit/secrets.toml`, verify worksheet names and header order, share the spreadsheet with the service-account email, and test login plus each write/report workflow against a non-production copy of the spreadsheet.
- Under the requested write-only policy, global duplicate detection across different users/devices cannot be guaranteed. Same-session retry guards do not provide a spreadsheet-wide unique constraint.
- Extra Fittings remains the supplied local PDF estimate/print flow; the original module had no Google Sheets persistence, and no new storage schema was introduced.

See `API_CALL_AUDIT.md` for the complete permission matrix, expected Sheets calls, read ranges, and data-integrity trade-offs.
