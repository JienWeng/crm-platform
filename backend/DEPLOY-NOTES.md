# Deploy notes — hard-won gotchas (read before changing prod)

Operational truths discovered bringing the VPS up. Each one cost a debugging cycle.

## 1. Single-tenant Entra → patched image required (AADSTS50194)
Upstream Twenty hardcodes the Microsoft OAuth `tenant: 'common'` endpoint and has
**no tenant env var**. Single-tenant Azure apps reject `/common`. Fix: build the
tenant-pinned overlay and point `SERVER_IMAGE` at it — see `tenant-patch.Dockerfile`.
Verify: `GET https://api.<domain>/auth/microsoft` must 302 to
`login.microsoftonline.com/<tenant-guid>/oauth2/...` (not `/common/...`).
Rebuild the overlay on every Twenty upgrade.

## 2. `FRONTEND_URL` must be the APEX (the `app.app` bug)
Twenty builds workspace URLs as `<subdomain>.<FRONTEND_URL host>`. With
`FRONTEND_URL=https://app.<domain>` + `DEFAULT_SUBDOMAIN=app` you get
`app.app.<domain>`. Use the apex: `FRONTEND_URL=https://<domain>`. Confirm via
`GET https://api.<domain>/client-config` → `"frontDomain":"<domain>"`.

## 3. `.env` changes need `docker compose up -d`, NOT `restart`
`docker compose restart` reuses the container's **baked-in** env — it does not
re-read `.env`. Only `up -d` (recreate) applies `.env` edits. Check with
`docker compose exec server printenv <VAR>`.
- Sub-gotcha: running `up -d` while the server is mid-reboot can leave `caddy`/
  `worker` in **"Created"** (Caddy waits for `server: healthy`). Re-run `up -d`
  once the server is healthy, or check `docker compose ps`.

## 4. `SERVER_IMAGE` must NOT contain a tag
Compose resolves the image as `${SERVER_IMAGE}:${TAG}`. Putting a tag in
`SERVER_IMAGE` (e.g. `quandatics/twenty:v2.8.3-tenant`) yields the invalid
`...:v2.8.3-tenant:v2.8.3`, and compose silently keeps the old container. Keep
`SERVER_IMAGE=quandatics/twenty`, `TAG=v2.8.3`.

## 5. Slow boot on 4 GB RAM
The server runs several sequential setup phases, each booting a full Nest context
(~2 min each on 2 cores / 4 GB) → ~4–12 min total per recreate, and it can wedge
Docker. **Bump the VPS to 8–16 GB** before real load — it's the single biggest
reliability + iteration-speed win.

## 6. DNS rebind: private IP + public domain ⇒ clients can't resolve it
Pointing `*.<domain>` at the private `10.1.10.26` means public DNS returns an
RFC1918 address; OS/router resolvers drop it (DNS-rebind protection) even though
`dig` shows it. The page is reachable by IP but not by name. Options:
- **Production:** port-forward 443/80 to the box + public DNS → the public IP.
  Then names resolve from anywhere, no hacks.
- **Internal:** a split-horizon resolver on the VPN authoritative for `*.<domain>`.
- **Test-only stopgap:** per-host `/etc/hosts` entries on each client (does NOT
  scale to many workspaces).

## 7. Rebranded frontend (deferred)
Prod currently serves Twenty's **built-in** frontend via `reverse_proxy` (stock
branding) so login works without a build. The intended end-state builds the
Quandatics-rebranded `twenty-front` static bundle (Node 24.15 + Yarn 4, ~8 GB RAM
— not the 4 GB VPS; use CI or a build box) and serves it via `file_server` on the
workspace hosts. See `frontend/` + `.github/workflows/deploy-frontend.yml`.
