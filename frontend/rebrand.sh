#!/usr/bin/env bash
# Apply our medium rebrand to a checked-out twenty-front package, BEFORE building.
# Twenty has no branding env vars, so rebranding = swapping static assets +
# strings in source. This script is intentionally conservative and idempotent so
# it can be re-run on every version bump (it only touches what it can change
# safely; deeper string/email work lives as a tracked fork patch — see notes
# emitted at the end and CUSTOMIZING.md).
#
# Usage: ./rebrand.sh /path/to/twenty/packages/twenty-front
#
# Configure via env (all optional):
#   APP_NAME    (default "Quandatics CRM")  -> replaces <title> + manifest "name"
#   APP_SHORT   (default "Quandatics")      -> manifest "short_name"
#   ASSETS_DIR  (default ./brand-assets)    -> files here are copied over matching
#                                              paths in twenty-front (mirror the
#                                              tree, e.g. brand-assets/public/favicon.ico)
set -euo pipefail

FRONT_DIR="${1:?usage: rebrand.sh <twenty-front dir>}"
APP_NAME="${APP_NAME:-Quandatics CRM}"
APP_SHORT="${APP_SHORT:-Quandatics}"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="${ASSETS_DIR:-$KIT_DIR/brand-assets}"

echo "  rebrand: app name  -> $APP_NAME"
echo "  rebrand: short name -> $APP_SHORT"

# 1) Title in index.html (guarded; only if a <title> exists)
INDEX="$FRONT_DIR/index.html"
if [ -f "$INDEX" ] && grep -q "<title>" "$INDEX"; then
  sed -i.bak -E "s#<title>[^<]*</title>#<title>${APP_NAME}</title>#" "$INDEX"
  rm -f "$INDEX.bak"
  echo "  rebrand: patched <title> in index.html"
fi

# 2) Asset overrides: copy everything under ASSETS_DIR onto the same relative
#    path inside twenty-front. Put your logo/favicon/manifest/og-image here,
#    mirroring twenty-front's tree (e.g. brand-assets/public/...).
#    NB: if you ship a full brand-assets/public/manifest.json it overrides the
#    upstream one wholesale; step 3 below is the safety net for when you DON'T.
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

# 3) manifest.json name / short_name (guarded + idempotent).
#    twenty-front ships its PWA manifest under public/. Patch the upstream file
#    in place so we don't have to maintain a full copy in brand-assets (icons
#    are still swapped via the asset copy in step 2). If you DID ship your own
#    manifest.json in brand-assets, step 2 already wrote it and these sed edits
#    are simply harmless no-ops / re-assert the right values.
#    Search the usual locations; bail quietly if the layout changed.
MANIFEST=""
for cand in \
  "$FRONT_DIR/public/manifest.json" \
  "$FRONT_DIR/public/site.webmanifest" \
  "$FRONT_DIR/manifest.json"; do
  if [ -f "$cand" ]; then MANIFEST="$cand"; break; fi
done
if [ -n "$MANIFEST" ]; then
  # Patch "name" and "short_name" string values in place. JSON-string-safe:
  # APP_NAME/APP_SHORT are plain text (no embedded quotes/backslashes expected).
  sed -i.bak -E \
    -e "s#(\"name\"[[:space:]]*:[[:space:]]*\")[^\"]*(\")#\1${APP_NAME}\2#" \
    -e "s#(\"short_name\"[[:space:]]*:[[:space:]]*\")[^\"]*(\")#\1${APP_SHORT}\2#" \
    "$MANIFEST"
  rm -f "$MANIFEST.bak"
  echo "  rebrand: patched manifest name/short_name in ${MANIFEST#$FRONT_DIR/}"
else
  echo "  rebrand: no manifest.json found under public/ (skipped; verify layout"
  echo "           for this Twenty version and add a brand-assets copy if needed)"
fi

# 4) Guidance for the fork-tracked patches that CANNOT be sed'd safely.
#    These are user-visible strings + the invitation email; they live in the
#    company-main fork branch as a tracked patch over the pinned tag (spec §7),
#    NOT in this script, because they're scattered across i18n catalogs and JSX
#    and a blind sed would be fragile across version bumps. Re-apply / rebase
#    these on every upstream bump (see CUSTOMIZING.md).
cat <<'EOF'
  ------------------------------------------------------------------------------
  rebrand: assets + title + manifest done (the safely-automatable parts).
  rebrand: the following MEDIUM-rebrand strings live as a tracked FORK PATCH on
           branch company-main (re-apply / rebase on every version bump):

    twenty-front (user-visible strings):
      - login screen copy / "Welcome to Twenty" headings
      - default new-workspace name
      - error / 404 page text
      - any remaining "Twenty" mentions in i18n catalogs
        (packages/twenty-front/src/locales/.../*.po) and JSX

    twenty-server (transactional emails):
      - the INVITATION email template (most user-visible)
      - other email templates under
        packages/twenty-emails/ (subjects, body copy, sender name)

  Find candidates to patch with, e.g.:
      grep -rni 'twenty' packages/twenty-front/src/locales
      grep -rni 'twenty' packages/twenty-emails/src
  ------------------------------------------------------------------------------
EOF
