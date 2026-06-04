# Configuring a running Twenty (v2.x)

Covers: Microsoft Entra ID SSO (multi-workspace, SSO-only), workspace access, roles &
permissions, and data migration. Two places configuration lives in 2.x:
- **`.env` / compose** — infra vars (used here; set `IS_CONFIG_VARIABLES_IN_DB_ENABLED=false` to make `.env` authoritative).
- **In-app admin panel** — *Settings → Admin Panel → Configuration Variables* (DB-backed, the 2.x default). Either path works for most vars; pick one and be consistent.

---

## 1. Microsoft Entra ID (Azure AD) SSO — multi-workspace, SSO-only

This instance runs **Twenty native multi-workspace** (many workspaces, one instance,
subdomain-per-workspace) with **Entra as the only login method**. There are no passwords
and no Google — every user comes from one Entra tenant. One **single-tenant** app
registration and **one centralized callback** on the API domain serve every workspace;
there are **no per-workspace redirect URIs**.

### A. Azure portal — app registration
1. **Entra ID → App registrations → New registration.**
2. **Supported account types:** *Single tenant* (restricts login to your org — there is **no tenant env var** in Twenty, so this is where you scope it).
3. **Redirect URI → type `Web`**, add BOTH (pointing at your **API** domain — these are the *only* redirect URIs; workspaces never get their own):
   - `https://api.ourco.com/auth/microsoft/redirect`  (SSO login)
   - `https://api.ourco.com/auth/microsoft-apis/get-access-token`  (mail/calendar, optional)
   After Entra completes login at `api.ourco.com`, the server redirects the browser back to the correct workspace subdomain (`*.app.ourco.com`) — so a single callback covers all workspaces.
4. **Certificates & secrets → New client secret** → copy the value → `AUTH_MICROSOFT_CLIENT_SECRET`.
5. **Overview → Application (client) ID** → `AUTH_MICROSOFT_CLIENT_ID`.
6. **API permissions → Microsoft Graph (delegated):** `openid`, `email`, `profile`, `User.Read` (SSO). For mail/calendar sync also add `offline_access`, `Calendars.Read`, `Mail.Read` (and `Mail.ReadWrite`, `Mail.Send` only if sending email from workflows). Grant admin consent. (Sync needs an M365 licence per user.)

### B. Twenty — env vars
Uncomment in `backend/docker-compose.yml` (server, and worker if syncing) and set in `.env`:
```sh
# Multi-workspace
IS_MULTIWORKSPACE_ENABLED=true                          # many workspaces on one instance
IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true     # only server admins create workspaces
DEFAULT_SUBDOMAIN=app                                    # the default landing subdomain (app.ourco.com)
FRONTEND_URL=https://app.ourco.com                       # base the server uses to build per-workspace URLs

# Entra-only auth
AUTH_MICROSOFT_ENABLED=true
AUTH_MICROSOFT_CLIENT_ID=<application-client-id>
AUTH_MICROSOFT_CLIENT_SECRET=<client-secret-value>
AUTH_MICROSOFT_CALLBACK_URL=https://api.ourco.com/auth/microsoft/redirect
AUTH_MICROSOFT_APIS_CALLBACK_URL=https://api.ourco.com/auth/microsoft-apis/get-access-token
AUTH_PASSWORD_ENABLED=false                              # SSO-only — no email/password login
# Google intentionally left disabled (AUTH_GOOGLE_ENABLED unset/false)
# optional sync:
# MESSAGING_PROVIDER_MICROSOFT_ENABLED=true
# CALENDAR_PROVIDER_MICROSOFT_ENABLED=true
```
Apply: `docker compose up -d`. With `AUTH_PASSWORD_ENABLED=false`, the login screen shows **only** the **"Continue with Microsoft"** button.

**Subdomain routing.** With multi-workspace on, each workspace lives at its own subdomain
under `*.app.ourco.com` (e.g. `acme.app.ourco.com`); `DEFAULT_SUBDOMAIN=app` is the default
landing subdomain (`app.ourco.com`). One static `twenty-front` bundle serves every
subdomain — the host tells the server which workspace — and Entra always returns to the
single API-domain callback, never to a per-workspace URL.

