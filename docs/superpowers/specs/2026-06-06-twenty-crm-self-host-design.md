# Design — Self-hosted Twenty CRM, multi-entity, public, custom-branded

**Date:** 2026-06-06
**Status:** Approved (brainstorming) — pending implementation plan
**Repo:** github.com/JienWeng/crm-platform

## Goal

Deploy and run a self-hosted [Twenty](https://github.com/twentyhq/twenty) CRM for the
company, where multiple **entities** each get an **isolated** CRM, the system is
**accessible from anywhere** (not VPN-gated), it carries the company's **own
branding** (Quandatics CRM), and the whole deployment is **version-controlled on
GitHub**.

## Requirements (decided during brainstorming)

| # | Requirement | Decision |
|---|-------------|----------|
| R1 | Entity model | **Isolated data per entity** → Twenty **multi-workspace**, one workspace per entity, subdomain-per-entity. |
| R2 | Reachability | **Public** — usable from any network. Login gated by Microsoft Entra SSO. |
| R3 | Hosting substrate | **Existing internal Rocky Linux 9 VPS** at `10.1.10.26` (private IP, behind OpenZiti, public egress `202.186.223.119`). |
| R4 | Scale | 5–15 entities, 25–100 users. |
| R5 | Public ingress | **Port-forward (DNAT) 443+80** on the gateway → VPS. Enables a true wildcard. |
| R6 | Branding | **Custom — "Quandatics CRM"**, applied by us via the repo's rebrand pipeline (light cosmetic rebrand, no fork of Twenty internals). |
| R7 | Version control | Everything in **GitHub** (`JienWeng/crm-platform`); secrets never committed. |
| R8 | Auth | **Entra SSO only** (`AUTH_PASSWORD_ENABLED=false`), single tenant, one centralized callback. |

## Non-goals

- No VPN-only deployment (R2 makes it public).
- No Vercel / external CDN for the frontend (evaluated and rejected: wildcard-on-Vercel
  needs Vercel nameservers, which conflicts with the Cloudflare-managed zone needed for
  the API cert; and a CDN adds no value here).
- No forking/modifying Twenty's application internals — cosmetic rebrand only, to keep
  upgrades cheap and stay on the AGPL core.
- No per-workspace SAML; we use the global Entra-env approach for all workspaces.

## Architecture

```
   Users anywhere (any WiFi/4G)  ── https ──►  Cloudflare DNS (zone: quandatics.dpdns.org)
        grey-cloud / DNS-only A records:
          api.quandatics.dpdns.org    ─┐
          app.quandatics.dpdns.org    ─┤──►  202.186.223.119  (public egress IP)
          *.app.quandatics.dpdns.org  ─┘        │  port-forward 443+80 (DNAT)
                                                 ▼
                                       VPS 10.1.10.26 — Docker Compose:
                                         caddy   (only thing exposed; 443/80)
                                            ├─ *.app.…  → static rebranded frontend (file_server, SPA fallback)
                                            └─ api.…    → reverse_proxy → twenty-server:3000
                                            TLS: ONE Cloudflare DNS-01 wildcard cert (*.app + api)
                                         twenty-server  (NestJS API + GraphQL)
                                         twenty-worker  (background jobs)
                                         postgres:16    (all workspaces' data; Docker volume)
                                         redis          (cache / queues)

   Login: Microsoft Entra SSO only — one app registration, callback on api.quandatics.dpdns.org
```

### Key properties
- **Single ingress.** Caddy is the only exposed service; it owns TLS (one wildcard cert
  via Cloudflare DNS-01 — issuance needs no inbound), file-serves the frontend on every
  `*.app` host, and reverse-proxies the API. Server/worker/Postgres/Redis are internal to
  the Docker network.
- **Entities = workspaces, one per subdomain.** `acme.app.quandatics.dpdns.org`,
  `sales.app.quandatics.dpdns.org`, … each fully data-isolated. The wildcard cert + wildcard
  DNS mean **adding an entity is just creating a workspace in the admin UI** — no DNS/cert
  work per entity.
- **`app.quandatics.dpdns.org`** is the default landing workspace (`DEFAULT_SUBDOMAIN=app`).
- **Public, Entra-gated.** No VPN. The only way in is a Microsoft login from the single tenant.

## Components

| Component | Image / source | Notes |
|-----------|----------------|-------|
| Caddy | `ghcr.io/caddybuilds/caddy-cloudflare:latest` | Has the Cloudflare DNS module for DNS-01. |
| twenty-server | `twentycrm/twenty:v2.8.3` | API + GraphQL; runs DB migrations on boot. |
| twenty-worker | `twentycrm/twenty:v2.8.3` | Background jobs; `DISABLE_DB_MIGRATIONS=true`. |
| postgres | `postgres:16` | DB name `default`; persistent Docker volume. |
| redis | `redis` | Cache/queues. |
| frontend bundle | built from `twentyhq/twenty@v2.8.3` + `rebrand.sh` | Static; **must** match backend TAG. |

**TAG discipline:** frontend build tag and backend image tag are both **`v2.8.3`** and must
move together on every upgrade (mismatch → GraphQL schema errors). *(Note: the prior `.env`
on the box had an invalid `v0.62.0`; current upstream is v2.x.)*

## Configuration (`backend/.env`, secrets excluded)

```
SERVER_IMAGE=twentycrm/twenty
TAG=v2.8.3
SERVER_URL=https://api.quandatics.dpdns.org
FRONTEND_URL=https://app.quandatics.dpdns.org
API_DOMAIN=api.quandatics.dpdns.org
FRONTEND_WILDCARD_DOMAIN=*.app.quandatics.dpdns.org

IS_MULTIWORKSPACE_ENABLED=true
IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true
DEFAULT_SUBDOMAIN=app

AUTH_MICROSOFT_ENABLED=true
AUTH_MICROSOFT_CLIENT_ID=bb6e92e4-571b-4a83-8026-66e1211fee73
AUTH_MICROSOFT_CALLBACK_URL=https://api.quandatics.dpdns.org/auth/microsoft/redirect
AUTH_MICROSOFT_APIS_CALLBACK_URL=https://api.quandatics.dpdns.org/auth/microsoft-apis/get-access-token
AUTH_PASSWORD_ENABLED=false

# Generated on the VPS, never committed:
PG_DATABASE_PASSWORD=<openssl rand>
ENCRYPTION_KEY=<openssl rand -base64 32>
# Provided by the user, never committed:
CLOUDFLARE_API_TOKEN=<secret>
AUTH_MICROSOFT_CLIENT_SECRET=<secret>
```

Single Entra tenant is enforced by the app registration's *Supported account types =
Single tenant* (Twenty has no tenant env var). Tenant ID `8af4cff3-6ddb-47dc-95e3-1ef13b51a21a`.

## Branding (Quandatics CRM)

Applied via `frontend/rebrand.sh` + `frontend/brand-assets/`:
- App name / window title → **Quandatics CRM**
- Logo + favicon → generated Quandatics wordmark/monogram assets (replaceable by a
  designer later)
- Primary accent color + login-screen copy

Cosmetic only; no changes to Twenty application code.

## Frontend build & GitHub workflow

The custom-branded frontend must be **built off-box** (build needs ~8 GB RAM; the VPS has
4 GB). The static bundle is then served by Caddy on the VPS.

```
 repo: github.com/JienWeng/crm-platform
   backend/    docker-compose.yml, Caddyfile, .env.example (NO secrets), backup.sh
   frontend/   rebrand.sh, brand-assets/   (brand source of truth)
   .github/workflows/deploy.yml   ← CI: build rebranded bundle @ v2.8.3, ship to VPS

 push to main ──► GitHub Actions ──► build frontend @ v2.8.3 ──► deploy bundle to VPS dir Caddy serves
 backend change ─► git pull on VPS ──► docker compose up -d
```

- **Secrets out of git:** `.env` is git-ignored, lives only on the VPS. CI uses GitHub
  repository secrets (Cloudflare token, deploy SSH key).
- **Branch model:** simple — work on `main`, CI deploys on push.
- **Fallback for first launch:** build once on a Mac (≥8 GB) and rsync the bundle to the
  VPS; migrate to CI after.

## Operations

- **Add an entity:** admin UI → create workspace → instantly live at
  `<entity>.app.quandatics.dpdns.org` (wildcard cert + DNS already cover it). Zero infra steps.
- **Backups:** `backup.sh` → nightly `pg_dump` (gzip), keep last 14, via cron. Covers all
  workspaces at once.
- **Upgrades:** bump `TAG` in `.env` + repo → `docker compose pull && up -d`; CI rebuilds
  the frontend at the same tag.
- **Verify:** `curl -I https://api.quandatics.dpdns.org/healthz` → 200, valid TLS; sign in
  via "Continue with Microsoft"; create a second workspace and confirm subdomain routing.

## Out-of-band tasks (owned by the user / their team)

1. **Network:** port-forward inbound `443`+`80` on `202.186.223.119` → `10.1.10.26`.
2. **Cloudflare DNS:** three DNS-only (grey-cloud) A records — `api`, `app`, `*.app` →
   `202.186.223.119`.
3. **Azure:** add redirect URI `https://api.quandatics.dpdns.org/auth/microsoft/redirect`
   to app registration `bb6e92e4-…` (Supported account types = single tenant).
4. **Secrets:** provide Cloudflare API token (Zone→DNS→Edit) + Entra client secret.
5. **Capacity (recommended):** bump VPS RAM to 8–16 GB for the stated scale.

## Risks / open items

- **RAM:** 4 GB is tight for 25–100 users; recommend 8–16 GB before real load (R5/R4).
- **Firewall change:** depends on network team approving the port-forward (R5).
- **Multi-workspace subdomain login** has had upstream quirks
  ([twenty#13263](https://github.com/twentyhq/twenty/issues/13263)); smoke-test subdomain
  login and approved-domain auto-join before onboarding entities.
- **Licensing:** Twenty core is AGPLv3; cosmetic rebrand + self-host stays on the AGPL
  core. Avoid `@license Enterprise` files in production without a subscription.
```
