# Frontend — static, rebranded Twenty SPA

Builds `twenty-front` from source, applies a light rebrand, injects the backend
URL at runtime (`window._env_`), and deploys the static output to Azure Static
Web Apps or Vercel.

## Prereqs (build machine / CI)
- Node **24.15.x**, Yarn 4 via `corepack enable`
- **≥8 GB free RAM** (build uses `--max-old-space-size=8192`)
- Azure SWA CLI token *or* Vercel token for deploy

## Customize the brand
Put assets in `brand-assets/` mirroring twenty-front's tree (see
`brand-assets/README.md`). Set the app name via `APP_NAME`.

## Build + deploy

```sh
# Azure Static Web Apps
TAG=v2.8.3 \
REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
APP_NAME="Quandatics CRM" \
HOST=azure SWA_DEPLOYMENT_TOKEN=xxxxx \
./build-and-deploy.sh

# Vercel
TAG=v2.8.3 \
REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
HOST=vercel VERCEL_TOKEN=xxxxx \
./build-and-deploy.sh

# Just build (upload the printed build/ dir yourself)
TAG=v2.8.3 REACT_APP_SERVER_BASE_URL=https://api.ourco.com HOST=none ./build-and-deploy.sh
```

After deploy, set the custom domain `app.ourco.com` in the host dashboard and
create the matching CNAME (see top-level README → Domain & DNS).

## Critical rules
- **`TAG` must equal the backend's `TAG`.** Mismatched front/back versions cause
  GraphQL schema errors. Rebuild + redeploy on every backend upgrade.
- `REACT_APP_SERVER_BASE_URL` must be **https** (mixed-content rule).
- The build is version-agnostic at build time; the backend URL is injected into
  `build/index.html` afterward by Twenty's own `scripts/inject-runtime-env.sh`.

## How the backend URL wiring works
`twenty-front` reads `window._env_.REACT_APP_SERVER_BASE_URL` at runtime
(`src/config/index.ts`). The official all-in-one image injects it at server boot;
since we host statically, `inject-runtime-env.sh` writes it into `index.html` at
build time instead. Auth uses bearer tokens in the `Authorization` header (token
kept in a `SameSite=Lax`, secure cookie on the frontend origin), so the
cross-domain split does not break login.

## CI secrets (Settings → Secrets and variables → Actions)
- `DEPLOY_SSH_KEY`        — private key whose public half is in the VPS deploy user's authorized_keys
- `DEPLOY_SSH_USER_HOST`  — e.g. internalops@202.186.223.119  (must be reachable from the GitHub runner; requires exposing port 22 OR using a self-hosted runner on the VPN)
- `DEPLOY_HOST_IP`        — 202.186.223.119

> Note: GitHub-hosted runners can only reach the VPS if SSH (22) is exposed publicly, which we do NOT want. Prefer a self-hosted runner on the VPS/VPN (dials out, no inbound 22), or have CI upload the bundle as an artifact and let the VPS pull it. The first production build is done manually from a Mac (see deploy plan), so CI can be finalized after launch.
