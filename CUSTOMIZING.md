# Customizing Twenty — dev → test → production

How to change the product (not just config), test locally, and ship. Pick the
**lowest tier** that does the job — only fork when you truly must.

## Decide the tier

```
Does the feature already exist natively? ───────────────► TIER 1 (no code)
   e.g. Dashboards (beta), custom objects/fields, roles, themes, webhooks
        │ no
        ▼
Is it a widget / custom object / server logic / side-panel? ─► TIER 2 (App)
        │ no  (you need a new full page/route, or to change core behavior/UI)
        ▼
                                                              TIER 3 (fork core)
```

Twenty's App-rendered front components only render in the **right-side panel** or
as **page-layout/dashboard widgets** — they cannot add new routes. A standalone
new *page* ⇒ Tier 3.

---

## Tier 1 — Native / no-code
No repo, no build. Configure in the running app. Dashboards: *Settings → Updates
→ Early Access → Dashboards → + New Dashboard*. Custom objects/fields, roles, API
keys, webhooks: *Settings*. Per-workspace theme/colors: *Settings*. Nothing to
deploy — it's stored in Postgres, so it's already "in production" once set on the
prod instance (and backed up by `backend/backup.sh`).

---

## Tier 2 — App (extend, no fork)
A sandboxed TypeScript package with its own CLI. Upgrade-safe (pinned via semver
+ `engines.twenty`). Use for custom widgets, objects, server-side logic
functions, skills/AI agents, side-panel UI, command-menu/nav items, page layouts.

```sh
# scaffold
npx create-twenty-app@latest my-app
cd my-app

# dev loop against a local backend (Loop 1 from local-dev/ running on :3000,
# or the apps dev server on :2020). Watches src/, rebuilds, syncs to the server:
yarn twenty dev

# test (Vitest against a real server) + typecheck
yarn test
yarn twenty dev:typecheck

# ship to production
yarn twenty remote:add --url https://api.ourco.com --as production
# bump "version" in package.json first (server rejects duplicate versions)
yarn twenty app:publish --private --remote production
```
Docs: https://docs.twenty.com/developers/extend

---

## Tier 3 — Fork core (custom frontend page and/or backend code)

This is the only tier that changes your deployment: you stop using the prebuilt
`twentycrm/twenty` image and ship **your own** image + static build, both from the
**same commit**.

### A. One-time: set up your fork
```sh
# Fork twentyhq/twenty on GitHub to yourorg/twenty, then:
git clone https://github.com/yourorg/twenty.git && cd twenty
git remote add upstream https://github.com/twentyhq/twenty.git
git fetch upstream --tags
# Keep your work on a long-lived branch cut from a RELEASE TAG (not main):
git checkout -b company-main vX.Y.Z
corepack enable && yarn
```

### B. Local dev loop (hot reload)
```sh
# 1) Backend deps: Postgres + Redis. Easiest: run local-dev/ stack for db+redis,
#    or point packages/twenty-server/.env at your own. Then:
cp packages/twenty-server/.env.example packages/twenty-server/.env
npx nx database:reset twenty-server      # truncate + init + seed dev data
npx nx start twenty-server               # API on :3000  (/graphql, /rest)
npx nx run twenty-server:worker          # background worker

# 2) Frontend with HMR, pointed at the local backend:
cp packages/twenty-front/.env.example packages/twenty-front/.env   # REACT_APP_SERVER_BASE_URL=http://localhost:3000
npx nx start twenty-front                # UI on :3001, hot reload
```

**Conventions when adding code:**
- New page → `packages/twenty-front/src/pages/<area>/`; wire routing in `src/modules/app/`.
- New feature module → `packages/twenty-front/src/modules/<feature>/` with the
  standard subfolders `components/ graphql/ hooks/ states/ utils/`. Mirror an
  existing one — for dashboards see `src/modules/dashboards/` and
  `src/modules/page-layout/`. State uses **Recoil** (atoms/selectors in `states/`).
- New GraphQL ops → put them under the module's `graphql/`, then regenerate typed
  hooks: `npx nx run twenty-front:graphql:generate` (server must be running).
- Backend module → `packages/twenty-server/src/modules/<feature>/` (mirror
  `dashboard/`). DB change → create a migration:
  `npx nx run twenty-server:database:migrate:generate --name <name> --type fast`
  (files land in `src/database/typeorm/core/migrations/`). The server runs
  migrations automatically on startup in prod — no manual step on deploy.

### C. Test before shipping (what CI runs)
```sh
npx nx lint twenty-front     && npx nx typecheck twenty-front
npx nx lint twenty-server    && npx nx typecheck twenty-server
npx nx test twenty-front                         # Jest unit (front)
npx nx run twenty-server:test:unit               # Jest unit (server)
npx nx run twenty-server:test:integration        # integration (needs DB)
npx nx storybook:test twenty-front               # optional, Storybook
```

### D. Ship to production (from your Mac)
Both halves from the **same ref** (`company-main` or a tag you cut).

```sh
# 1) Backend: build + push your custom server image
cd crm-platform/backend
REPO=https://github.com/yourorg/twenty.git REF=company-main \
IMAGE=ghcr.io/yourorg/twenty-server TAG=2026.06.01 PUSH=true ./build-image.sh

# 2) Point the VPS at it: set SERVER_IMAGE + TAG in backend/.env, then deploy
#    (locally via remote docker context, or rsync+ssh — see local-dev/README.md)
docker compose pull && docker compose up -d        # migrations auto-run on boot

# 3) Frontend: build the static SPA from the SAME ref and deploy to the CDN
cd ../frontend
REPO=https://github.com/yourorg/twenty.git TAG=company-main \
REACT_APP_SERVER_BASE_URL=https://api.ourco.com APP_NAME="Quandatics CRM" \
HOST=azure SWA_DEPLOYMENT_TOKEN=xxxxx ./build-and-deploy.sh
```

### E. Take upstream updates later
```sh
cd twenty
git fetch upstream --tags
git checkout company-main
git rebase vX.Y.(Z+1)        # replay your changes onto the new release (or merge)
# resolve conflicts, re-run Tier-3 C (tests), then re-ship via Tier-3 D
```
Keeping as much as possible in **Tier 2 Apps** minimizes these conflicts.

---

## The two rules that bite if ignored
1. **Front and back from the same commit/ref.** GraphQL types are generated
   against the server schema; mismatched versions break the app. The build scripts
   take `REF`/`TAG` precisely so you can keep them locked together.
2. **Migrations run automatically on server startup** — but **back up first**
   (`backend/backup.sh`) and set `ENCRYPTION_KEY` before any major upgrade.
