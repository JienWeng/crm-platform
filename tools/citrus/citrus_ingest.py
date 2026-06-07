#!/usr/bin/env python3
"""Extract Citrus Cloud customers+projects from the Billing Forecast workbook and
(optionally) ingest them into Twenty via REST.

Usage:
  python3 citrus_ingest.py preview                 # parse + show mapped records, no writes
  TWENTY_API_URL=http://localhost:3000 TWENTY_API_KEY=<key> \
    python3 citrus_ingest.py ingest                 # create companies + opportunities

Raw-parses the .xlsx (zip+XML) because its styles.xml breaks openpyxl/pandas.
"""
import os, sys, json, zipfile, re
import xml.etree.ElementTree as ET
NS="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ART=os.path.expanduser("~/Documents/Quandatics/CRM/quandatics-artifacts/Billing Forecast - Citrus Cloud (1).xlsx")

def col_to_idx(ref):
    m=re.match(r"([A-Z]+)",ref)
    if not m: return 0
    n=0
    for ch in m.group(1): n=n*26+(ord(ch)-64)
    return n-1

def read_xlsx(f):
    z=zipfile.ZipFile(f); shared=[]
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid={r.get("Id"):r.get("Target") for r in rels}; out={}
    for s in wb.find(f"{NS}sheets"):
        tgt=rid.get(s.get(f"{RNS}id"),""); tgt=tgt if tgt.startswith("xl/") else "xl/"+tgt
        rows=[]
        for row in ET.fromstring(z.read(tgt)).iter(f"{NS}row"):
            cells={}; mx=0
            for c in row.findall(f"{NS}c"):
                ci=col_to_idx(c.get("r","")); mx=max(mx,ci); t=c.get("t")
                v=c.find(f"{NS}v"); isv=c.find(f"{NS}is"); val=""
                if t=="s" and v is not None:
                    try: val=shared[int(v.text)]
                    except: val=""
                elif t=="inlineStr" and isv is not None: val="".join(x.text or "" for x in isv.iter(f"{NS}t"))
                elif v is not None: val=v.text
                cells[ci]=val
            rows.append([str(cells.get(i,"")).strip() for i in range(mx+1)])
        out[s.get("name")]=rows
    return out

def extract():
    d=read_xlsx(ART)
    # --- Customers (sheet "1. Customer Data"), header row index 3 ---
    companies={}
    for r in d["1. Customer Data"][4:]:
        name=(r[1] if len(r)>1 else "").strip(); code=(r[2] if len(r)>2 else "").strip()
        mgr=(r[3] if len(r)>3 else "").strip()
        if name and re.match(r"^[A-Za-z]{2,6}$", code) and "Customer" not in name and "DUPLICAT" not in name.upper():
            companies.setdefault(code, {"name":name,"code":code,"accountManager":mgr})
    # --- Projects (sheet "2. Project Data"); data rows have a numeric Year in col0 ---
    projects=[]
    for r in d["2. Project Data"][4:]:
        if len(r)<19: r=r+[""]*(19-len(r))
        year,code_cust,proj_code,cust_name = r[0], r[2], r[7], r[8]
        desc, mgr, inv_co = r[10], r[11], r[12]
        total, billed, forecast, recog = r[13], r[14], r[15], r[18]
        if not (year.isdigit() and proj_code and proj_code not in ("None","Auto-generated") and cust_name):
            continue
        def num(x):
            try: return float(str(x).replace(",","")) if str(x) not in("","None") else 0.0
            except: return 0.0
        projects.append({
            "projectCode":proj_code, "customerName":cust_name, "customerCode":code_cust,
            "description":" ".join(desc.split())[:200], "accountManager":mgr, "invoiceVia":inv_co,
            "totalAmount":num(total), "billed":num(billed), "forecast":num(forecast),
            "recognisedPct":num(recog),
            "stage": ("CUSTOMER" if num(billed)>0 else ("PROPOSAL" if num(forecast)>0 else "NEW")),
        })
    return list(companies.values()), projects

def preview():
    comps, projs = extract()
    print(f"\n=== COMPANIES ({len(comps)}) ===")
    for c in comps: print(f"  [{c['code']}] {c['name']}  (AM: {c['accountManager']})")
    print(f"\n=== OPPORTUNITIES / PROJECTS ({len(projs)}) ===")
    tot=0
    for p in projs:
        tot+=p["totalAmount"]
        print(f"  {p['projectCode']:<18} {p['customerName'][:26]:<26} RM{p['totalAmount']:>12,.0f}  {p['stage']:<9} | {p['description'][:46]}")
    print(f"\n  TOTAL pipeline value: RM {tot:,.0f}")
    return comps, projs

def api(method, path, key, body=None):
    import urllib.request
    base=os.environ["TWENTY_API_URL"].rstrip("/")
    req=urllib.request.Request(base+path, method=method,
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
        data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(req) as r: return json.loads(r.read() or "{}")

def ingest():
    key=os.environ["TWENTY_API_KEY"]; comps,projs=extract(); idmap={}
    for c in comps:
        res=api("POST","/rest/companies",key,{"name":c["name"]})
        cid=res.get("data",{}).get("createCompany",{}).get("id") or res.get("data",{}).get("id")
        idmap[c["code"]]=cid; print(f"  + company {c['name']} -> {cid}")
    for p in projs:
        body={"name":f"{p['projectCode']} — {p['description'][:60]}",
              "stage":p["stage"],
              "amount":{"amountMicros":int(p["totalAmount"]*1_000_000),"currencyCode":"MYR"}}
        cid=idmap.get(p["customerCode"])
        if cid: body["companyId"]=cid
        res=api("POST","/rest/opportunities",key,body)
        print(f"  + opp {p['projectCode']} -> {res.get('data',{}).get('id') or res}")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "preview"
    (preview if cmd=="preview" else ingest)()
