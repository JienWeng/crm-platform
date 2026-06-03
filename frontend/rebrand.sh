#!/usr/bin/env bash
# Apply our light rebrand to a checked-out twenty-front package, BEFORE building.
# Twenty has no branding env vars, so rebranding = swapping static assets +
# strings in source. This script is intentionally conservative and idempotent so
# it can be re-run on every version bump.
#
# Usage: ./rebrand.sh /path/to/twenty/packages/twenty-front
#
# Configure via env (all optional):
#   APP_NAME   (default "Quandatics CRM")  -> replaces the <title>
#   ASSETS_DIR (default ./brand-assets)    -> files here are copied over matching
#                                             paths in twenty-front (mirror the
#                                             tree, e.g. brand-assets/public/favicon.ico)
set -euo pipefail

FRONT_DIR="${1:?usage: rebrand.sh <twenty-front dir>}"
APP_NAME="${APP_NAME:-Quandatics CRM}"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="${ASSETS_DIR:-$KIT_DIR/brand-assets}"

echo "  rebrand: app name -> $APP_NAME"

# 1) Title in index.html (guarded; only if a <title> exists)
INDEX="$FRONT_DIR/index.html"
if [ -f "$INDEX" ] && grep -q "<title>" "$INDEX"; then
  sed -i.bak -E "s#<title>[^<]*</title>#<title>${APP_NAME}</title>#" "$INDEX"
  rm -f "$INDEX.bak"
fi

# 2) Asset overrides: copy everything under ASSETS_DIR onto the same relative
#    path inside twenty-front. Put your logo/favicon/manifest/og-image here,
#    mirroring twenty-front's tree (e.g. brand-assets/public/...).
if [ -d "$ASSETS_DIR" ]; then
  ( cd "$ASSETS_DIR" && find . -type f ! -name 'README*' -print0 ) | \
  while IFS= read -r -d '' rel; do
    dest="$FRONT_DIR/${rel#./}"
    mkdir -p "$(dirname "$dest")"
    cp "$ASSETS_DIR/${rel#./}" "$dest"
    echo "  rebrand: asset -> ${rel#./}"
  done
else
  echo "  rebrand: no ASSETS_DIR at $ASSETS_DIR (skipping asset swaps)"
fi

echo "  rebrand: done. Review additional strings (manifest.json name/short_name,"
echo "           meta/og tags) per the version you're building."
