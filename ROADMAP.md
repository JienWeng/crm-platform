# Roadmap — from local preview to customized production

Status legend: ☐ todo · ◐ in progress · ☑ done

## Phase 0 — Local preview (now)
- ◐ Run `local-dev/` stack, open http://localhost:3000, create first workspace.
- ☐ Enable **Early Access → Dashboards** and try the native (no-code) dashboard.
- ☐ Decide per feature you want: Tier 1 (native) / Tier 2 (App) / Tier 3 (fork).
  See `CUSTOMIZING.md`.

## Phase 1 — Decide customization scope
- ☐ List the changes you actually need (dashboards, custom objects, branding…).
- ☐ Classify each into a tier. Goal: keep as much in Tier 1/2 as possible.
- ☐ Rebrand to Quandatics is **Tier 3** (medium: assets + user-visible strings + invite
  email), maintained as a fork patch over the pinned tag. See Phase 5/6.
- ☐ Fork `twentyhq/twenty` → `quandatics/twenty`, branch `company-main` off the current
  release tag (v2.8.3). Add `upstream` remote.

## Phase 2 — Provisioning (company infra)
- ☐ Backend VPS on the local server: Ubuntu/Debian, ≥4 GB RAM, Docker, VPN reachable.
- ☐ Register domain; DNS on Cloudflare; create Zone:DNS:Edit API token.
- ☐ DNS: `api` A-record → VPS internal/VPN IP (grey cloud); `*.app` wildcard A-record →
  same VPS IP (grey cloud). No CDN — Caddy serves the frontend.
- ☐ Entra ID: register a **single-tenant** Azure app; redirect URIs on the API domain only
  (`https://api.ourco.com/auth/microsoft/redirect`); grant `openid email profile User.Read`.

## Phase 3 — Backend live
- ☐ Copy `backend/` to the VPS (`/opt/twenty/backend`), fill `.env`
  (generate `ENCRYPTION_KEY`, set passwords, domains, Cloudflare token).
- ☐ Set multi-workspace + Entra vars: `IS_MULTIWORKSPACE_ENABLED=true`,
  `IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true`, `DEFAULT_SUBDOMAIN=app`,
  `FRONTEND_URL=https://app.ourco.com`, `AUTH_MICROSOFT_*`, `AUTH_PASSWORD_ENABLED=false`
  (SSO-only; Google left disabled).
- ☐ `docker compose up -d`; watch Caddy issue the `api` + `*.app` wildcard certs.
- ☐ Verify `curl -I https://api.ourco.com/healthz` from a VPN client.
- ☐ Schedule `backup.sh` via cron.

## Phase 4 — Frontend live
- ☐ (Optional) drop brand assets in `frontend/brand-assets/`, set `APP_NAME`.
- ☐ `frontend/build-and-deploy.sh` with matching `TAG`/`REF` + `REACT_APP_SERVER_BASE_URL=https://api.ourco.com`;
  output to the Caddy-served dir (mounted into the Caddy container) — no CDN push.
- ☐ Caddy serves the one static bundle on `*.app.ourco.com` (SPA fallback to `/index.html`);
  the subdomain selects the workspace, the bundle is workspace-agnostic.
- ☐ Load `app.ourco.com`, sign in with Microsoft, create a second workspace as server admin,
  confirm it routes to its own subdomain.
- ☐ Run the 7-step verification in `README.md`, extended for the second workspace.

## Phase 5 — Custom features (Tier 2/3 + rebrand)
- ☐ Tier 2 Apps: scaffold, `yarn twenty dev`, test, `app:publish --private --remote production`.
- ☐ Tier 3 rebrand: apply assets + string/email patch on `company-main`, run CI-equivalent
  tests, build+push the custom server image (`backend/build-image.sh`), build the frontend
  from the **same ref**, set `SERVER_IMAGE`/`TAG` to the custom image, redeploy both.

## Phase 6 — Operating rhythm
- ☐ Upgrades: bump `TAG` → rebase the rebrand patch onto the new upstream tag → rebuild
  & push custom image → pull/up backend → rebuild & redeploy frontend at the same ref.
  Back up first. (See the rebase-on-bump step in `CUSTOMIZING.md`.)
- ☐ Monitor: Caddy logs, `docker compose ps`, disk usage, backup retention.
- ☐ Consider S3 storage (`STORAGE_TYPE=s3`) before heavy file/attachment use.
- ☐ Enable Outlook mail/calendar sync (`AUTH_MICROSOFT_APIS_*`) later if needed.
