#!/usr/bin/env python3
"""Provision the Billing Forecast funnel data model in Twenty (the Twenty-native way).

Creates, idempotently, via the Metadata GraphQL API (`/metadata`):

    Company (native) ─1:*─ Opportunity (native)
                                  └─1:*─ Funnel ─1:*─ Quotation ─1:*─ Invoice

plus a small editable config object `FunnelStage` (one row per sales stage holding
the win-rate and the in-forecast flag) so win-rates / thresholds can be changed in
the UI without code.

Sales stages: 0e, 1d, 2c, 3b, 4a, closed.
Default win-rates: 0e=0%, 1d=25%, 2c=50%, 3b=75%, 4a=90%, closed=100%.
In billing forecast: only 4a and closed (win-rate >= threshold / includeInForecast=true).

The forecast number itself (Funnel.winRate + Funnel.forecastAmount) is recomputed by
`funnel_forecast.py` — Twenty has no formula fields, so a small idempotent sync keeps
those columns correct. Visualise via a native Dashboard (see README).

Usage:
  TWENTY_API_URL=https://api.quandatics.dpdns.org \
  TWENTY_API_KEY=<workspace metadata-capable API key> \
  python3 funnel_provision.py preview        # show what exists / what would be created
  python3 funnel_provision.py apply          # create missing objects, fields, relations
  python3 funnel_provision.py seed-stages    # (re)create the 6 FunnelStage config rows

`apply` is safe to re-run: every object/field is created only if absent. It never
deletes or alters existing schema.

Endpoints are version-checked against Twenty v2.8.3:
  createOneObject(input:{object:{...}})  createOneField(input:{field:{...}})
  relationCreationPayload={type,targetObjectMetadataId,targetFieldLabel,targetFieldIcon}
"""
import os, sys, json, urllib.request, urllib.error

API_URL = os.environ.get("TWENTY_API_URL", "").rstrip("/")
API_KEY = os.environ.get("TWENTY_API_KEY", "")

# ── Stage definitions (label shown in UI, value stored in the SELECT) ──────────
STAGES = [
    # label,  value,    color,    winRate, includeInForecast
    ("0e",     "S0E",    "gray",     0,   False),
    ("1d",     "S1D",    "blue",    25,   False),
    ("2c",     "S2C",    "turquoise",50,  False),
    ("3b",     "S3B",    "yellow",  75,   False),
    ("4a",     "S4A",    "orange",  90,   True),
    ("closed", "CLOSED", "green",  100,   True),
]
STAGE_OPTIONS = [
    {"label": lbl, "value": val, "color": col, "position": i}
    for i, (lbl, val, col, _wr, _inc) in enumerate(STAGES)
]


