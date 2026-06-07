# Tenant-pinned Twenty image for SINGLE-TENANT Entra ID SSO.
#
# Why: upstream Twenty hardcodes the Microsoft OAuth `tenant: 'common'` endpoint
# in its auth strategies. Single-tenant Azure app registrations reject /common
# with **AADSTS50194** ("…not configured as a multi-tenant application…"). Twenty
# exposes NO tenant env var (only AUTH_MICROSOFT_{ENABLED,CLIENT_ID,CLIENT_SECRET,
# CALLBACK_URL,APIS_CALLBACK_URL}), so the only fixes are (a) make the app
# multi-tenant — weakens the security boundary — or (b) this overlay, which pins
# the tenant id into the compiled strategies. We use (b): stays single-tenant,
# needs no Azure change, and is a pure file overlay (NO source compile).
#
# Build (run from backend/):
#   docker build -f tenant-patch.Dockerfile \
#     --build-arg AZURE_TENANT_ID=<your-tenant-guid> \
#     --build-arg TWENTY_VERSION=v2.8.3 \
#     -t quandatics/twenty:v2.8.3 .
# Then in .env: SERVER_IMAGE=quandatics/twenty  (NO tag — compose appends :${TAG}),
#               TAG=v2.8.3   (must equal TWENTY_VERSION above)
# Recreate:  docker compose up -d --force-recreate server worker
#
# On every Twenty upgrade: rebuild this with the new TWENTY_VERSION/TAG.

ARG TWENTY_VERSION=v2.8.3
FROM twentycrm/twenty:${TWENTY_VERSION}

# Default is the Quandatics org tenant; override with --build-arg for other tenants.
ARG AZURE_TENANT_ID=8af4cff3-6ddb-47dc-95e3-1ef13b51a21a

RUN find /app/packages/twenty-server/dist/engine/core-modules/auth/strategies -name '*.js' \
      -exec sed -i "s/tenant: 'common'/tenant: '${AZURE_TENANT_ID}'/g" {} + \
 && echo 'Patched Microsoft auth tenant ->' \
 && grep -rh "tenant: '" /app/packages/twenty-server/dist/engine/core-modules/auth/strategies/*.js \
      | grep -v map | sort -u
