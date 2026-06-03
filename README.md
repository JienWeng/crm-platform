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
- [`local-dev/`](local-dev/README.md) — run the whole thing on your Mac (dev + preview)
- [`backend/`](backend/README.md) — Docker Compose stack + Caddy + env + backups (runs on the VPS)
- [`frontend/`](frontend/README.md) — build + rebrand + deploy scripts (runs on your Mac / CI)
- [`CONFIGURE.md`](CONFIGURE.md) — Entra ID SSO, sign-up, roles/permissions, data migration
- [`CUSTOMIZING.md`](CUSTOMIZING.md) — how to change the product (dev → test → ship)
- [`tools/migrate.py`](tools/migrate.py) — bulk CSV → REST import script
- [`ROADMAP.md`](ROADMAP.md) — phased plan from local preview to production

---

# Local development (on your Mac)

Prereqs: **Docker Desktop** running; for source/rebrand work also **Node 24.15.x**
+ `corepack enable` and ~8 GB free RAM. Full detail + 3 loops in
[`local-dev/README.md`](local-dev/README.md).

**Fastest — see the app running:**
```sh
cd local-dev
cp .env.example .env          # throwaway local secrets
docker compose up -d          # pulls + starts server + worker + postgres + redis
open http://localhost:3000    # create the first workspace + user
```
Native **Dashboards** live under *Settings → Updates → Early Access* — try those
before writing any code (they may cover your needs with zero changes).

**Iterate on branding / UI (hot reload):**
```sh
# with the stack above running on :3000
git clone --branch v2.8.3 --depth 1 https://github.com/twentyhq/twenty.git
cd twenty && corepack enable && yarn
echo 'REACT_APP_SERVER_BASE_URL=http://localhost:3000' > packages/twenty-front/.env
npx nx start twenty-front     # UI with hot reload on :3001
```

**Stop / reset:**
```sh
cd local-dev
docker compose down           # stop (keeps data)
docker compose down -v        # stop + wipe the local database
```

For changing product code the right way (tiers, conventions, tests), see
[`CUSTOMIZING.md`](CUSTOMIZING.md).

---

# Deploy to production

Order of operations (each step links to its detailed runbook):

1. **Domain & DNS** (below) — register domain, DNS on Cloudflare, API token.
2. **Backend** ([`backend/README.md`](backend/README.md)) — on the VPS:
   ```sh
   cd /opt/twenty/backend
   cp .env.example .env        # set TAG, domains, secrets, Cloudflare token
   docker compose up -d
   curl -I https://api.ourco.com/healthz   # expect 200, valid TLS
   ```
3. **Frontend** ([`frontend/README.md`](frontend/README.md)) — from your Mac, same `TAG`:
   ```sh
   cd frontend
   TAG=v2.8.3 REACT_APP_SERVER_BASE_URL=https://api.ourco.com APP_NAME="Quandatics CRM" \
     HOST=azure SWA_DEPLOYMENT_TOKEN=xxxxx ./build-and-deploy.sh
   ```
   Then set the `app.ourco.com` custom domain on the host and create its CNAME.
4. **Verify** end-to-end (checklist below).

Deploying the backend *from your Mac* (remote Docker context or rsync+ssh) and
shipping custom code are covered in [`local-dev/README.md`](local-dev/README.md)
and [`CUSTOMIZING.md`](CUSTOMIZING.md).

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
