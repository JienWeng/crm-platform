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
TAG=v0.62.0 \
REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
APP_NAME="Quandatics CRM" \
HOST=azure SWA_DEPLOYMENT_TOKEN=xxxxx \
./build-and-deploy.sh

# Vercel
TAG=v0.62.0 \
REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
HOST=vercel VERCEL_TOKEN=xxxxx \
./build-and-deploy.sh

# Just build (upload the printed build/ dir yourself)
TAG=v0.62.0 REACT_APP_SERVER_BASE_URL=https://api.ourco.com HOST=none ./build-and-deploy.sh
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
