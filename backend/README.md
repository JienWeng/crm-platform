# Backend — Twenty server on the VPN VPS

Runs `server` + `worker` + `postgres:16` + `redis` + `caddy` (TLS) via Docker Compose.
Only Caddy is exposed (443/80); the app server is reachable only inside the compose
network and, externally, only through `https://api.ourco.com` on the VPN.

## One-time setup

```sh
# 1. Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh

# 2. Put this folder on the VPS, e.g. /opt/twenty/backend, then:
cd /opt/twenty/backend
cp .env.example .env

# 3. Generate secrets and paste into .env
openssl rand -base64 32   # -> ENCRYPTION_KEY

# 4. Edit .env: set TAG, SERVER_URL, FRONTEND_URL, API_DOMAIN,
#    CLOUDFLARE_API_TOKEN, PG_DATABASE_PASSWORD, ENCRYPTION_KEY
nano .env
```

DNS prerequisite (see top-level README → Domain & DNS): an **A record for
`api.ourco.com` pointing at this server's VPN/internal IP**, set DNS-only in
Cloudflare. Caddy needs the Cloudflare token only to solve the DNS-01 challenge —
it does not need public inbound traffic.

## Launch / operate

```sh
docker compose up -d           # start everything
docker compose ps              # status
docker compose logs -f server  # tail server logs
docker compose logs -f caddy   # watch cert issuance
docker compose down            # stop
```

First boot runs DB migrations automatically (server has
`DISABLE_DB_MIGRATIONS` unset; worker has it forced true).

## Verify

```sh
# From a VPN client:
curl -I https://api.ourco.com/healthz   # 200, valid TLS, no cert warning
```

## Backups

```sh
./backup.sh                    # writes ./backups/twenty_<ts>.sql.gz, keeps last 14
```

## Upgrade

```sh
# Bump TAG in .env to the new release, then:
docker compose pull && docker compose up -d
# IMPORTANT: rebuild + redeploy the static frontend at the SAME tag (see frontend/).
```

## Notes / gotchas
- DB name is `default` (Twenty's convention), not `twenty`.
- `SERVER_URL` and `FRONTEND_URL` must both be `https://`.
- No CORS allowlist var exists in Twenty — cross-origin app→api works by default.
- Caddy image `ghcr.io/caddybuilds/caddy-cloudflare` includes the DNS module the
  stock `caddy` image lacks.
