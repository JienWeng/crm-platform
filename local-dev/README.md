# Dev & deploy from your Mac

Three loops, fastest to most realistic. All run on your laptop. Requires
**Docker Desktop** (and for source dev, **Node 24.15.x** + `corepack enable`).

## Loop 1 — Quick preview (all-in-one)
Evaluate Twenty, configure workspaces, set per-workspace theme/colors. Server
serves the bundled frontend; http on localhost is fine.

```sh
cd local-dev
cp .env.example .env
docker compose up -d
open http://localhost:3000          # create the first workspace + user
docker compose down                 # stop (add -v to wipe data)
```

## Loop 2 — Rebrand with hot reload (frontend from source)
Best for iterating on logo / title / colors. Run the backend from Loop 1, then
run the frontend dev server against it.

```sh
# backend from Loop 1 is up on :3000
git clone --branch v0.62.0 --depth 1 https://github.com/twentyhq/twenty.git
cd twenty && corepack enable && yarn
# point the dev front at the local backend:
echo 'REACT_APP_SERVER_BASE_URL=http://localhost:3000' > packages/twenty-front/.env
npx nx start twenty-front           # hot-reloading UI on :3001
```
Edit assets/strings under `packages/twenty-front/`, see changes live. Mirror the
files you change into `../frontend/brand-assets/` so the production build picks
them up. (Capture the same edits in `../frontend/rebrand.sh` if they're string
swaps rather than asset files.)

## Loop 3 — Test the real split locally
Mirror production (static build → separate backend) before shipping.

```sh
# 1) backend up on :3000 (Loop 1)
# 2) build the static front pointed at the local backend, no deploy:
cd ../frontend
TAG=v0.62.0 REACT_APP_SERVER_BASE_URL=http://localhost:3000 HOST=none ./build-and-deploy.sh
# 3) serve the static output like a CDN would:
npx -y serve .work/twenty/packages/twenty-front/build -l 4000
open http://localhost:4000          # static front (:4000) talking to backend (:3000)
```

---

## Deploy from your Mac

Your laptop is the build/deploy box — no CI required.

### Frontend → Azure SWA / Vercel
```sh
cd frontend
# Azure
TAG=v0.62.0 REACT_APP_SERVER_BASE_URL=https://api.ourco.com APP_NAME="Quandatics CRM" \
  HOST=azure SWA_DEPLOYMENT_TOKEN=xxxxx ./build-and-deploy.sh
# Vercel
TAG=v0.62.0 REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
  HOST=vercel VERCEL_TOKEN=xxxxx ./build-and-deploy.sh
```

### Backend → the VPS, driven from your Mac
Pick one:

**A. Remote Docker context (run compose locally, executes on the VPS):**
```sh
docker context create vps --docker "host=ssh://user@vps-host"
docker context use vps
cd backend && docker compose up -d        # images pull/run on the VPS
docker context use default                # switch back when done
```

**B. Sync files + run over SSH:**
```sh
rsync -av --exclude .env backend/ user@vps-host:/opt/twenty/backend/
ssh user@vps-host 'cd /opt/twenty/backend && docker compose pull && docker compose up -d'
```
Keep the real `backend/.env` on the VPS (never synced — it's git-ignored).

### Mac build note
The production frontend build wants ~8 GB RAM. Building with **host Node**
(Loop 3 / `build-and-deploy.sh`) uses your Mac's RAM directly — fine on 16 GB.
If you instead build inside Docker, raise Docker Desktop → Settings → Resources →
Memory to 8 GB+.
