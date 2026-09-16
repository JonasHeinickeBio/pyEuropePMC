# Documentation

This page explains how the pyEuropePMC documentation is built and published today, how to connect it to GitBook with Git Sync, how to add a page, and how to check links before you open a pull request.

## Where the pages live

The documentation is the Markdown in `docs/`:

- `docs/README.md` is the first page.
- `docs/SUMMARY.md` is the table of contents that GitBook uses.
- `.gitbook.yaml` in the repository root sets `root: ./docs/`, so GitBook reads only `docs/`.

Every page has to render in three places: on GitHub, on the GitHub Pages site and on GitBook. Write plain Markdown:

- Link to files with relative paths, such as `../api/search-client.md`. To link to a folder, link to its `README.md`.
- Link to anything outside `docs/`, such as example scripts or test fixtures, with a full `https://github.com/JonasHeinickeBio/pyEuropePMC/...` URL. Neither GitBook nor GitHub Pages publishes those files.
- Do not use GitBook-only blocks such as hints or tabs.
- Do not write two opening curly braces in a row, or an opening curly brace followed by a percent sign, even in code blocks. Jekyll reads both as Liquid template syntax: it drops the text or fails the build.

## How the docs are published today

The site is served by GitHub Pages at https://jonasheinickebio.github.io/pyEuropePMC/.

- **Pages settings.** The Pages source is "Deploy from a branch", with branch `main` and folder `/docs`. On every push to `main`, GitHub's built-in `pages-build-deployment` workflow builds `docs/` with Jekyll and publishes it. There is no `_config.yml`, so the GitHub Pages defaults apply. Jekyll turns each `README.md` into its folder's index page and rewrites links to `.md` files so that they point at the generated pages. `SUMMARY.md` becomes an ordinary page, and the site has no navigation sidebar.
- **`.github/workflows/deploy-docs.yml`.** On pull requests that change `docs/`, it builds the site with `actions/jekyll-build-pages`, so a build error shows up in review. On pushes to `main` that change `docs/`, it builds the site again and deploys it with `actions/deploy-pages`. Such a push therefore deploys the same site twice.

## Connect GitBook

GitBook's Git Sync links a GitBook space to one branch of this repository, in both directions: merging a change request in GitBook commits to that branch, and commits to the branch update GitBook. With `.gitbook.yaml` in place, the space uses `docs/README.md` as its first page and `docs/SUMMARY.md` as its navigation.

GitBook needs to push to the synced branch. The "Protect Main" ruleset rejects every direct push to `main` and has no bypass list; see [CI, branch protection and releases](ci-and-release-workflow.md). GitBook's troubleshooting guide says that a protected branch works only if the GitBook app may bypass the protection. That leaves three setups:

1. **Sync a dedicated branch.** Sync the space with a branch such as `gitbook`; GitBook creates it during the first sync if it does not exist. Edits made in GitBook land on that branch. Open a pull request from `gitbook` to `main`, where the required checks run, and merge `main` back into `gitbook` so GitBook picks up changes made through other pull requests. The GitBook site shows the `gitbook` branch, which can be ahead of or behind `main`.
2. **Edit only on GitHub.** Sync the space with `main` and make every change through a pull request on GitHub. Do not merge change requests in GitBook: their commits to `main` are rejected and the sync reports an error.
3. **Let the GitBook app bypass the ruleset.** Add `gitbook-com` as a bypass actor for "Require a pull request before merging". This ends the rule that nothing reaches `main` without a pull request, so it is a decision for the maintainers.

To connect the space:

1. Install the [GitBook GitHub app](https://github.com/apps/gitbook-com) for the `JonasHeinickeBio` account with access to this repository.
2. In GitBook, set up GitHub Sync, select `JonasHeinickeBio/pyEuropePMC` and the branch for the setup you chose, and map the space to the repository root (`./`), where `.gitbook.yaml` is.
3. For the first sync, make the repository the source of truth with GitBook's **Swap direction** option, so that the repository content replaces the space's content.
4. Manage `README.md` files in the repository, not in the GitBook editor, which can create duplicates.

When GitBook serves the docs, update the links that point to the GitHub Pages site (the repository README, the issue greeting and the MCP server README) and decide whether to keep publishing to GitHub Pages.

## Add a page

1. Create the Markdown file in the folder of its section, for example `docs/features/my-feature.md`. Start with a `#` title in sentence case and one or two sentences that say what the page covers.
2. Add the page to `docs/SUMMARY.md`. `##` headings are groups; indent an entry by two spaces to make it a child of the entry above. List each file only once:

   ```markdown
   ## Features

   * [Search](features/search/README.md)
     * [My feature](features/my-feature.md)
   ```

3. Link to the new page from related pages.
4. Check the links, and run the page's Python examples.

GitBook takes its navigation from `SUMMARY.md` only. GitHub Pages ignores `SUMMARY.md`, so readers there find the page only through links from other pages.

## Check links

Save this script outside the repository, for example as `check_docs_links.py`, and run it from the repository root with `python check_docs_links.py`. It reports links to missing files, links to folders, links that leave `docs/`, and anchors that match no heading. It uses GitHub's heading IDs, which can differ from GitBook's for headings with punctuation. External links are not checked.

```python
"""Report broken relative links in docs/. Run from the repository root."""

import re
import sys
from functools import lru_cache
from pathlib import Path

DOCS = Path("docs").resolve()
FENCE = re.compile(r"^ {0,3}(\x60{3,}|~{3,}).*?^ {0,3}\1[\x60~]*[ \t]*$", re.M | re.S)
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)


@lru_cache(maxsize=None)
def anchors(page: Path) -> frozenset:
    found, seen = set(), {}
    for title in HEADING.findall(FENCE.sub("", page.read_text(encoding="utf-8"))):
        title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title).replace("\x60", "")
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        found.add(f"{slug}-{seen[slug]}" if slug in seen else slug)
        seen[slug] = seen.get(slug, 0) + 1
    return frozenset(found)


problems = 0
for page in sorted(DOCS.rglob("*.md")):
    text = FENCE.sub("", page.read_text(encoding="utf-8"))
    text = re.sub(r"\x60[^\x60\n]*\x60", "", text)  # ignore inline code
    for target in LINK.findall(text):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):  # https:, mailto: and so on
            continue
        path, _, anchor = target.partition("#")
        dest = (page.parent / path).resolve() if path else page
        if not dest.exists():
            problem = "file does not exist"
        elif dest != DOCS and DOCS not in dest.parents:
            problem = "leaves docs/; use a GitHub URL"
        elif dest.is_dir():
            problem = "links to a folder; link to its README.md"
        elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
            problem = f"no heading matches #{anchor}"
        else:
            continue
        problems += 1
        print(f"{page.relative_to(DOCS.parent)}: {target}: {problem}")

print(f"{problems} problem(s) found")
sys.exit(1 if problems else 0)
```
