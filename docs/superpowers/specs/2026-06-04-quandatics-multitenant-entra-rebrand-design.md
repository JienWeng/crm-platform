# Quandatics CRM — Multi-workspace + Entra-only SSO + Rebrand

**Date:** 2026-06-04
**Status:** Design approved (pending written-spec review)
**Repo role:** This repository is the *deployment & documentation kit* for a self-hosted
Twenty CRM. Application code lives in a fork of `twentyhq/twenty`. This spec changes the
kit (docs, compose, Caddy, frontend build, rebrand assets) and describes the fork work.

---

## 1. Goal

Turn the current **single-workspace** Quandatics deployment into a **multi-workspace**
instance where:

1. Multiple workspaces run on one instance using **Twenty's native multi-workspace**
   feature (subdomain-per-workspace).
2. **All authentication is Microsoft Entra ID** — SSO-only, no passwords, no Google.
3. The product is **rebranded to Quandatics** at a "medium" depth (assets + user-visible
   strings + the invitation email), maintained as a fork patch over the pinned tag.

All users come from **one Entra tenant** (one organization). This is *not* SaaS for
external customers — it is one company running several workspaces (teams / clients /
departments) on shared infrastructure.

Grounded in Twenty's official docs:
<https://docs.twenty.com/developers/self-host/capabilities/setup>

---

## 2. Decisions (locked)

| Area | Decision |
|---|---|
| Tenancy | Twenty native multi-workspace (`IS_MULTIWORKSPACE_ENABLED=true`); subdomain routing; workspace creation locked to server admins |
| Auth | Entra-only SSO; single-tenant Azure app registration; `AUTH_PASSWORD_ENABLED=false`; Google left disabled |
| Access | Per-workspace approved-domain auto-join + invitations for guests |
| Rebrand | Medium: assets + user-visible strings + invite email, as a maintained fork patch over `v2.8.3` |
| Hosting / TLS | Frontend served by Caddy on the VPS; `*.app.ourco.com` wildcard cert via Cloudflare DNS-01 (no CDN, no Azure SWA) |

---

## 3. Architecture

```
   VPN / local users
        │  https
        ▼
   *.app.ourco.com  ─┐
   api.ourco.com    ─┴────►  Caddy (TLS via Cloudflare DNS-01, wildcard)
                                 │   ├─ *.app.ourco.com → static twenty-front bundle (file server)
                                 │   └─ api.ourco.com   → twenty-server :3000 (reverse proxy)
                                 │
                                 ├─ worker
                                 ├─ postgres:16
                                 └─ redis
```

Key points:

- **One Caddy, one wildcard cert.** Caddy already runs the Cloudflare DNS-01 challenge for
  `api.ourco.com`; adding a wildcard `*.app.ourco.com` site block is the only new TLS work.
  DNS-01 is the only ACME flow that issues wildcards, and it needs no public inbound.
- **One static frontend bundle serves every workspace.** `twenty-front` is built once with
  `REACT_APP_SERVER_BASE_URL=https://api.ourco.com`. The browser's subdomain
  (`acme.app.ourco.com`) tells the server which workspace; the bundle itself is
  workspace-agnostic. Caddy serves the same files on every `*.app.ourco.com` host.
- **Auth callback stays centralized on the API domain.** Entra redirects to
  `https://api.ourco.com/auth/microsoft/redirect` only — there are **no per-workspace
  redirect URIs**. After login the server redirects the browser back to the correct
  workspace subdomain.

### DNS
- `api`  → A record → VPS VPN/internal IP (grey cloud).
- `*.app` → A record (wildcard) → same VPS IP. (`app.ourco.com` is the default landing
  subdomain, `DEFAULT_SUBDOMAIN=app`.)

### What is NOT used
- No Azure Static Web Apps / Vercel / CDN for the frontend (rejected: SWA needs Standard
  tier + Azure Front Door to do wildcard subdomains, which is more cost + config than Caddy
  does for free, and a CDN gives no benefit to VPN-only users).

---

## 4. Backend configuration (`backend/docker-compose.yml` + `.env`)

Enable (currently commented) and add:

```sh
# Multi-workspace
IS_MULTIWORKSPACE_ENABLED=true
IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true
DEFAULT_SUBDOMAIN=app
FRONTEND_URL=https://app.ourco.com        # base the server uses to build per-workspace URLs

# Entra-only auth
AUTH_MICROSOFT_ENABLED=true
AUTH_MICROSOFT_CLIENT_ID=<application-client-id>
AUTH_MICROSOFT_CLIENT_SECRET=<client-secret-value>
AUTH_MICROSOFT_CALLBACK_URL=https://api.ourco.com/auth/microsoft/redirect
AUTH_MICROSOFT_APIS_CALLBACK_URL=https://api.ourco.com/auth/microsoft-apis/get-access-token
AUTH_PASSWORD_ENABLED=false               # SSO-only
# Google intentionally left disabled (AUTH_GOOGLE_ENABLED unset/false)
```

- A `.env.example` for `backend/` is **created** (referenced today but missing).
- `IS_CONFIG_VARIABLES_IN_DB_ENABLED=false` so `.env` stays authoritative.

> **To verify during local test (§8):** the exact mechanism the server uses to build
> per-workspace subdomain URLs (`FRONTEND_URL` base + `DEFAULT_SUBDOMAIN`), and whether
> per-workspace approved-domain auto-join behaves as it does in single-workspace mode.

---

## 5. Caddy (`backend/Caddyfile`)

Add a wildcard site block for the frontend alongside the existing API block:

