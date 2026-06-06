# Twenty CRM Self-Host Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a public, multi-entity (multi-workspace), Entra-SSO-only, Quandatics-branded Twenty CRM on the existing Rocky Linux VPS (`10.1.10.26`), version-controlled on GitHub with CI building the frontend.

**Architecture:** Docker Compose on the VPS runs Caddy (single ingress, TLS via Cloudflare DNS-01 wildcard) + twenty-server + twenty-worker + postgres:16 + redis. Caddy file-serves a custom-branded static frontend on `*.app.quandatics.dpdns.org` and reverse-proxies `api.quandatics.dpdns.org` → server. Public reach comes from a gateway port-forward (443+80) to the private box. The branded frontend bundle is built off-box (GitHub Actions, or a Mac for first launch) because the build needs ~8 GB RAM.

**Tech Stack:** Twenty `v2.8.3` (`twentycrm/twenty`), Docker Compose, Caddy (caddy-cloudflare), Postgres 16, Redis, Cloudflare DNS, Microsoft Entra ID, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-06-twenty-crm-self-host-design.md`

**Conventions used in this plan:**
- VPS commands run through the existing SSH master socket: `SSH="ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26"`. If a command returns `Control socket ... No such file`, re-open the master in a normal terminal: `ssh -fN -M -o ControlPath=~/.ssh/cm-vps -o ControlPersist=4h internalops@10.1.10.26`.
- Domain: `quandatics.dpdns.org` → `api.`, `app.`, `*.app.`. Public IP `202.186.223.119`, VPS `10.1.10.26`.

---

## ⛳ Prerequisites — out-of-band, owned by the user/their team (GATE before Phase 3+)

These are NOT agent tasks. The backend cert (Task 9) and public verification (Task 11) are blocked until they're done. Track them but don't attempt to perform them.

- [ ] **P1. Port-forward** inbound `443` + `80` on the gateway (`202.186.223.119`) → `10.1.10.26`.
- [ ] **P2. Cloudflare DNS** in zone `quandatics.dpdns.org`, all **DNS-only (grey cloud)**:
  - `api`  A → `202.186.223.119`
  - `app`  A → `202.186.223.119`
  - `*.app` A → `202.186.223.119`
- [ ] **P3. Azure** app registration `bb6e92e4-571b-4a83-8026-66e1211fee73`: add Redirect URI (type Web) `https://api.quandatics.dpdns.org/auth/microsoft/redirect`; confirm *Supported account types = Single tenant*; under API permissions grant `openid email profile User.Read`.
- [ ] **P4. Secrets** handed over (into the VPS `.env` directly, or to the agent): `CLOUDFLARE_API_TOKEN` (Zone→DNS→Edit on this zone) and `AUTH_MICROSOFT_CLIENT_SECRET`.
- [ ] **P5. (Recommended) RAM** bump the VPS to 8–16 GB on the hypervisor.

---

## Phase 1 — Quandatics brand assets (local Mac, no external deps)

### Task 1: Create the Quandatics SVG brand assets

**Files:**
- Create: `frontend/brand-assets/src/assets/logo-square.svg`
- Create: `frontend/brand-assets/src/assets/logo.svg`
- Create: `frontend/brand-assets/src/assets/login-logo.svg`
- Create: `frontend/brand-assets/public/images/placeholders/og-image.svg` (source for the PNG)

- [ ] **Step 1: Write the square monogram** `frontend/brand-assets/src/assets/logo-square.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Quandatics">
  <defs>
    <linearGradient id="qg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2348C7"/>
      <stop offset="1" stop-color="#18B8A6"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#qg)"/>
  <circle cx="256" cy="248" r="120" fill="none" stroke="#ffffff" stroke-width="44"/>
  <line x1="300" y1="292" x2="372" y2="364" stroke="#ffffff" stroke-width="44" stroke-linecap="round"/>
</svg>
```

