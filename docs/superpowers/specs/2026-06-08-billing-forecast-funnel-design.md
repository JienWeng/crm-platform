# Billing forecast — sales funnel data model + weighted forecast

Date: 2026-06-08 · Status: implemented (repo), pending VPS apply (needs VPN/LAN)

## Goal

A billing forecast driven by a sales funnel across stages **0e, 1d, 2c, 3b, 4a,
closed** (wide-top → narrow-bottom). Each stage has an editable win-rate
(0e=0%, 1d=25%, 2c=50%, 3b=75%, 4a=90%, closed=100%). Only stages **at/above the
threshold (4a, closed)** enter the billing forecast. Visualise the funnel and the
forecast natively. Records hang together in a linked hierarchy.

## Decisions (from brainstorming)

- **Sales stage lives on the Funnel record.** One Opportunity → several Funnels, each
  with its own stage + win-rate.
- **Forecast = Funnel.amount × win-rate**, summed over funnels at/above the threshold.
  Quotations/Invoices are linked records in the chain but do not drive the number.
- **Native / reproducible, no fork.** Custom objects/fields/relations via the Metadata
  API; records via Core REST; visual via native Dashboard. GitHub is the source of
  truth so the VPS can be rebuilt/extended later.

## Data model

```
Company (native) ─1:*─ Opportunity (native)
                              └─1:*─ Funnel ─1:*─ Quotation ─1:*─ Invoice
```

| Object | Key fields |
|--------|-----------|
| **Funnel** (child of Opportunity) | `stage` SELECT(0e…closed), `amount` CURRENCY, `winRate` NUMBER%, `forecastAmount` CURRENCY, `includeInForecast` BOOL, relation→Opportunity |
| **Quotation** (child of Funnel) | `quoteNumber`, `total` CURRENCY, `status` SELECT, `quoteDate`, relation→Funnel |
| **Invoice** (child of Quotation) | `invoiceNumber`, `amount` CURRENCY, `status` SELECT, `invoiceDate`, relation→Quotation |
| **Funnel Stage** (config) | `stageValue`, `winRate` NUMBER%, `includeInForecast` BOOL, `position` — one editable row per stage |

Relations are MANY_TO_ONE on the child (`relationCreationPayload` via the GraphQL
Metadata API — REST cannot create relations); the reverse ONE_TO_MANY field is
auto-created on the parent so the records are linked both ways in the UI.

## Win-rate & threshold (editable, no code)

Win-rates and the in-forecast flag live in the **Funnel Stage** config object, edited
in the UI. `forecastAmount = amount × winRate%` when `includeInForecast`, else 0.
Threshold change = toggle `includeInForecast` on a stage row.

## Computation

Twenty v2.8.3 has **no formula fields**. `tools/funnel/funnel_forecast.py` recomputes
`winRate`/`includeInForecast`/`forecastAmount` on every Funnel from the config
(idempotent PATCH), and prints the weighted forecast + per-stage funnel breakdown. Run
on demand, after edits/import, or on a cron.

## Visualisation

Native Dashboard (Tier 1): a Number widget `SUM(forecastAmount)` = the weighted
billing forecast (only 4a/closed contribute); a Bar widget grouped by `stage`
(count + `SUM(amount)`) = the funnel shape; pipeline-vs-forecast Number widgets. A
true funnel-shaped chart widget is a possible Tier-2 follow-up.

## Implementation

- `tools/funnel/funnel_provision.py` — `preview | apply | seed-stages` (Metadata API).
- `tools/funnel/funnel_forecast.py` — `preview | apply` (recompute + report).
- `tools/funnel/README.md` — apply runbook, dashboard steps, cron.

## Apply to VPS

`10.1.10.26` / `api.quandatics.dpdns.org` is VPN/LAN-only (DEPLOY-NOTES gotcha #6).
On the VPN or on the box: create a metadata-capable API key (Settings → API &
Webhooks), set `TWENTY_API_URL`/`TWENTY_API_KEY`, run `apply` → `seed-stages` →
`funnel_forecast.py apply`, then build the dashboard.

## Out of scope / follow-ups

- Wiring the existing Citrus import to create Funnels (today it creates Companies +
  Opportunities only).
- True funnel-shaped chart widget (Tier-2 app) if native bars are insufficient.
- Auto-recompute via a native Workflow on Funnel change (instead of/in addition to cron).