> **Verify locally (§8 of the design spec):** confirm how the server builds per-workspace
> subdomain URLs from `FRONTEND_URL` + `DEFAULT_SUBDOMAIN` before relying on it in prod —
> exact behavior varies across Twenty versions. Enabling multi-workspace without subdomains
> wired up has broken login upstream ([#13263](https://github.com/twentyhq/twenty/issues/13263)),
> so smoke-test subdomain login first.

> Per-workspace SAML SSO also exists (*Settings → Security → SSO Configuration*) as an alternative to the global env approach, with JIT user provisioning. We deliberately use the **global Entra env** approach for all workspaces here; don't mix the two.

---

## 2. Access in multi-workspace mode

**There is no `IS_SIGN_UP_ENABLED` in 2.x.** With `IS_MULTIWORKSPACE_ENABLED=true`, the
instance hosts **many independent workspaces** (teams / clients / departments), each on its
own `*.app.ourco.com` subdomain. Access has two layers — who can create workspaces, and who
can join an existing one — and all of it is **SSO-only** (`AUTH_PASSWORD_ENABLED=false`, no
passwords, no Google).

### Who creates workspaces
- `IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true` — **only server admins** stand up new
  workspaces; ordinary Entra users cannot self-provision one. Each new workspace gets its
  subdomain and a first admin.

### Who joins a workspace
Membership is configured **per workspace** (each is independent — these settings do not span workspaces):
  - **Approved-domain auto-join** — *Settings → Members* → add `ourco.com`. Anyone in that
    Entra tenant with a matching email joins **that** workspace automatically on first
    Microsoft sign-in. This is how you let a team onboard without per-user invites.
  - **Invitation** — *Settings → Members → Invite* (by email) — for guests, or for anyone you
    don't want auto-joining by domain.

Because login is SSO-only, every join (auto or invited) authenticates through the single
centralized Entra callback (§1) and then lands the user on the workspace's own subdomain.

> **Verify locally (§8 of the design spec):** confirm that per-workspace approved-domain
> auto-join behaves the same under multi-workspace as it does in single-workspace mode
> before relying on it in prod; if it differs, fall back to invitation-only per workspace.

**Recommended for your case:** server admins create a workspace per team; add `ourco.com` as
that workspace's approved domain so Entra users auto-join on first SSO login; use invites for
guests outside the domain.

---

## 3. Roles & permissions (RBAC)

All in **Settings → Members → Roles** (UI; no officially documented role API):
- Default roles **Admin** / **Member**; create custom roles (+ Create Role).
- **Object-level**: baseline view/edit/delete per object, with **+ Add rule** exceptions per object.
- **Field-level**: per field → *See / Edit / No access*.
- **Settings & action permissions**: API-key creation, data-model config, security, workflows, importing data, sending email — granular or "Settings All Access".
- One role per user. Assign via the role's **Assignment tab → + Assign to member**. New members get the configured **default role**.
- **API keys can be scoped to a role** (Assignment tab) — use a restricted role for the migration key below.

---

## 4. Data migration

### API access
*Settings → API & Webhooks → + Create key* (shown once). Then:
- Header: `Authorization: Bearer <API_KEY>`
- Base URLs (self-hosted): core `https://api.ourco.com/rest`, GraphQL `https://api.ourco.com/graphql`, metadata `https://api.ourco.com/rest/metadata`. (The API domain is shared across all workspaces; the **key** scopes the call to the workspace it was created in.)
- Limits: **100 req/min**, **≤60 records per batch call**.

> In multi-workspace mode, data is **per workspace**: create the key from inside the target workspace, and repeat the import for each workspace you're migrating into.

### Options by volume
- **< 10k rows** → built-in CSV importer: open the object (People/Companies) → ⋮ → **Import records**, auto-maps columns. For relations, map the company **domain** (preferred) or **companyId** — not both.
- **> 50k / repeatable** → REST batch API (`tools/migrate.py` below).

### Recommended order (dependencies)
1. **Metadata** — custom objects/fields first (Metadata API or *Settings → Data model*).
2. **Invite users** (so owner/assignee relations resolve by email).
3. **Companies** (no deps).
4. **People** — link via `companyId`.
5. **Opportunities** → 6. **Notes / Tasks** → 7. other custom objects.

### Scripted bulk import
See [`tools/migrate.py`](tools/migrate.py) — a stdlib-only Python example that
reads CSVs, batch-creates companies, then people linked by `companyId`, with
rate-limit handling. Configure via env:
```sh
export TWENTY_API_URL=https://api.ourco.com
export TWENTY_API_KEY=<key>
python3 tools/migrate.py companies tools/sample/companies.csv
python3 tools/migrate.py people    tools/sample/people.csv
```