- [ ] **Step 2: Write the horizontal wordmark** `frontend/brand-assets/src/assets/logo.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 200" role="img" aria-label="Quandatics">
  <defs>
    <linearGradient id="qg2" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2348C7"/>
      <stop offset="1" stop-color="#18B8A6"/>
    </linearGradient>
  </defs>
  <rect x="20" y="36" width="128" height="128" rx="30" fill="url(#qg2)"/>
  <circle cx="84" cy="96" r="34" fill="none" stroke="#ffffff" stroke-width="12"/>
  <line x1="98" y1="110" x2="118" y2="130" stroke="#ffffff" stroke-width="12" stroke-linecap="round"/>
  <text x="180" y="128" font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
        font-size="92" font-weight="700" fill="#1A2B4A">Quandatics</text>
</svg>
```

- [ ] **Step 3: Write the login logo** `frontend/brand-assets/src/assets/login-logo.svg` (reuse the wordmark — copy the Step 2 content verbatim into this file).

- [ ] **Step 4: Write the OG image source** `frontend/brand-assets/public/images/placeholders/og-image.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" role="img" aria-label="Quandatics CRM">
  <rect width="1200" height="630" fill="#0E1A33"/>
  <rect x="92" y="232" width="166" height="166" rx="40" fill="#18B8A6"/>
  <circle cx="175" cy="307" r="44" fill="none" stroke="#ffffff" stroke-width="16"/>
  <line x1="193" y1="325" x2="219" y2="351" stroke="#ffffff" stroke-width="16" stroke-linecap="round"/>
  <text x="300" y="330" font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
        font-size="92" font-weight="700" fill="#ffffff">Quandatics CRM</text>
  <text x="300" y="396" font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
        font-size="38" fill="#9FB3D1">Self-hosted customer relationship management</text>
</svg>
```

- [ ] **Step 5: Verify the SVGs are well-formed**

Run: `for f in frontend/brand-assets/src/assets/logo-square.svg frontend/brand-assets/src/assets/logo.svg frontend/brand-assets/src/assets/login-logo.svg frontend/brand-assets/public/images/placeholders/og-image.svg; do xmllint --noout "$f" && echo "OK $f"; done`
Expected: four `OK …` lines, no parse errors. (If `xmllint` is absent: `for f in …; do python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1]); print('OK',sys.argv[1])" "$f"; done`.)

### Task 2: Rasterize favicons + PWA icons from the monogram

**Files:**
- Create: `frontend/brand-assets/public/favicon-16x16.png`, `favicon-32x32.png`
- Create: `frontend/brand-assets/public/favicon.ico`
- Create: `frontend/brand-assets/public/icons/apple-touch-icon.png` (180), `android-chrome-192x192.png`, `android-chrome-512x512.png`
- Create: `frontend/brand-assets/public/images/placeholders/og-image.png`

- [ ] **Step 1: Pick an available rasterizer**

Run: `command -v rsvg-convert || command -v magick || command -v convert || command -v inkscape || echo "NONE"`
Expected: a path. If `NONE`, install one: `brew install librsvg` (gives `rsvg-convert`). The commands below assume `rsvg-convert`; ImageMagick equivalents are `magick input.svg -resize NxN output.png`.

- [ ] **Step 2: Generate the PNG icon sizes from the monogram**

```bash
cd frontend/brand-assets
SQ=src/assets/logo-square.svg
rsvg-convert -w 16  -h 16  "$SQ" -o public/favicon-16x16.png
rsvg-convert -w 32  -h 32  "$SQ" -o public/favicon-32x32.png
rsvg-convert -w 180 -h 180 "$SQ" -o public/icons/apple-touch-icon.png
rsvg-convert -w 192 -h 192 "$SQ" -o public/icons/android-chrome-192x192.png
rsvg-convert -w 512 -h 512 "$SQ" -o public/icons/android-chrome-512x512.png
rsvg-convert -w 1200 -h 630 public/images/placeholders/og-image.svg -o public/images/placeholders/og-image.png
cd ../..
```

- [ ] **Step 3: Build the multi-size favicon.ico**

```bash
cd frontend/brand-assets/public
# ImageMagick makes a proper multi-res .ico:
magick favicon-16x16.png favicon-32x32.png favicon.ico 2>/dev/null \
  || convert favicon-16x16.png favicon-32x32.png favicon.ico
cd ../../..
```
(If no ImageMagick: ship `favicon-32x32.png` and skip `.ico` — Twenty references PNG favicons too; note it and continue.)

