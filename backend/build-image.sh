#!/usr/bin/env bash
# Build a CUSTOM backend image from your fork of Twenty and push it to a registry.
# Only needed for Tier-3 changes (forking twenty-server). For native features or
# Apps you do NOT need this — keep using the upstream image.
#
# Builds the `twenty-server` target (server only, no bundled frontend) — the
# frontend is shipped separately as a static build from the SAME ref.
#
# Usage:
#   REPO=https://github.com/yourorg/twenty.git \
#   REF=company-main \
#   IMAGE=ghcr.io/yourorg/twenty-server \
#   TAG=2026.06.01 \
#   PUSH=true \
#   ./build-image.sh
#
# Requires Docker (Buildx). On Mac use Docker Desktop with >=8GB memory.
set -euo pipefail

REPO="${REPO:?set REPO to your fork git URL}"
REF="${REF:?set REF to your branch/tag/commit (must match the frontend build)}"
IMAGE="${IMAGE:?set IMAGE to your registry path, e.g. ghcr.io/yourorg/twenty-server}"
TAG="${TAG:?set TAG, e.g. a date or version}"
TARGET="${TARGET:-twenty-server}"   # twenty-server (no front) | twenty (all-in-one)
PUSH="${PUSH:-false}"

WORK="${WORK:-$(cd "$(dirname "$0")" && pwd)/.imgbuild}"
SRC="$WORK/twenty"

echo "==> Clone $REPO @ $REF"
mkdir -p "$WORK"
if [ ! -d "$SRC" ]; then
  git clone "$REPO" "$SRC"
fi
git -C "$SRC" remote set-url origin "$REPO"
git -C "$SRC" fetch origin "$REF"
git -C "$SRC" checkout FETCH_HEAD

echo "==> Build $IMAGE:$TAG (target=$TARGET) from $(git -C "$SRC" rev-parse --short HEAD)"
docker build \
  -f "$SRC/packages/twenty-docker/twenty/Dockerfile" \
  --target "$TARGET" \
  -t "$IMAGE:$TAG" \
  "$SRC"

if [ "$PUSH" = "true" ]; then
  echo "==> Push $IMAGE:$TAG"
  docker push "$IMAGE:$TAG"
fi

echo "Done. Point backend/.env at it:"
echo "  SERVER_IMAGE=$IMAGE"
echo "  TAG=$TAG"
echo "Then: docker compose pull && docker compose up -d"
echo "IMPORTANT: build the frontend from the SAME ref ($REF):"
echo "  cd ../frontend && REPO=$REPO TAG=$REF REACT_APP_SERVER_BASE_URL=https://api.ourco.com HOST=azure ... ./build-and-deploy.sh"
