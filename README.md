# yard-landing

Documentation site for [yard](https://github.com/sean-mca/yard), built with
Jekyll on the [jekyll-gitbook](https://github.com/sighingnow/jekyll-gitbook)
theme (Apache 2.0, see `LICENSE-jekyll-gitbook`). The theme is vendored into
`_layouts/`, `_includes/` and `assets/gitbook/` rather than loaded as a remote
theme, so the site builds with plain Jekyll 4 and the sidebar could be
customised.

## Local preview

With Ruby 3.x:

```sh
bundle install
bundle exec jekyll serve
```

Or without a local Ruby, via Docker:

```sh
docker run --rm -it -p 4000:4000 -v "$PWD":/site -w /site ruby:3.3 \
  sh -c "bundle install && bundle exec jekyll serve --host 0.0.0.0"
```

Then open http://localhost:4000/yard-landing/. Config changes need a restart.

## Deploy

`.github/workflows/pages.yml` builds the site with Jekyll 4 and publishes it
to GitHub Pages on every push to `main`. In the repository settings, set
**Pages → Build and deployment → Source** to **GitHub Actions**.

`baseurl` in `_config.yml` is `/yard-landing`, which matches the
`yggdrasilLabs/yard-landing` repository, published at
https://yggdrasillabs.github.io/yard-landing/. The workflow overrides it from the
Pages configuration at build time, so renaming the repository or adding a custom
domain only requires updating `url` and `baseurl` for local previews.

## Content

- `index.md` is the overview page shown at `/`.
- The sidebar sections are Jekyll collections (`_start/`, `_howto/`,
  `_plugins/`, `_reference/`, `_contributing/`). Their titles and
  order are set in `_config.yml`; the pages inside them are generated.

### Generated documentation pages

The collections are generated from the `docs/` tree of the yard repository plus
the yard-plugins README. The generated files are committed, so the site builds
without the other repositories present.

To refresh them after the upstream docs change, with `yard` and `yard-plugins`
checked out as siblings of this folder:

```sh
python3 scripts/sync-docs.py
```

The script adds front matter, rewrites relative markdown links to site URLs
(links that leave the docs tree become GitHub links), and escapes anything
Liquid would otherwise interpret. Do not edit the generated files by hand; edit
the source docs and re-run the script.

`scripts/docs-nav.json` decides which section each page lands in and in what
order. A new upstream page is skipped with a warning until it is added there.

Pages the site owns rather than mirrors, such as the install page, live in
`docs-site/` and are copied in by the same script. They use the same
`permalink` front matter to pick their URL and are placed by `docs-nav.json`
like any other page.

### Tabbed examples

Upstream markdown can mark a region as tabs. GitHub hides the comment markers
and renders the tabs in sequence with their bold labels; the sync script turns
the region into tab buttons and drops the labels. Every group shares one
setting, so picking a language on one example switches all of them, and the
choice is remembered in the browser.

```markdown
<!-- tabs:start -->
<!-- tab: Rust -->
**Rust**

...markdown, including fenced code...
<!-- tab: Python -->
**Python**

...markdown...
<!-- tabs:end -->
```

The tab styles and script live in `assets/gitbook/custom-local.css` and
`assets/gitbook/custom-local.js`, the theme's designated customisation files.