- [ ] **Step 4: Verify all asset files exist and are non-empty**

Run: `find frontend/brand-assets -type f ! -name 'README*' -size +0c | sort`
Expected: lists the 4 SVGs + 6 PNGs (+ favicon.ico if generated) — at least 10 files.

- [ ] **Step 5: Commit the brand assets**

```bash
git add frontend/brand-assets
git commit -m "brand: add Quandatics CRM logo, favicons, PWA icons, og-image"
```

---

## Phase 2 — GitHub baseline + CI (local Mac)

### Task 3: Add the GitHub Actions frontend build-and-deploy workflow

**Files:**
- Create: `.github/workflows/deploy-frontend.yml`

- [ ] **Step 1: Write the workflow** `.github/workflows/deploy-frontend.yml`

```yaml
name: Build & deploy Quandatics frontend
on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - '.github/workflows/deploy-frontend.yml'
  workflow_dispatch: {}

concurrency:
  group: frontend-deploy
  cancel-in-progress: true

env:
  TAG: v2.8.3
  REACT_APP_SERVER_BASE_URL: https://api.quandatics.dpdns.org

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '24.15.x'

      - name: Enable corepack (Yarn 4)
        run: corepack enable

      - name: Add VPS to known_hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -H "${{ secrets.DEPLOY_HOST_IP }}" >> ~/.ssh/known_hosts

      - name: Load deploy SSH key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.DEPLOY_SSH_KEY }}

      - name: Build rebranded bundle and rsync to VPS
        env:
          DEPLOY: ssh
          DEPLOY_HOST: ${{ secrets.DEPLOY_SSH_USER_HOST }}
          DEPLOY_DIR: /srv/quandatics-front
        run: |
          cd frontend
          chmod +x build-and-deploy.sh rebrand.sh
          ./build-and-deploy.sh
```

