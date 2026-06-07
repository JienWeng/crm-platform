#!/usr/bin/env python3
"""Clean Twenty demo data + ingest Citrus Cloud companies/opportunities. Create+delete only."""
import os, json, urllib.request, urllib.error
import importlib.util
spec=importlib.util.spec_from_file_location("ci", os.path.expanduser("~/crm-platform/tools/citrus/citrus_ingest.py"))
ci=importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
BASE=os.environ["TWENTY_API_URL"].rstrip("/"); KEY=os.environ["TWENTY_API_KEY"]

def call(method, path, body=None):
    req=urllib.request.Request(BASE+path, method=method,
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
        data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")

def list_all(obj):
    st,d=call("GET", f"/rest/{obj}?limit=200"); return d.get("data",{}).get(obj,[]) if st==200 else []

def newid(d):  # extract id from create response
    data=d.get("data",{})
    for k,v in data.items():
        if isinstance(v,dict) and v.get("id"): return v["id"]
    return data.get("id")

print("=== STEP 1: DELETE demo data (opportunities, people, companies) ===")
for obj in ("opportunities","people","companies"):
    for r in list_all(obj):
        nm=r.get("name"); nm=(nm.get("firstName","")+" "+nm.get("lastName","")).strip() if isinstance(nm,dict) else nm
        st,_=call("DELETE", f"/rest/{obj}/{r['id']}")
        print(f"  delete {obj[:-1]:<12} {str(nm)[:30]:<30} -> HTTP {st}")

print("\n=== STEP 2: CREATE Citrus Cloud companies ===")
comps, projs = ci.extract()
idmap={}
for c in comps:
    st,d=call("POST","/rest/companies",{"name":c["name"]})
    cid=newid(d); idmap[c["code"]]=cid
    print(f"  + company {c['name'][:34]:<34} -> {st} {cid}")

print("\n=== STEP 3: CREATE Citrus Cloud opportunities ===")
ok=0; fail=0
for p in projs:
    body={"name":f"{p['projectCode']} — {p['description'][:55]}".strip(),
          "stage":p["stage"],
          "amount":{"amountMicros":int(round(p["totalAmount"]*1_000_000)),"currencyCode":"MYR"}}
    cid=idmap.get(p["customerCode"])
    if cid: body["companyId"]=cid
    st,d=call("POST","/rest/opportunities",body)
    if st in (200,201): ok+=1
    else: fail+=1; print(f"   ! {p['projectCode']} HTTP {st}: {str(d)[:120]}")
print(f"  opportunities created: {ok}  failed: {fail}")

print("\n=== STEP 4: VERIFY final counts ===")
for obj in ("companies","opportunities"):
    print(f"  {obj}: {len(list_all(obj))}")
