# Quandatics CRM — self-hosted Twenty (split deployment)

Our own CRM built on [Twenty](https://github.com/twentyhq/twenty) (open source,
AGPLv3), deployed as a **split**:

```
   VPN/Local users
        │
        ▼  https (CDN)
  app.ourco.com ──────────────►  Azure SWA / Vercel  (static, rebranded twenty-front)
        │
        │  browser API calls (https, Authorization: Bearer …)
        ▼
  api.ourco.com ──────────────►  Caddy (TLS, DNS-01)  ─►  twenty-server :3000
                                    on the company VPS         │
                                    (VPN / local network)      ├─ worker
                                                               ├─ postgres:16
                                                               └─ redis
```

- **Frontend** is public on a CDN but useless without backend access.
- **Backend** is reachable only on the VPN → **users must be on the VPN.**
- Because the CDN frontend is HTTPS, the backend **must** be HTTPS too
  (mixed-content rule) — handled by Caddy with a Cloudflare DNS-01 cert, which
  needs no public inbound traffic.

Repo layout:
- [`backend/`](backend/README.md) — Docker Compose stack + Caddy + env + backups (runs on the VPS)
- [`frontend/`](frontend/README.md) — build + rebrand + deploy scripts (runs on a build machine/CI)

## Order of operations

1. **Domain & DNS** (below) — register domain, DNS on Cloudflare, API token.
2. **Backend** — deploy on the VPS, confirm `https://api.ourco.com/healthz`.
3. **Frontend** — build at the same `TAG`, deploy, set `app.ourco.com` custom domain.
4. **Verify** end-to-end (checklist below).

## Domain & DNS (Cloudflare)

1. Register a domain (e.g. `ourco.com`) at any registrar.
2. Add the zone to **Cloudflare** and switch the registrar's nameservers to Cloudflare's.
3. Create a **Cloudflare API token**: *My Profile → API Tokens → Create* with
   permission **Zone → DNS → Edit** scoped to this zone. Put it in
   `backend/.env` as `CLOUDFLARE_API_TOKEN`.
4. DNS records:
   | Name | Type | Value | Proxy |
   |------|------|-------|-------|
   | `api` | A | VPS **internal/VPN IP** | DNS only (grey cloud) |
   | `app` | CNAME | target from Azure SWA / Vercel | per host instructions |

   `api` resolves for everyone but is only reachable on the VPN — that's the gate.
   Caddy still gets a valid public cert because DNS-01 only proves zone control.

## Wire-up (the values that connect both halves)

| Where | Variable | Value |
|-------|----------|-------|
| `backend/.env` | `TAG` | pinned release, e.g. `v2.8.3` |
| `backend/.env` | `SERVER_URL` | `https://api.ourco.com` |
| `backend/.env` | `FRONTEND_URL` | `https://app.ourco.com` |
| `backend/.env` | `API_DOMAIN` | `api.ourco.com` |
| `backend/.env` | `CLOUDFLARE_API_TOKEN` | DNS-01 token |
| frontend build | `TAG` | **same** as backend |
| frontend build | `REACT_APP_SERVER_BASE_URL` | `https://api.ourco.com` |

## End-to-end verification

1. `curl -I https://api.ourco.com/healthz` from a VPN client → `200`, valid TLS.
2. Open `https://app.ourco.com` on the VPN → DevTools → Network: API calls hit
   `https://api.ourco.com`, no mixed-content / CORS errors.
3. From **off** the VPN: `app.ourco.com` loads but API calls fail → gate confirmed.
4. Create first workspace + user, log out, log back in → bearer-token auth works.
5. Tab title / favicon / logo show the rebrand.
6. Create a record + custom field → no GraphQL schema-version errors (front TAG == back TAG).
7. `docker compose down && up -d`, reload → data persists.

## Upgrades

1. Bump `TAG` in `backend/.env` → `cd backend && docker compose pull && docker compose up -d`.
2. Rebuild + redeploy the frontend at the **same** new `TAG` (`frontend/build-and-deploy.sh`).
   Re-applying `rebrand.sh` is automatic in that script.

## Licensing

Twenty core is **AGPLv3** — self-host and modify freely, but if you distribute/offer
a modified network service you must offer your source. Files marked
`@license Enterprise` need a paid subscription for production; the deploy + light
rebrand path here stays on the AGPL core. Worth a quick legal skim before launch.

## What this repo does NOT do for you
- Provision the VPS or the VPN (company infra).
- Buy the domain or create the Cloudflare token (manual, one-time — see above).
- Hold any secrets — `.env` is git-ignored; fill it on the VPS.
