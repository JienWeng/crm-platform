#!/usr/bin/env python3
"""Bulk-import data into Twenty CRM via the REST batch API (stdlib only).

Twenty 2.x: POST /rest/batch/{objectPlural}, max 60 records/call, 100 req/min,
auth via `Authorization: Bearer <key>`. This script imports companies, then
people linked to those companies by companyId.

Setup:
    export TWENTY_API_URL=https://api.ourco.com     # no trailing slash
    export TWENTY_API_KEY=<your api key>            # Settings → API & Webhooks

Usage:
    python3 migrate.py companies path/to/companies.csv
    python3 migrate.py people    path/to/people.csv

CSV columns:
    companies.csv : name, domain            (domain optional)
    people.csv    : firstName, lastName, email, company   (company = a name
                    present in companies.csv; resolved to companyId)

People import reads .company_map.json (written by the companies import) to map
company name → id. Run companies first. Re-running is NOT idempotent — Twenty
generates new ids each call; dedupe your source first.
"""
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_URL = os.environ.get("TWENTY_API_URL", "").rstrip("/")
API_KEY = os.environ.get("TWENTY_API_KEY", "")
BATCH = 60                      # Twenty's documented max per batch call
SLEEP = 0.7                     # ~85 req/min, under the 100/min limit
MAP_FILE = os.path.join(os.path.dirname(__file__), ".company_map.json")


def die(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def post_batch(object_plural, records):
    """POST up to 60 records; returns the list of created records."""
    url = f"{API_URL}/rest/batch/{object_plural}"
    body = json.dumps(records).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {API_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        die(f"{e.code} {e.reason}: {e.read().decode()[:500]}")
    except urllib.error.URLError as e:
        die(f"connection failed: {e}")
    # Twenty wraps results; accept a few shapes defensively.
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            # e.g. {"data": {"createCompanies": [...]}}
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
        return data
    return payload if isinstance(payload, list) else []


def chunked(rows, n):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def import_companies(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    name_to_id = {}
    total = 0
    for batch in chunked(rows, BATCH):
        records = []
        for r in batch:
            rec = {"name": (r.get("name") or "").strip()}
            domain = (r.get("domain") or "").strip()
            if domain:
                if not domain.startswith("http"):
                    domain = "https://" + domain
                rec["domainName"] = {"primaryLinkUrl": domain}
            records.append(rec)
        created = post_batch("companies", records)
        for rec, out in zip(batch, created):
            cid = out.get("id") if isinstance(out, dict) else None
            if cid:
                name_to_id[(rec.get("name") or "").strip()] = cid
        total += len(created)
        print(f"  companies: +{len(created)} (total {total})")
        time.sleep(SLEEP)
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(name_to_id, f)
    print(f"Done. {total} companies. Map saved to {MAP_FILE}")


def import_people(path):
    name_to_id = {}
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, encoding="utf-8") as f:
            name_to_id = json.load(f)
    else:
        print("WARN: no .company_map.json — people won't be linked to companies.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    total = 0
    unmatched = set()
    for batch in chunked(rows, BATCH):
        records = []
        for r in batch:
            rec = {
                "name": {
                    "firstName": (r.get("firstName") or "").strip(),
                    "lastName": (r.get("lastName") or "").strip(),
                }
            }
            email = (r.get("email") or "").strip()
            if email:
                rec["emails"] = {"primaryEmail": email}
            company = (r.get("company") or "").strip()
            if company:
                cid = name_to_id.get(company)
                if cid:
                    rec["companyId"] = cid
                else:
                    unmatched.add(company)
            records.append(rec)
        created = post_batch("people", records)
        total += len(created)
        print(f"  people: +{len(created)} (total {total})")
        time.sleep(SLEEP)
    print(f"Done. {total} people.")
    if unmatched:
        print(f"WARN: {len(unmatched)} company names had no id (not linked): "
              f"{sorted(unmatched)[:10]}{' …' if len(unmatched) > 10 else ''}")


def main():
    if not API_URL or not API_KEY:
        die("set TWENTY_API_URL and TWENTY_API_KEY")
    if len(sys.argv) != 3:
        die("usage: migrate.py <companies|people> <csv-path>")
    kind, path = sys.argv[1], sys.argv[2]
    if not os.path.exists(path):
        die(f"no such file: {path}")
    if kind == "companies":
        import_companies(path)
    elif kind == "people":
        import_people(path)
    else:
        die("first arg must be 'companies' or 'people'")


if __name__ == "__main__":
    main()
