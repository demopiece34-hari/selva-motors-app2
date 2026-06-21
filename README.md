# SELVA MOTORS | HERO Dealership ERP

Production-ready Streamlit ERP for a Hero two-wheeler dealership.

## What this version does

- Google Sheet only architecture
- Fast login that reads only the Employees sheet
- Role-based navigation for Owner, Admin, Service Advisor, Technician and Billing
- Dashboard with instant daily KPIs
- Attendance check-in / check-out
- Service job cards
- Invoice entry with GST support
- Manual bill generation
- OCR upload for invoice extraction
- Customer / vehicle history
- Technician summary
- Reports and duplicate checks
- Full-screen HERO loader
- Safe cache invalidation after save / update / delete

## Sheets used

The app preserves the existing workbook structure:

- employees
- attendance
- invoices
- delete_requests
- pending_invoice_requests
- manual_invoices
- settings

It also adds new sheets only when needed:

- customers
- vehicles
- service_jobs
- billing_records
- technicians

## Files

- `app.py`
- `google_sheet.py`
- `hero_loader.py`
- `pdf_generator.py`
- `ocr_module.py`
- `utils.py`

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit secrets

Set:

- `SHEET_ID`
- `gcp_service_account`

The Google Sheet is the only source of truth.