- [ ] **Step 2: Document the required GitHub repository secrets** — append to `frontend/README.md` (or create `.github/README.md`) a short block listing the secrets CI needs (so they're not guessed):

```markdown
## CI secrets (Settings → Secrets and variables → Actions)
- `DEPLOY_SSH_KEY`        — private key whose public half is in the VPS deploy user's authorized_keys
- `DEPLOY_SSH_USER_HOST`  — e.g. internalops@202.186.223.119  (must be reachable from GitHub runners; requires P1 port-forward of port 22 OR a self-hosted runner on the VPN)
- `DEPLOY_HOST_IP`        — 202.186.223.119
```

> ⚠️ Decision note for execution: GitHub-hosted runners can only reach the VPS if SSH (22) is also exposed publicly, which we do NOT want. Two clean options — record which is chosen during execution: **(a)** use a **self-hosted GitHub runner** on the VPS/VPN (recommended; runner dials out, no inbound 22), or **(b)** CI uploads the built bundle as an artifact and a cron/pull step on the VPS fetches it. Task 10 covers the first manual build regardless, so CI can be finalized after launch.

- [ ] **Step 3: Verify the workflow YAML parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy-frontend.yml')); print('YAML OK')"`
Expected: `YAML OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-frontend.yml frontend/README.md
git commit -m "ci: add GitHub Actions workflow to build + deploy rebranded frontend"
```

### Task 4: Land the branch on main (GitHub = source of truth)

- [ ] **Step 1: Push the working branch**

```bash
git push -u origin deploy/twenty-crm-selfhost
```
Expected: branch pushed; a PR URL is printed.

- [ ] **Step 2: Open a PR**

```bash
gh pr create --base main --head deploy/twenty-crm-selfhost \
  --title "Deploy: Quandatics CRM (multi-entity, public, Entra SSO)" \
  --body "Implements docs/superpowers/specs/2026-06-06-twenty-crm-self-host-design.md — brand assets, CI, and deployment of self-hosted Twenty."
```
Expected: PR created.

- [ ] **Step 3: Verify** the PR exists and CI (if any path matched) is green or pending.

Run: `gh pr view --json number,state,mergeable`
Expected: JSON with `"state":"OPEN"`. (Merge to `main` happens in Task 13 after verification.)

---

## Phase 3 — VPS backend bring-up (needs P4 secrets; cert step needs P1+P2)

### Task 5: Take ownership and sync the VPS checkout to `origin/main`

**Files (on VPS):** `/opt/quandatics/crm-platform`

- [ ] **Step 1: (USER, one-time) chown the checkout to internalops** — the agent cannot sudo. Ask the user to run, in a normal terminal:

```bash
ssh -t internalops@10.1.10.26 'sudo chown -R internalops:internalops /opt/quandatics/crm-platform'
```

- [ ] **Step 2: Verify writability**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'test -w /opt/quandatics/crm-platform/backend && echo WRITABLE'`
Expected: `WRITABLE`.

- [ ] **Step 3: Point the checkout at the real remote and sync (preserving any existing .env)**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 '
  cd /opt/quandatics/crm-platform &&
  cp -n backend/.env backend/.env.bak 2>/dev/null || true &&
  git remote set-url origin https://github.com/JienWeng/crm-platform.git 2>/dev/null || git remote add origin https://github.com/JienWeng/crm-platform.git &&
  git fetch origin main &&
  git checkout -B main origin/main &&
  git log --oneline -1'
```
Expected: HEAD now matches the pushed `origin/main` tip (the merge from Task 13, or `894d9cb`+ before that). `.env` preserved (git-ignored).

- [ ] **Step 4: Verify the kit is present**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'ls /opt/quandatics/crm-platform/backend/{docker-compose.yml,Caddyfile,.env.example}'`
Expected: all three paths listed.

### Task 6: Configure `backend/.env` with real values + generated secrets

**Files (on VPS):** `/opt/quandatics/crm-platform/backend/.env`

- [ ] **Step 1: Start from the example and generate the two local secrets**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 '
  cd /opt/quandatics/crm-platform/backend &&
  cp .env.example .env &&
  PGP=$(openssl rand -hex 24) &&
  ENC=$(openssl rand -base64 32) &&
  sed -i -E "s#^PG_DATABASE_PASSWORD=.*#PG_DATABASE_PASSWORD=${PGP}#" .env &&
  sed -i -E "s#^ENCRYPTION_KEY=.*#ENCRYPTION_KEY=${ENC//#/\\#}#" .env &&
  echo "generated PG password + ENCRYPTION_KEY"'
```

- [ ] **Step 2: Set domains, tag, multi-workspace, and Entra (non-secret) values**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 '
  cd /opt/quandatics/crm-platform/backend &&
  sed -i -E \
    -e "s#^SERVER_IMAGE=.*#SERVER_IMAGE=twentycrm/twenty#" \
    -e "s#^TAG=.*#TAG=v2.8.3#" \
    -e "s#^SERVER_URL=.*#SERVER_URL=https://api.quandatics.dpdns.org#" \
    -e "s#^FRONTEND_URL=.*#FRONTEND_URL=https://app.quandatics.dpdns.org#" \
    -e "s#^API_DOMAIN=.*#API_DOMAIN=api.quandatics.dpdns.org#" \
    -e "s#^FRONTEND_WILDCARD_DOMAIN=.*#FRONTEND_WILDCARD_DOMAIN=*.app.quandatics.dpdns.org#" \
    -e "s#^IS_MULTIWORKSPACE_ENABLED=.*#IS_MULTIWORKSPACE_ENABLED=true#" \
    -e "s#^IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=.*#IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true#" \
    -e "s#^DEFAULT_SUBDOMAIN=.*#DEFAULT_SUBDOMAIN=app#" \
    -e "s#^AUTH_MICROSOFT_ENABLED=.*#AUTH_MICROSOFT_ENABLED=true#" \
    -e "s#^AUTH_MICROSOFT_CLIENT_ID=.*#AUTH_MICROSOFT_CLIENT_ID=bb6e92e4-571b-4a83-8026-66e1211fee73#" \
    -e "s#^AUTH_MICROSOFT_CALLBACK_URL=.*#AUTH_MICROSOFT_CALLBACK_URL=https://api.quandatics.dpdns.org/auth/microsoft/redirect#" \
    -e "s#^AUTH_MICROSOFT_APIS_CALLBACK_URL=.*#AUTH_MICROSOFT_APIS_CALLBACK_URL=https://api.quandatics.dpdns.org/auth/microsoft-apis/get-access-token#" \
    -e "s#^AUTH_PASSWORD_ENABLED=.*#AUTH_PASSWORD_ENABLED=false#" \
    .env &&
  echo "set domains/tag/multiworkspace/entra"'
```

- [ ] **Step 3: Insert the two provided secrets (P4)** — replace `<CF>` and `<MS>` with the real values, or instruct the user to paste them directly:

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 '
  cd /opt/quandatics/crm-platform/backend &&
  sed -i -E "s#^CLOUDFLARE_API_TOKEN=.*#CLOUDFLARE_API_TOKEN=<CF>#" .env &&
  sed -i -E "s#^AUTH_MICROSOFT_CLIENT_SECRET=.*#AUTH_MICROSOFT_CLIENT_SECRET=<MS>#" .env &&
  echo "secrets set"'
```

- [ ] **Step 4: Verify no placeholders remain (secrets masked)**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && grep -nE "repl|changeme|ourco\.com|<|>|=$" .env | sed -E "s/(SECRET|KEY|PASSWORD|TOKEN)=.*/\1=***/" || echo "no placeholders"'`
Expected: `no placeholders`.

### Task 7: Bring up the data plane (Postgres + Redis) and verify

- [ ] **Step 1: Start only db + redis**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose up -d db redis'
```

- [ ] **Step 2: Verify Postgres is healthy and accepts the configured password**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose exec -T db pg_isready -U postgres'`
Expected: `... accepting connections`.

### Task 8: Bring up server + worker and verify migrations + internal health

- [ ] **Step 1: Start server + worker (server runs DB migrations on boot)**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose up -d server worker'
```

- [ ] **Step 2: Watch server logs until it reports listening / migrations done**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose logs --tail=40 server'`
Expected: migration output then a "listening on 3000" style line; no fatal `ENCRYPTION_KEY`/DB errors.

- [ ] **Step 3: Verify health from inside the compose network**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose exec -T server sh -lc "wget -qO- http://localhost:3000/healthz || curl -s http://localhost:3000/healthz"'`
Expected: a 200/OK health body.

### Task 9: Bring up Caddy and verify wildcard cert issuance  ⛳ needs P2 (DNS) + P4 (CF token)

- [ ] **Step 1: Start Caddy**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose up -d caddy && docker compose ps'
```

- [ ] **Step 2: Watch Caddy issue the certs via DNS-01**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && docker compose logs --tail=60 caddy'`
Expected: lines showing certificates obtained for `api.quandatics.dpdns.org` and `*.app.quandatics.dpdns.org`; no repeated DNS-01 auth failures. (Failures here almost always = wrong `CLOUDFLARE_API_TOKEN` scope or DNS records missing → fix P2/P4.)

- [ ] **Step 3: Verify the API answers over TLS from the VPS itself**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'curl -sI --resolve api.quandatics.dpdns.org:443:127.0.0.1 https://api.quandatics.dpdns.org/healthz | head -1'`
Expected: `HTTP/2 200` (or `HTTP/1.1 200`).

---

## Phase 4 — Branded frontend: first build + deploy (Mac)  ⛳ needs Task 9 green

### Task 10: Build the rebranded bundle on the Mac and deploy to the VPS

**Files:** uses `frontend/build-and-deploy.sh` (DEPLOY=ssh) → VPS `/srv/quandatics-front`

- [ ] **Step 1: (USER, one-time) create the served dir on the VPS**

```bash
ssh -t internalops@10.1.10.26 'sudo mkdir -p /srv/quandatics-front && sudo chown -R internalops:internalops /srv/quandatics-front'
```

- [ ] **Step 2: Build + deploy from the Mac** (Node 24.15.x, ≥8 GB free RAM; first run clones Twenty + yarn install — several minutes)

```bash
cd frontend
TAG=v2.8.3 \
REACT_APP_SERVER_BASE_URL=https://api.quandatics.dpdns.org \
APP_NAME="Quandatics CRM" \
DEPLOY=ssh DEPLOY_HOST=internalops@10.1.10.26 DEPLOY_DIR=/srv/quandatics-front \
./build-and-deploy.sh
cd ..
```
Expected: ends with `Published to internalops@10.1.10.26:/srv/quandatics-front …`.

> Note: `DEPLOY_HOST` uses the VPN/private reachability of your Mac. If the Mac can't `ssh` the VPS directly, reuse the master socket: prepend `RSYNC_RSH="ssh -o ControlPath=~/.ssh/cm-vps"` and set `DEPLOY_HOST=internalops@10.1.10.26`.

- [ ] **Step 3: Verify the bundle landed and Caddy serves it**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'ls /srv/quandatics-front/index.html && grep -o "<title>[^<]*</title>" /srv/quandatics-front/index.html'`
Expected: `index.html` exists and title is `<title>Quandatics CRM</title>`.

- [ ] **Step 4: Verify the injected backend URL**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'grep -o "api.quandatics.dpdns.org" /srv/quandatics-front/index.html | head -1'`
Expected: `api.quandatics.dpdns.org` (runtime env injected).

---

## Phase 5 — Public verification + operations  ⛳ needs P1 (port-forward) + P2 (DNS)

### Task 11: End-to-end public verification

- [ ] **Step 1: Public API health (from the Mac, over the internet)**

Run: `curl -sI https://api.quandatics.dpdns.org/healthz | head -1`
Expected: `HTTP/2 200`, valid TLS, no cert warning.

- [ ] **Step 2: Public frontend loads with branding**

Run: `curl -s https://app.quandatics.dpdns.org | grep -o "<title>[^<]*</title>"`
Expected: `<title>Quandatics CRM</title>`.

- [ ] **Step 3: Manual — SSO login + subdomain multitenancy (record results)**
  - Open `https://app.quandatics.dpdns.org` → only "Continue with Microsoft" shows (no password field).
  - Sign in with a tenant user → lands in the default workspace; favicon/logo are Quandatics.
  - As server admin, create a **second workspace** → confirm it routes to `<name>.app.quandatics.dpdns.org` under the wildcard cert and SSO works there too.
  - Smoke-test approved-domain auto-join for one workspace (Settings → Members).

### Task 12: Nightly database backups

**Files (on VPS):** crontab for `internalops`; uses existing `backend/backup.sh`

- [ ] **Step 1: Verify a manual backup works**

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform/backend && ./backup.sh && ls -t backups | head -1'`
Expected: a new `twenty_<ts>.sql.gz` listed.

- [ ] **Step 2: Install a nightly cron (02:30) and verify it's registered**

```bash
ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 '
  ( crontab -l 2>/dev/null | grep -v quandatics-backup;
    echo "30 2 * * * cd /opt/quandatics/crm-platform/backend && ./backup.sh >> \$HOME/quandatics-backup.log 2>&1 # quandatics-backup" ) | crontab - &&
  crontab -l | grep quandatics-backup'
```
Expected: the cron line is printed back.

### Task 13: Merge to main

- [ ] **Step 1: Merge the PR once Task 11 manual checks pass**

```bash
gh pr merge deploy/twenty-crm-selfhost --squash --delete-branch
```
Expected: merged; `main` now holds brand assets + CI + spec/plan.

- [ ] **Step 2: Re-sync the VPS checkout to the new main** (repeat Task 5 Step 3) and verify HEAD matches.

Run: `ssh -o ControlPath=~/.ssh/cm-vps internalops@10.1.10.26 'cd /opt/quandatics/crm-platform && git fetch origin main && git checkout -B main origin/main && git log --oneline -1'`
Expected: HEAD equals the squash-merge commit on `origin/main`.

---

## Done = 

- `https://app.quandatics.dpdns.org` loads the **Quandatics-branded** Twenty from any network, login is **Entra-only**, a **second entity** lives on its own subdomain with isolated data, nightly backups run, and `main` on GitHub is the single source of truth with CI ready to rebuild the frontend.
