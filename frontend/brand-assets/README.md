# brand-assets

Drop your branding files here, **mirroring twenty-front's directory tree**.
`rebrand.sh` copies each file onto the same relative path inside the checked-out
`twenty-front` package before the build.

Example layout (paths depend on the Twenty version you build — inspect
`.work/twenty/packages/twenty-front/` after the first run to confirm exact names):

```
brand-assets/
  public/
    favicon.ico
    favicon-16x16.png
    favicon-32x32.png
    manifest.json          # set "name" / "short_name" to your app
  src/
    ...logo SVG/PNG assets you want to replace...
```

Anything named `README*` is ignored by the copy step.

For deeper UI rebranding (in-app logo components, color tokens beyond the
per-workspace theme settings) you'd edit `twenty-front` source — out of scope for
the "light rebrand" path. Per-workspace colors are set at runtime in the app's
workspace settings, no build change needed.
