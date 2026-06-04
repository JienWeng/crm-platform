# brand-assets

Drop your Quandatics branding files here, **mirroring twenty-front's directory
tree**. `rebrand.sh` copies each file onto the same relative path inside the
checked-out `twenty-front` package before the build (and additionally patches
`manifest.json` `name`/`short_name` in place — see below).

> Paths can shift between Twenty versions. After the first `build-and-deploy.sh`
> run, inspect `.work/twenty/packages/twenty-front/public/` and `.../src/` to
> confirm the exact filenames for the tag you build, and adjust this tree to
> match. Anything named `README*` is ignored by the copy step.

## Asset tree to drop in

These are the files the medium rebrand replaces. Mirror twenty-front's paths
exactly — the copy is path-for-path.

```
brand-assets/
  public/
    favicon.ico                 # browser tab / bookmark favicon
    favicon-16x16.png           # small favicon (if present upstream)
    favicon-32x32.png           # standard favicon (if present upstream)
    icons/
      apple-touch-icon.png      # 180x180 iOS home-screen icon
      android-chrome-192x192.png  # PWA manifest icon (192)
      android-chrome-512x512.png  # PWA manifest icon (512)
    manifest.json               # OPTIONAL full override; otherwise rebrand.sh
                                # patches the upstream file's name/short_name
                                # in place and you only ship the icons above
    images/
      placeholders/
        og-image.png            # Open Graph / social-share preview image
  src/
    assets/
      logo.svg                  # primary app/brand logo (sidebar / header)
      logo-square.svg           # square / monogram logo variant
      login-logo.svg            # logo shown on the sign-in screen
```

### Notes per file group

- **Favicon (`public/favicon.ico`, `favicon-*.png`)** — the browser-tab icon.
  Ship at least `favicon.ico`; add the PNG sizes only if the upstream tag ships
  them (check `public/` after the first run).
- **Manifest icons (`public/icons/*`)** — referenced by the PWA `manifest.json`.
  Keep the same filenames the upstream manifest points at so you don't have to
  also edit the manifest's `icons[]` paths. Confirm the exact names/sizes for
  your tag.
- **`manifest.json`** — you usually do **not** need to copy this. `rebrand.sh`
  patches the upstream manifest's `name` (`Quandatics CRM`) and `short_name`
  (`Quandatics`) in place. Only drop a full `public/manifest.json` here if you
  need to change more than name/short_name (e.g. `icons[]`, `theme_color`); a
  copied file overrides the upstream one wholesale.
- **Logos (`src/assets/*.svg`)** — the in-app and login-screen logos. Match the
  exact filenames twenty-front imports; a mismatched name is a no-op copy that
  leaves the upstream logo in place. SVG preferred to stay crisp at any size.
- **OG image (`public/images/placeholders/og-image.png`)** — the link-preview
  image (Slack / Teams / etc.). 1200x630 is the standard size.

## What this does NOT cover

- **User-visible strings + the invitation email** are part of the medium
  rebrand but live as a tracked **fork patch** on `company-main` (spec §7), not
  here — they're scattered across i18n catalogs, JSX, and email templates and
  can't be copied path-for-path. `rebrand.sh` prints where to find them; the
  rebase-on-version-bump step is documented in `CUSTOMIZING.md`.
- **Per-workspace colors / theme** are set at runtime in each workspace's
  settings — no build change and no asset here.
