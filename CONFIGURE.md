# Configuring a running Twenty (v2.x)

Covers: Microsoft Entra ID SSO, sign-up behavior, roles & permissions, and data
migration. Two places configuration lives in 2.x:
- **`.env` / compose** — infra vars (used here; set `IS_CONFIG_VARIABLES_IN_DB_ENABLED=false` to make `.env` authoritative).
- **In-app admin panel** — *Settings → Admin Panel → Configuration Variables* (DB-backed, the 2.x default). Either path works for most vars; pick one and be consistent.

---

## 1. Microsoft Entra ID (Azure AD) SSO

### A. Azure portal — app registration
1. **Entra ID → App registrations → New registration.**
2. **Supported account types:** *Single tenant* (restricts login to your org — there is **no tenant env var** in Twenty, so this is where you scope it).
3. **Redirect URI → type `Web`**, add BOTH (pointing at your **API** domain):
   - `https://api.ourco.com/auth/microsoft/redirect`  (SSO login)
   - `https://api.ourco.com/auth/microsoft-apis/get-access-token`  (mail/calendar, optional)
4. **Certificates & secrets → New client secret** → copy the value → `AUTH_MICROSOFT_CLIENT_SECRET`.
5. **Overview → Application (client) ID** → `AUTH_MICROSOFT_CLIENT_ID`.
6. **API permissions → Microsoft Graph (delegated):** `openid`, `email`, `profile`, `User.Read` (SSO). For mail/calendar sync also add `offline_access`, `Calendars.Read`, `Mail.Read` (and `Mail.ReadWrite`, `Mail.Send` only if sending email from workflows). Grant admin consent. (Sync needs an M365 licence per user.)

### B. Twenty — env vars
Uncomment in `backend/docker-compose.yml` (server, and worker if syncing) and set in `.env`:
```sh
AUTH_MICROSOFT_ENABLED=true
AUTH_MICROSOFT_CLIENT_ID=<application-client-id>
AUTH_MICROSOFT_CLIENT_SECRET=<client-secret-value>
AUTH_MICROSOFT_CALLBACK_URL=https://api.ourco.com/auth/microsoft/redirect
AUTH_MICROSOFT_APIS_CALLBACK_URL=https://api.ourco.com/auth/microsoft-apis/get-access-token
# optional sync:
# MESSAGING_PROVIDER_MICROSOFT_ENABLED=true
# CALENDAR_PROVIDER_MICROSOFT_ENABLED=true
```
Apply: `docker compose up -d`. A **"Continue with Microsoft"** button appears on the login screen.

> Per-workspace SAML SSO also exists (*Settings → Security → SSO Configuration*) as an alternative to the global env approach, with JIT user provisioning. Use one or the other.

---

## 2. Enabling sign-up

**There is no `IS_SIGN_UP_ENABLED` in 2.x.** Signup is governed by workspace mode:

- **Single-workspace (default):** the first user becomes admin; after that, open signup is closed. New people join via:
  - **Invitation** — *Settings → Members → Invite* (by email), or
  - **Company-domain auto-join** — *Settings → Members* → add `ourco.com`. Anyone with a matching email (e.g. via Microsoft SSO) joins automatically on first login. **This is how you "enable signup" for your team.**
- **Multi-workspace** (`IS_MULTIWORKSPACE_ENABLED=true`): many independent workspaces on one instance. Lock down creation with `IS_WORKSPACE_CREATION_LIMITED_TO_SERVER_ADMINS=true`.

Force SSO-only (no passwords): `AUTH_PASSWORD_ENABLED=false`.

**Recommended for your case:** single-workspace + Microsoft SSO + add your email domain → Entra users sign in and auto-join, no per-user invites.

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
- Base URLs (self-hosted): core `https://api.ourco.com/rest`, GraphQL `https://api.ourco.com/graphql`, metadata `https://api.ourco.com/rest/metadata`.
- Limits: **100 req/min**, **≤60 records per batch call**.

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
