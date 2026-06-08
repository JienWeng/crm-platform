# Billing Forecast — sales funnel data model + forecast

Adds a **billing forecast** built on a sales funnel, the Twenty-native way (custom
objects/fields/relations via the Metadata API; records via the Core REST API; a
native Dashboard for the visual). No fork, no app build — everything lives in
Postgres on the VPS and is reproducible from these scripts (GitHub = source of truth).

## Model

```
Company (native) ─1:*─ Opportunity (native)
                              └─1:*─ Funnel ─1:*─ Quotation ─1:*─ Invoice
```

- **Funnel** — one pursuit moving through the sales stages. Fields: `stage`
  (0e/1d/2c/3b/4a/closed), `amount`, `winRate %`, `forecastAmount`, `includeInForecast`,
  relation → Opportunity. One Opportunity can have several Funnels.
- **Quotation** — `quoteNumber`, `total`, `status`, `quoteDate`, relation → Funnel.
- **Invoice** — `invoiceNumber`, `amount`, `status`, `invoiceDate`, relation → Quotation.
- **Funnel Stage** — editable config, one row per stage: `stageValue`, `winRate %`,
  `includeInForecast`, `position`. Change win-rates / the forecast threshold here in
  the UI — no code change.

### Win-rates & threshold

| Stage | 0e | 1d | 2c | 3b | 4a | closed |
|-------|----|----|----|----|----|--------|
| Win-rate | 0% | 25% | 50% | 75% | **90%** | **100%** |
| In forecast | – | – | – | – | ✓ | ✓ |

`forecastAmount = amount × winRate%` for funnels at/above the threshold (4a, closed);
0 below it. The **weighted billing forecast** is the sum of `forecastAmount` — so only
4a and closed contribute, exactly as required. Twenty has no formula fields, so
`funnel_forecast.py` keeps `winRate`/`forecastAmount` in sync (run on demand or cron).

## Apply (run against the VPS instance)

The VPS API (`10.1.10.26` / `https://api.quandatics.dpdns.org`) is reachable only on
the VPN / on-site LAN. Get a metadata-capable API key from **Settings → API & Webhooks
→ Create key** in the workspace, then:

```sh
export TWENTY_API_URL=https://api.quandatics.dpdns.org   # or http://localhost:3000 on the box
export TWENTY_API_KEY=<workspace API key>

python3 funnel_provision.py preview        # show current schema, no writes
python3 funnel_provision.py apply          # create objects + fields + relations (idempotent)
python3 funnel_provision.py seed-stages    # create the 6 editable FunnelStage rows

python3 funnel_forecast.py preview         # report the funnel + weighted forecast
python3 funnel_forecast.py apply           # write winRate/forecastAmount, then report
```

Re-running `apply` is safe — it creates only what's missing and never deletes.

## Visualise (native Dashboard, Tier 1)

*Settings → Updates → Early Access → Dashboards → + New Dashboard*, then add:

1. **Weighted billing forecast** — Number widget: source **Funnels**, metric
   `SUM(forecastAmount)`. (Only 4a/closed are non-zero, so this is the forecast.)
2. **Funnel by stage** — Bar/aggregate widget: source **Funnels**, group by `stage`,
   metric `COUNT` (and a second by `SUM(amount)`). Ordered 0e→closed this is the
   wide-top→narrow-bottom funnel.
3. **Pipeline vs forecast** — two Number widgets: `SUM(amount)` (all) vs
   `SUM(forecastAmount)` (weighted).

`funnel_forecast.py` also prints an ASCII funnel + the weighted total for quick CLI checks.
A true funnel-shaped chart widget (vs grouped bars) would be a Tier-2 app and is a
follow-up if the native bar grouping isn't enough.

## Cron (keep the forecast fresh)

On the VPS, e.g. hourly:

```cron
0 * * * * cd /opt/twenty/tools/funnel && TWENTY_API_URL=http://localhost:3000 \
  TWENTY_API_KEY=<key> /usr/bin/python3 funnel_forecast.py apply >> /var/log/funnel.log 2>&1
```
