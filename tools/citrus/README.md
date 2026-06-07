# Citrus Cloud ingest

Parses the **Billing Forecast - Citrus Cloud** workbook and loads it into Twenty
as Companies + Opportunities via the REST API. Credentials come from the
environment — **never hardcode the API key**.

The workbook's `styles.xml` breaks openpyxl/pandas, so the parser reads the
`.xlsx` zip + sheet XML directly.

## Mapping
- **Customers** (sheet `1. Customer Data`) → Companies (4: TIME dotCom, NTT Data,
  CTC Global, Hitachi Asia).
- **Projects** (sheet `2. Project Data`) → Opportunities (21), linked to their
  company, amount = Total Amount (MYR), stage from billing status
  (billed→CUSTOMER, forecast→PROPOSAL, else NEW).

## Usage
```sh
# preview only (no writes)
python3 citrus_ingest.py preview

# clean demo seed + ingest (create/delete only — never truncates)
TWENTY_API_URL=https://api.quandatics.dpdns.org \
TWENTY_API_KEY=<workspace API key> \
python3 citrus_run.py
```
`citrus_run.py` deletes the Twenty demo seed (Notion/Stripe/… companies, demo
people + opportunities) then creates the Citrus Cloud records. It only ever
issues per-id `DELETE` and `POST` — no schema/table operations.

Artifact path is set in `citrus_ingest.py` (`ART`); adjust if the workbook moves.
