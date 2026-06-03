#!/usr/bin/env bash
# Build the Twenty frontend from source, apply our rebrand, inject the backend
# URL, and (optionally) deploy the static output to Azure SWA or Vercel.
#
# Run on a build machine / CI with Node 24.15.x, Yarn 4 (corepack), >=8GB free RAM.
#
# Usage:
#   TAG=v0.62.0 \
#   REACT_APP_SERVER_BASE_URL=https://api.ourco.com \
#   HOST=azure|vercel|none \
#   ./build-and-deploy.sh
#
# For Azure also set:  SWA_DEPLOYMENT_TOKEN=...
# For Vercel also set: VERCEL_TOKEN=...  (and run `vercel link` once, or pass --yes)
set -euo pipefail

TAG="${TAG:?set TAG to the same ref as the backend image (e.g. v0.62.0 or your fork branch)}"
REACT_APP_SERVER_BASE_URL="${REACT_APP_SERVER_BASE_URL:?set to your https backend URL}"
HOST="${HOST:-none}"
# Point at your fork to ship custom frontend code; defaults to upstream.
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
# Drop in SPA fallback configs so deep links resolve to index.html.
cp "$KIT_DIR/staticwebapp.config.json" "$BUILD_DIR/staticwebapp.config.json"
cp "$KIT_DIR/vercel.json"            "$BUILD_DIR/vercel.json"
echo "Build ready at: $BUILD_DIR"

echo "==> 5/5 Deploy (host=$HOST)"
case "$HOST" in
  azure)
    npx -y @azure/static-web-apps-cli deploy "$BUILD_DIR" \
      --deployment-token "${SWA_DEPLOYMENT_TOKEN:?set SWA_DEPLOYMENT_TOKEN}" \
      --env production
    ;;
  vercel)
    npx -y vercel deploy --prod --yes --cwd "$BUILD_DIR" \
      --token "${VERCEL_TOKEN:?set VERCEL_TOKEN}"
    ;;
  none)
    echo "Skipping deploy. Upload the contents of $BUILD_DIR to your static host."
    ;;
  *)
    echo "Unknown HOST=$HOST (use azure|vercel|none)"; exit 1
    ;;
esac
echo "Done."