# ── HTTP helpers ───────────────────────────────────────────────────────────────
def _post(path, payload):
    if not API_URL or not API_KEY:
        sys.exit("Set TWENTY_API_URL and TWENTY_API_KEY (a metadata-capable API key).")
    req = urllib.request.Request(
        API_URL + path, method="POST",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        data=json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


def gql(query, variables=None):
    st, body = _post("/metadata", {"query": query, "variables": variables or {}})
    if "errors" in body:
        raise RuntimeError(json.dumps(body["errors"]))
    return body.get("data", {})


def rest(method, path, body=None):
    """Core REST API (records), e.g. seeding FunnelStage rows."""
    req = urllib.request.Request(
        API_URL + path, method=method,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


# ── Metadata introspection (idempotency) ───────────────────────────────────────
def fetch_schema():
    """Return {nameSingular: {id, fields:{fieldName:id}}} for all objects."""
    data = gql("""
      query {
        objects(paging: { first: 500 }) {
          edges { node {
            id nameSingular namePlural
            fields(paging: { first: 500 }) { edges { node { id name type } } }
          } }
        }
      }
    """)
    out = {}
    for e in data["objects"]["edges"]:
        n = e["node"]
        out[n["nameSingular"]] = {
            "id": n["id"],
            "fields": {f["node"]["name"]: f["node"]["id"] for f in n["fields"]["edges"]},
        }
    return out


def ensure_object(schema, name_s, name_p, label_s, label_p, icon):
    if name_s in schema:
        print(f"  = object {name_s} exists ({schema[name_s]['id']})")
        return schema[name_s]["id"]
    data = gql("""
      mutation($input: CreateOneObjectInput!) {
        createOneObject(input: $input) { id nameSingular }
      }
    """, {"input": {"object": {
        "nameSingular": name_s, "namePlural": name_p,
        "labelSingular": label_s, "labelPlural": label_p, "icon": icon,
    }}})
    oid = data["createOneObject"]["id"]
    print(f"  + object {name_s} -> {oid}")
    schema[name_s] = {"id": oid, "fields": {}}
    return oid


def ensure_field(schema, obj_name, field):
    """field: dict with at least name,label,type (+ options / relationCreationPayload)."""
    obj = schema[obj_name]
    if field["name"] in obj["fields"]:
        print(f"  = field {obj_name}.{field['name']} exists")
        return obj["fields"][field["name"]]
    payload = {"objectMetadataId": obj["id"], **field}
    data = gql("""
      mutation($input: CreateOneFieldMetadataInput!) {
        createOneField(input: $input) { id name }
      }
    """, {"input": {"field": payload}})
    fid = data["createOneField"]["id"]
    obj["fields"][field["name"]] = fid
    extra = ""
    if field["type"] == "RELATION":
        extra = f"  (MANY_TO_ONE -> {field['relationCreationPayload']['targetFieldLabel']})"
    print(f"  + field {obj_name}.{field['name']} [{field['type']}]{extra}")
    return fid


def relation_to(schema, target_name, reverse_label, reverse_icon="IconList"):
    """Build a MANY_TO_ONE relationCreationPayload pointing at target object.
    The reverse ONE_TO_MANY field (reverse_label) is auto-created on the target."""
    return {
        "type": "RELATION",
        "name": target_name,            # e.g. funnel.opportunity
        "label": target_name.capitalize(),
        "relationCreationPayload": {
            "type": "MANY_TO_ONE",
            "targetObjectMetadataId": schema[target_name]["id"],
            "targetFieldLabel": reverse_label,
            "targetFieldIcon": reverse_icon,
        },
    }


# ── Field specs ────────────────────────────────────────────────────────────────
def select(name, label, options, icon="IconList"):
    return {"name": name, "label": label, "type": "SELECT", "icon": icon, "options": options}


def currency(name, label, icon="IconCurrencyDollar"):
    return {"name": name, "label": label, "type": "CURRENCY", "icon": icon}


def number(name, label, icon="IconNumber"):
    return {"name": name, "label": label, "type": "NUMBER", "icon": icon}


def boolean(name, label, icon="IconCheck"):
    return {"name": name, "label": label, "type": "BOOLEAN", "icon": icon}


def text(name, label, icon="IconAbc"):
    return {"name": name, "label": label, "type": "TEXT", "icon": icon}


def dt(name, label, icon="IconCalendar"):
    return {"name": name, "label": label, "type": "DATE_TIME", "icon": icon}


# ── Apply ──────────────────────────────────────────────────────────────────────
def apply(preview=False):
    schema = fetch_schema()
    if "opportunity" not in schema:
        sys.exit("Native 'opportunity' object not found — is this a Twenty workspace?")

    if preview:
        print("PREVIEW — no writes. Existing objects:",
              ", ".join(sorted(schema)))
        print("\nWould ensure: funnel, quotation, invoice, funnelStage (+ fields & relations).")
        return

    print("=== Objects ===")
    ensure_object(schema, "funnel", "funnels", "Funnel", "Funnels", "IconFilter")
    ensure_object(schema, "quotation", "quotations", "Quotation", "Quotations", "IconFileInvoice")
    ensure_object(schema, "invoice", "invoices", "Invoice", "Invoices", "IconReceipt")
    ensure_object(schema, "funnelStage", "funnelStages", "Funnel Stage", "Funnel Stages", "IconStairs")

    print("\n=== Funnel fields ===")
    ensure_field(schema, "funnel", select("stage", "Stage", STAGE_OPTIONS, "IconStairs"))
    ensure_field(schema, "funnel", currency("amount", "Amount"))
    ensure_field(schema, "funnel", number("winRate", "Win Rate %"))
    ensure_field(schema, "funnel", currency("forecastAmount", "Forecast Amount"))
    ensure_field(schema, "funnel", boolean("includeInForecast", "In Forecast"))
    ensure_field(schema, "funnel", relation_to(schema, "opportunity", "Funnels", "IconFilter"))

    print("\n=== Quotation fields ===")
    ensure_field(schema, "quotation", text("quoteNumber", "Quote Number"))
    ensure_field(schema, "quotation", currency("total", "Total"))
    ensure_field(schema, "quotation", select("status", "Status", [
        {"label": "Draft", "value": "DRAFT", "color": "gray", "position": 0},
        {"label": "Sent", "value": "SENT", "color": "blue", "position": 1},
        {"label": "Accepted", "value": "ACCEPTED", "color": "green", "position": 2},
        {"label": "Rejected", "value": "REJECTED", "color": "red", "position": 3},
    ]))
    ensure_field(schema, "quotation", dt("quoteDate", "Quote Date"))
    ensure_field(schema, "quotation", relation_to(schema, "funnel", "Quotations", "IconFileInvoice"))

    print("\n=== Invoice fields ===")
    ensure_field(schema, "invoice", text("invoiceNumber", "Invoice Number"))
    ensure_field(schema, "invoice", currency("amount", "Amount"))
    ensure_field(schema, "invoice", select("status", "Status", [
        {"label": "Draft", "value": "DRAFT", "color": "gray", "position": 0},
        {"label": "Issued", "value": "ISSUED", "color": "blue", "position": 1},
        {"label": "Paid", "value": "PAID", "color": "green", "position": 2},
        {"label": "Overdue", "value": "OVERDUE", "color": "red", "position": 3},
        {"label": "Cancelled", "value": "CANCELLED", "color": "gray", "position": 4},
    ]))
    ensure_field(schema, "invoice", dt("invoiceDate", "Invoice Date"))
    ensure_field(schema, "invoice", relation_to(schema, "quotation", "Invoices", "IconReceipt"))

    print("\n=== FunnelStage config fields ===")
    ensure_field(schema, "funnelStage", text("stageValue", "Stage Value"))
    ensure_field(schema, "funnelStage", number("winRate", "Win Rate %"))
    ensure_field(schema, "funnelStage", boolean("includeInForecast", "In Forecast"))
    ensure_field(schema, "funnelStage", number("position", "Position"))

    print("\nDone. Now run: python3 funnel_provision.py seed-stages")


# ── Seed the 6 editable stage-config rows ──────────────────────────────────────
def seed_stages():
    st, existing = rest("GET", "/rest/funnelStages?limit=200")
    have = {r.get("stageValue") for r in (existing.get("data", {}).get("funnelStages", []) if st == 200 else [])}
    print(f"=== Seed FunnelStage rows (existing: {len(have)}) ===")
    for i, (lbl, val, _col, wr, inc) in enumerate(STAGES):
        if val in have:
            print(f"  = {lbl} exists"); continue
        s, d = rest("POST", "/rest/funnelStages", {
            "name": lbl, "stageValue": val, "winRate": wr,
            "includeInForecast": inc, "position": i,
        })
        print(f"  + {lbl}: winRate={wr}% inForecast={inc} -> HTTP {s}")
    print("\nEdit win-rates / thresholds anytime in the UI (Funnel Stages object), "
          "then re-run funnel_forecast.py.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if cmd == "preview":
        apply(preview=True)
    elif cmd == "apply":
        apply(preview=False)
    elif cmd == "seed-stages":
        seed_stages()
    else:
        sys.exit("usage: funnel_provision.py [preview|apply|seed-stages]")