- `api.ourco.com` → `reverse_proxy server:3000` (unchanged; honors `X-Forwarded-Proto`).
- `*.app.ourco.com` → `file_server` (or `try_files` SPA fallback to `/index.html`) over the
  built `twenty-front` static files, mounted into the Caddy container.
- TLS: `tls { dns cloudflare {env.CLOUDFLARE_API_TOKEN} }`, requesting a wildcard cert for
  `*.app.ourco.com` (and the existing cert for `api.ourco.com`).

The frontend build output is mounted into Caddy (bind mount or shared volume) rather than
pushed to a CDN.

---

## 6. Entra ID app registration

Minimal change from current `CONFIGURE.md`:

- **Single tenant** account type (scopes login to your org — Twenty has no tenant env var).
- Redirect URIs (type `Web`), both on the **API** domain:
  - `https://api.ourco.com/auth/microsoft/redirect`
  - `https://api.ourco.com/auth/microsoft-apis/get-access-token` (only if mail/calendar sync
    is later enabled)
- Graph delegated scopes: `openid`, `email`, `profile`, `User.Read`; admin consent granted.
- Behavioral change vs. today: enforce **SSO-only** (`AUTH_PASSWORD_ENABLED=false`).
- No per-workspace redirect URIs (auth is centralized).

---

## 7. Rebrand — Quandatics (medium, maintained fork)

ROADMAP Phase 1 already anticipates the fork. Concretely:

1. Fork `twentyhq/twenty` → `quandatics/twenty`; branch `company-main` off tag **v2.8.3**;
   add `upstream` remote.
2. **Assets** (via extended `frontend/rebrand.sh` + populated `frontend/brand-assets/`,
   mirroring `twenty-front`'s tree): favicon, app/login logo, `manifest.json`
   name/short_name/icons, OG/meta tags, `<title>`.
3. **User-visible strings** as a tracked patch over the tag:
   - `twenty-front`: login screen text, page titles, error pages, default new-workspace name.
   - `twenty-server`: transactional **email templates** (the invitation email especially).
4. Build a **custom server image** via `backend/build-image.sh`; build the frontend from the
   **same ref**; set `SERVER_IMAGE`/`TAG` in `backend/.env` to the custom image.

This moves the deployment from "pinned upstream image" to **Tier 3** (custom build). The
rebrand patch must be re-applied / rebased on every upstream bump — documented as an
operating-rhythm step in `CUSTOMIZING.md`.

---

## 8. Validation & rollout

Order matters; validate locally before prod.

1. **Local multi-workspace smoke test** (`local-dev/`): set `IS_MULTIWORKSPACE_ENABLED=true`
   and exercise subdomains via `*.localhost` (e.g. `app.localhost`, `acme.app.localhost`).
   Confirms login still works — guards against upstream issue
   [#13263](https://github.com/twentyhq/twenty/issues/13263) where enabling multi-workspace
   broke login when subdomains/redirects weren't set up.
2. **Verify URL-building + auto-join** behavior (the two items flagged in §4).
3. **Rebrand build**: apply patch + assets, build custom image, run locally, eyeball
   branding (login, title, favicon, invite email).
4. **Backend prod**: wildcard DNS, Caddy wildcard cert issuance, Entra env, bring up stack,
   `curl -I https://api.ourco.com/healthz`.
5. **Frontend prod**: build → Caddy-served dir; load `app.ourco.com`, sign in with Microsoft,
   create a second workspace as server admin, confirm it routes to its subdomain.
6. **Full 7-step verification** from `README.md`, extended for the second workspace.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| `IS_MULTIWORKSPACE_ENABLED` breaks login (upstream #13263) | Local subdomain smoke test before prod (§8.1) |
| Per-workspace domain auto-join behaves differently in multi-workspace | Verify in local test; fall back to invitation-only if needed |
| Fork rebrand patch drifts on upstream bumps | Documented rebase step in `CUSTOMIZING.md`; keep patch minimal |
| Wildcard cert issuance / DNS propagation | Cloudflare DNS-01 already proven for `api`; test issuance in staging |
| Server URL-building var assumptions wrong | Explicit verify step (§4 note) before prod |

---

## 10. Files changed in this repo (deliverable)

- `CONFIGURE.md` — rewrite §1 (Entra multi-workspace, SSO-only) and §2 (access =
  multi-workspace domain auto-join + invite); add subdomain model.
- `README.md` — architecture diagram → `*.app.ourco.com` wildcard behind Caddy; rebrand wording.
- `ROADMAP.md` — resolve the "single vs many workspace" open decision; fold in Entra-only +
  medium rebrand; drop CDN/SWA-vs-Vercel open item.
- `backend/docker-compose.yml` — enable multi-workspace + Entra vars; add `DEFAULT_SUBDOMAIN`,
  `FRONTEND_URL`, `AUTH_PASSWORD_ENABLED=false`.
- `backend/Caddyfile` — add `*.app.ourco.com` static site block + wildcard TLS.
- `backend/.env.example` — **new**; all vars above.
- `frontend/build-and-deploy.sh` — output to a Caddy-served dir instead of CDN push.
- `frontend/rebrand.sh` + `frontend/brand-assets/` — extend for medium rebrand; populate assets.
- `CUSTOMIZING.md` — note rebrand is now a maintained Tier-3 patch + rebase-on-bump step.

---

## 11. Out of scope

- External-customer SaaS (multiple Entra tenants), per-workspace SAML/OIDC, separate
  instance-per-tenant — all rejected during brainstorming.
- Mail/calendar sync (Outlook) — vars noted but left disabled; can be enabled later.
- S3 storage migration — independent decision, unchanged here.
</content>
</invoke>
