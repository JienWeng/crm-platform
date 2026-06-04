#!/usr/bin/env bash
# Build the Twenty frontend from source, apply our rebrand, inject the backend
# URL, and place the static output into a directory that Caddy serves.
#
# Per the design spec (§3, §5): the frontend is ONE workspace-agnostic static
# bundle served by Caddy on every *.app.ourco.com host (file_server with SPA
# fallback), behind a wildcard cert issued via Cloudflare DNS-01. There is NO
# CDN, NO Azure Static Web Apps, and NO Vercel in the deploy path anymore.
#
# NOTE: staticwebapp.config.json / vercel.json are NO LONGER part of the deploy
#       path. SPA fallback is handled by Caddy (try_files ... /index.html) in
#       backend/Caddyfile, not by a host-provider config file. Those two files
#       are kept only for reference / possible future use; they are intentionally
#       NOT copied into the build output below.
#
# Run on a build machine / CI with Node 24.15.x, Yarn 4 (corepack), >=8GB free RAM.
#
# Usage:
#   TAG=v2.8.3 \
#   REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
#   DEPLOY_DIR=/srv/quandatics-front \
#   ./build-and-deploy.sh
#
# Common variants:
#   # Build only, no deploy (inspect the bundle, then sync it yourself):
#   DEPLOY=none ./build-and-deploy.sh
#
#   # Deploy to a remote VPS over rsync+ssh (the dir is bind-mounted into Caddy):
#   DEPLOY=ssh DEPLOY_HOST=deploy@vps DEPLOY_DIR=/srv/quandatics-front ./build-and-deploy.sh
set -euo pipefail

TAG="${TAG:?set TAG to the same ref as the backend image (e.g. v2.8.3 or your fork branch)}"
REACT_APP_SERVER_BASE_URL="${REACT_APP_SERVER_BASE_URL:?set to your https backend URL}"
# Where the built bundle is published. This must match the path bind-mounted
# into the Caddy container that serves *.app.ourco.com (see backend/Caddyfile).
DEPLOY_DIR="${DEPLOY_DIR:-/srv/quandatics-front}"
# local = copy into DEPLOY_DIR on this host (build runs on the VPS, or DEPLOY_DIR
#         is an NFS/shared mount). ssh = rsync to DEPLOY_HOST:DEPLOY_DIR.
# none  = build only; print the bundle path and stop.
DEPLOY="${DEPLOY:-local}"
DEPLOY_HOST="${DEPLOY_HOST:-}"   # required when DEPLOY=ssh, e.g. deploy@vps
# Point at your fork to ship custom (rebranded) frontend code; defaults to upstream.
REPO="${REPO:-https://github.com/twentyhq/twenty.git}"

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-$KIT_DIR/.work}"
SRC="$WORK/twenty"

echo "==> 1/5 Clone $REPO @ $TAG"
mkdir -p "$WORK"
if [ ! -d "$SRC" ]; then
  git clone --branch "$TAG" --depth 1 "$REPO" "$SRC"
else
  git -C "$SRC" remote set-url origin "$REPO"
  git -C "$SRC" fetch --depth 1 origin "$TAG" && git -C "$SRC" checkout FETCH_HEAD
fi

echo "==> 2/5 Install deps (yarn 4 via corepack)"
corepack enable
( cd "$SRC" && yarn )

echo "==> 3/5 Apply rebrand"
"$KIT_DIR/rebrand.sh" "$SRC/packages/twenty-front"

echo "==> 4/5 Build static frontend + inject backend URL"
export NODE_OPTIONS="--max-old-space-size=8192"
( cd "$SRC" && npx nx build twenty-front )
( cd "$SRC/packages/twenty-front" \
  && REACT_APP_SERVER_BASE_URL="$REACT_APP_SERVER_BASE_URL" sh scripts/inject-runtime-env.sh )

BUILD_DIR="$SRC/packages/twenty-front/build"
# NB: we do NOT drop staticwebapp.config.json / vercel.json into the bundle.
# Caddy owns SPA fallback now (see header note + backend/Caddyfile).
echo "Build ready at: $BUILD_DIR"

echo "==> 5/5 Publish to Caddy-served dir (deploy=$DEPLOY, dir=$DEPLOY_DIR)"
case "$DEPLOY" in
  local)
    # Idempotent sync into the bind-mounted dir. --delete removes stale files
    # from previous builds so the served bundle exactly matches BUILD_DIR.
    mkdir -p "$DEPLOY_DIR"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete "$BUILD_DIR/" "$DEPLOY_DIR/"
    else
      # Fallback when rsync is unavailable: clear + copy.
      rm -rf "${DEPLOY_DIR:?}/"* "${DEPLOY_DIR:?}/".[!.]* 2>/dev/null || true
      cp -a "$BUILD_DIR/." "$DEPLOY_DIR/"
    fi
    echo "Published to $DEPLOY_DIR (served by Caddy on *.app.ourco.com)."
    ;;
  ssh)
    : "${DEPLOY_HOST:?set DEPLOY_HOST (e.g. deploy@vps) when DEPLOY=ssh}"
    # rsync over ssh into the remote bind-mounted dir; --delete keeps it exact.
    ssh "$DEPLOY_HOST" "mkdir -p '$DEPLOY_DIR'"
    rsync -a --delete -e ssh "$BUILD_DIR/" "$DEPLOY_HOST:$DEPLOY_DIR/"
    echo "Published to $DEPLOY_HOST:$DEPLOY_DIR (served by Caddy on *.app.ourco.com)."
    ;;
  none)
    echo "Skipping publish. Sync the contents of $BUILD_DIR to your Caddy-served"
    echo "dir yourself, e.g.:  rsync -a --delete '$BUILD_DIR/' '$DEPLOY_DIR/'"
    ;;
  *)
    echo "Unknown DEPLOY=$DEPLOY (use local|ssh|none)"; exit 1
    ;;
esac
echo "Done."
