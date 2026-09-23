#!/usr/bin/env python3
"""Generate this site's documentation collections from the yard docs tree.

Reads markdown from a sibling checkout of the yard repository, adds Jekyll
front matter, and rewrites relative markdown
links so they resolve on the published site. Links that point outside the docs
tree become links to the file on GitHub. Pages under `docs-site/` are site-owned
and copied in as they are.

`scripts/docs-nav.json` decides which collection each page lands in (by its
permalink) and its order in the sidebar. Pages not listed there are skipped.

Usage:
    scripts/sync-docs.py [--yard ../yard]
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
NAV_FILE = os.path.join(HERE, "docs-nav.json")

YARD_REPO = "https://github.com/sean-mca/yard"

LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
GENERATED_RE = re.compile(r"^<!--\s*generated-by:[^>]*-->\s*\n", re.M)
BACKLINK_RE = re.compile(r"^←\s*\[Back to repo README\]\([^)]*\)\s*\n", re.M)
FRONT_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
TABS_RE = re.compile(r"<!--\s*tabs:start\s*-->\n(.*?)<!--\s*tabs:end\s*-->\n?", re.S)
TAB_RE = re.compile(r"<!--\s*tab:\s*([^>]+?)\s*-->\n")


def load_nav():
    """Map permalink -> (collection, order) from docs-nav.json."""
    with open(NAV_FILE, encoding="utf-8") as f:
        groups = json.load(f)
    nav = {}
    collections = []
    for group in groups:
        collections.append(group["collection"])
        for i, permalink in enumerate(group["pages"], start=1):
            nav[permalink] = (group["collection"], i)
    return nav, collections


def convert_tabs(text):
    """Turn a tabbed region into the site's tab markup.

    Upstream markdown marks a region with HTML comments, which GitHub hides:

        <!-- tabs:start -->
        <!-- tab: Rust -->
        **Rust**

        ...markdown...
        <!-- tab: Python -->
        **Python**

        ...markdown...
        <!-- tabs:end -->

    The bold label line under each tab marker keeps the GitHub rendering
    readable and is dropped here, since the tab button carries the label.
    Every tab group shares the name "lang", so choosing a language on one
    example switches all of them.
    """
    def region(m):
        parts = TAB_RE.split(m.group(1))
        labels = parts[1::2]
        bodies = parts[2::2]
        if not labels:
            return m.group(0)
        buttons = []
        panels = []
        for i, (label, body) in enumerate(zip(labels, bodies)):
            key = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
            body = re.sub(r"^\*\*%s\*\*\s*\n" % re.escape(label), "", body.strip("\n"))
            active = " active" if i == 0 else ""
            buttons.append(
                '<button type="button" role="tab" class="tab%s" data-tab="%s" '
                'aria-selected="%s">%s</button>' % (active, key, "true" if i == 0 else "false", label)
            )
            panels.append(
                '<div class="tab-panel%s" data-tab="%s" role="tabpanel" markdown="1">\n\n%s\n\n</div>'
                % (active, key, body.strip("\n"))
            )
        return (
            '<div class="tabs" data-tabs="lang">\n<div class="tab-list" role="tablist">\n%s\n</div>\n%s\n</div>\n'
            % ("\n".join(buttons), "\n".join(panels))
        )

    return TABS_RE.sub(region, text)


def escape_liquid(text):
    """Keep Liquid from interpreting braces that appear in doc content."""
    text = text.replace("{{", "{% raw %}{{{% endraw %}")
    text = re.sub(r"\{%(?! raw %\}| endraw %\})", "{% raw %}{%{% endraw %}", text)
    return text


def permalink_for(doc_rel):
    """Site URL for a docs-relative source path (README.md is a directory index)."""
    base, _ = os.path.splitext(doc_rel)
    if os.path.basename(base) == "README":
        base = os.path.dirname(base)
    return "/docs/" + (base + "/" if base else "")


def output_path(permalink, collection):
    slug = permalink[len("/docs/"):].strip("/").replace("/", "-") or "index"
    return os.path.join("_" + collection, slug + ".md")


class Site:
    """Knows where every page will be written, so links can be rewritten."""

    def __init__(self, nav):
        self.nav = nav
        self.placed = {}  # permalink -> output path relative to SITE

    def place(self, permalink):
        if permalink not in self.nav:
            return None
        collection, order = self.nav[permalink]
        out = output_path(permalink, collection)
        self.placed[permalink] = out
        return out, order


def rewrite_links(body, doc_rel, docs_root, repo_url, site):
    src_dir = os.path.dirname(doc_rel)

    def repl(m):
        bang, text, target, title = m.groups()
        title = title or ""
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        path, _, anchor = target.partition("#")
        anchor = "#" + anchor if anchor else ""
        resolved = os.path.normpath(os.path.join(src_dir, path))
        abs_target = os.path.normpath(os.path.join(docs_root, resolved))
        inside = not resolved.startswith("..")
        if inside and resolved.endswith(".md") and os.path.isfile(abs_target):
            out = site.placed.get(permalink_for(resolved))
            if out:
                link = "{%% link %s %%}%s" % (out, anchor)
                return "%s[%s](%s%s)" % (bang, text, link, title)
        # Anything else lives in the repository, not on this site.
        repo_path = os.path.normpath(os.path.join("docs", resolved))
        link = "%s/blob/main/%s%s" % (repo_url, repo_path, anchor)
        return "%s[%s](%s%s)" % (bang, text, link, title)

    return LINK_RE.sub(repl, body)


def write_page(out_rel, front, body):
    lines = ["---"]
    for k, v in front.items():
        if isinstance(v, int):
            lines.append("%s: %d" % (k, v))
        else:
            lines.append('%s: "%s"' % (k, str(v).replace('"', '\\"')))
    lines.append("---")
    out_path = os.path.join(SITE, out_rel)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n" + body)
    return out_rel


def convert(src_path, doc_rel, docs_root, repo_url, source_display, site,
            title_override=None):
    permalink = permalink_for(doc_rel)
    placed = site.place(permalink)
    if not placed:
        print("skipping %s (not in docs-nav.json)" % doc_rel, file=sys.stderr)
        return None
    out_rel, order = placed

    with open(src_path, encoding="utf-8") as f:
        body = f.read()
    body = GENERATED_RE.sub("", body)
    body = BACKLINK_RE.sub("", body)
    m = H1_RE.search(body)
    title = title_override or (m.group(1) if m else os.path.basename(doc_rel))
    if m:
        body = body[: m.start()] + body[m.end():]
    body = body.lstrip("\n")
    body = convert_tabs(body)
    body = escape_liquid(body)
    body = rewrite_links(body, doc_rel, docs_root, repo_url, site)
    body = body.rstrip("\n") + (
        "\n\n---\n\n<small>This page is generated from "
        "[the repository](%s). Edit it there.</small>\n" % source_display
    )

    front = {
        "title": title,
        "permalink": permalink,
        "layout": "post",
        "order": order,
        "source": source_display,
    }
    return write_page(out_rel, front, body)


def copy_local(src_path, site):
    """Copy a site-owned page from docs-site/, placing it by its permalink."""
    with open(src_path, encoding="utf-8") as f:
        text = f.read()
    m = FRONT_RE.match(text)
    if not m:
        sys.exit("%s has no front matter" % src_path)
    front = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        front[k.strip()] = v.strip().strip('"')
    permalink = front.get("permalink")
    placed = site.place(permalink) if permalink else None
    if not placed:
        print("skipping %s (not in docs-nav.json)" % src_path, file=sys.stderr)
        return None
    out_rel, order = placed
    front["layout"] = front.get("layout", "post")
    front["order"] = order
    return write_page(out_rel, front, text[m.end():].lstrip("\n"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yard", default=os.path.join(SITE, "..", "yard"))
    args = ap.parse_args()

    docs_root = os.path.abspath(os.path.join(args.yard, "docs"))
    if not os.path.isdir(docs_root):
        sys.exit("docs directory not found: %s" % docs_root)

    nav, collections = load_nav()
    site = Site(nav)
    for collection in collections:
        out_dir = os.path.join(SITE, "_" + collection)
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
        os.makedirs(out_dir)

    # Pass 1: decide where every page goes, so cross-links can be resolved.
    sources = []
    for dirpath, _, files in os.walk(docs_root):
        for name in sorted(files):
            if name.endswith(".md"):
                src = os.path.join(dirpath, name)
                sources.append((src, os.path.relpath(src, docs_root)))
    for _, doc_rel in sources:
        site.place(permalink_for(doc_rel))
    local_dir = os.path.join(SITE, "docs-site")
    local_pages = []
    if os.path.isdir(local_dir):
        for dirpath, _, files in os.walk(local_dir):
            for name in sorted(files):
                if name.endswith(".md"):
                    local_pages.append(os.path.join(dirpath, name))
    for src in local_pages:
        with open(src, encoding="utf-8") as f:
            m = FRONT_RE.match(f.read())
        if m:
            pm = re.search(r'^permalink:\s*"?([^"\n]+)"?', m.group(1), re.M)
            if pm:
                site.place(pm.group(1).strip())

    # Pass 2: write everything.
    written = []
    for src, doc_rel in sources:
        out = convert(src, doc_rel, docs_root, YARD_REPO,
                      "%s/blob/main/docs/%s" % (YARD_REPO, doc_rel), site)
        if out:
            written.append(out)

    for src in local_pages:
        out = copy_local(src, site)
        if out:
            written.append(out)

    for p in written:
        print(p)
    print("%d pages written" % len(written), file=sys.stderr)


if __name__ == "__main__":
    main()
