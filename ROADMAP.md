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
- ☐ If any Tier 3: fork `twentyhq/twenty` → `yourorg/twenty`, branch `company-main`
  off the current release tag (v2.8.3). Add `upstream` remote.

## Phase 2 — Provisioning (company infra)
- ☐ Backend VPS on the local server: Ubuntu/Debian, ≥4 GB RAM, Docker, VPN reachable.
- ☐ Register domain; DNS on Cloudflare; create Zone:DNS:Edit API token.
- ☐ DNS: `api` A-record → VPS internal/VPN IP (grey cloud); `app` CNAME → CDN (later).
- ☐ Choose static host: Azure Static Web Apps **or** Vercel; get a deploy token.

## Phase 3 — Backend live
- ☐ Copy `backend/` to the VPS (`/opt/twenty/backend`), fill `.env`
  (generate `ENCRYPTION_KEY`, set passwords, domains, Cloudflare token).
- ☐ `docker compose up -d`; watch Caddy issue the cert.
- ☐ Verify `curl -I https://api.ourco.com/healthz` from a VPN client.
- ☐ Schedule `backup.sh` via cron.

## Phase 4 — Frontend live
- ☐ (Optional) drop brand assets in `frontend/brand-assets/`, set `APP_NAME`.
- ☐ `frontend/build-and-deploy.sh` with matching `TAG`/`REF` + `REACT_APP_SERVER_BASE_URL=https://api.ourco.com`.
- ☐ Set custom domain `app.ourco.com` on the static host; create the CNAME.
- ☐ Run the 7-step verification in `README.md`.

## Phase 5 — Custom features (only if Tier 2/3)
- ☐ Tier 2 Apps: scaffold, `yarn twenty dev`, test, `app:publish --private --remote production`.
- ☐ Tier 3: build code on `company-main`, run CI-equivalent tests, build+push custom
  server image (`backend/build-image.sh`), redeploy backend + frontend from same ref.

## Phase 6 — Operating rhythm
- ☐ Upgrades: bump `TAG` (or rebase fork onto new tag) → pull/up backend → rebuild
  & redeploy frontend at the same ref. Back up first.
- ☐ Monitor: Caddy logs, `docker compose ps`, disk usage, backup retention.
- ☐ Consider S3 storage (`STORAGE_TYPE=s3`) before heavy file/attachment use.
- ☐ Consider SMTP + SSO (Google/Microsoft) env vars when onboarding real users.

## Open decisions to revisit
- Static host: Azure SWA vs Vercel (cost/governance).
- Whether to host the frontend internally too (simpler, since users are on VPN anyway).
- Multi-workspace (`IS_MULTIWORKSPACE_ENABLED`) — single vs many workspaces.
