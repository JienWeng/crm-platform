# Backend — Twenty server on the VPN VPS

Runs `server` + `worker` + `postgres:16` + `redis` + `caddy` (TLS) via Docker Compose.
Only Caddy is exposed (443/80): it reverse-proxies `https://api.ourco.com` to the app
server and file-serves the static frontend on `https://*.app.ourco.com` (one bundle per
workspace subdomain) under a single Cloudflare DNS-01 wildcard cert. The app server is
reachable only inside the compose network and only on the VPN.

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
`api.ourco.com` pointing at this server's VPN/internal IP**, plus a **wildcard
`*.app.ourco.com` A record at the same IP** (multi-workspace frontend), both set
DNS-only in Cloudflare. Caddy needs the Cloudflare token only to solve the DNS-01
challenge — it does not need public inbound traffic.

## Deploy on Rocky Linux / RHEL

The `get.docker.com` one-liner above is for Ubuntu/Debian. On Rocky Linux (and
RHEL/AlmaLinux) three things differ: packages come from **`dnf`**, the firewall is
**`firewalld`**, and **SELinux is enforcing** — it silently denies containers
read access to bind-mounted host dirs (the `Caddyfile` and the frontend dir)
until you relabel them. Assumes Rocky Linux 9.

```sh
# 1. Base tools (semanage ships in policycoreutils-python-utils) + a deploy user
sudo dnf -y update
sudo dnf -y install git rsync policycoreutils-python-utils
sudo useradd -m -s /bin/bash deploy && sudo passwd deploy
#    add your SSH public key to /home/deploy/.ssh/authorized_keys

# 2. Docker CE + Compose v2 (Docker's CentOS repo is RHEL-compatible; NOT podman)
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker deploy          # re-login (or `newgrp docker`) to take effect

# 3. Firewall — open 80/443 (Docker often bypasses firewalld zones, but be explicit)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# 4. Put this folder on the VPS, e.g. /opt/quandatics/crm-platform/backend
sudo mkdir -p /opt/quandatics && sudo chown deploy:deploy /opt/quandatics
#    (as deploy) git clone <your fork>.git /opt/quandatics/crm-platform   — or rsync backend/
cd /opt/quandatics/crm-platform/backend
cp .env.example .env
```

**SELinux — the critical RHEL step.** Label both bind-mount sources
`container_file_t`, or Caddy gets permission-denied even though `ls` works:

```sh
# Frontend dir Caddy serves. A persistent fcontext rule means every file rsync
# drops in later inherits the right label automatically (no relabel per deploy):
sudo mkdir -p /srv/quandatics-front
sudo chown -R deploy:deploy /srv/quandatics-front
sudo semanage fcontext -a -t container_file_t "/srv/quandatics-front(/.*)?"
sudo restorecon -Rv /srv/quandatics-front

# The Caddyfile bind mount (static; re-run if a later `git pull` recreates it):
sudo chcon -t container_file_t /opt/quandatics/crm-platform/backend/Caddyfile
```
> Debug aid only: `sudo setenforce 0` confirms whether SELinux is the cause —
> then `sudo setenforce 1` and fix the labels properly. Don't leave it permissive.

Now fill `.env` and generate secrets exactly as in **One-time setup** (set
`SERVER_IMAGE`/`TAG`, domains, `FRONTEND_WILDCARD_DOMAIN=*.app.ourco.com`,
`CLOUDFLARE_API_TOKEN`, the Entra `AUTH_MICROSOFT_*`, and the `openssl`-generated
keys), then continue with **Launch / operate** and **Verify** below — they are the
same on every distro. Deploy the static frontend from your Mac/CI per
`frontend/` (`DEPLOY=ssh DEPLOY_HOST=deploy@<vps> DEPLOY_DIR=/srv/quandatics-front`);
the `semanage` rule keeps the rsync'd files SELinux-correct.

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
