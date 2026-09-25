# Anonymous review artifact

Use only the anonymous repository link when sharing this artifact for review.
The identity of a public source-repository owner is not hidden when that source
repository is visited directly. Sanitizing files does not erase earlier public
copies, search-engine caches, or the source repository's Git history.

## Included safeguards

- Navigation audit: **2026-09-25**. All HTML hyperlinks and Markdown text links
  are removed. Local images/video are embedded, not wrapped in links.
  No project link points to an author's profile, personal website, source-repo
  commit, issue tracker, or raw owner-hosted download.
- The README has no external demo/preview link or clickable animation wrapper.
  HTML pages have no repository button or code-repository footer link, including
  anonymous-proxy buttons. The page generator preserves these removals.
- Source attributions render as plain text, never clickable anchors. Original
  provenance URLs remain in JSON, not as links in the demo. Date selection loads
  the chosen local snapshot in place; it never redirects to a second HTML page.
- All four HTML entry points use English text. The older HTML builder delegates
  to the current builder, preventing stale identity links from being regenerated.
- Local data and images are served within the artifact. There are no third-party
  analytics, font downloads, tracking pixels or externally hosted scripts.
  `no-referrer` avoids sending the artifact URL when a source link is followed.
- The manuscript metadata contains no author identity, workstation information
  or creation/modification timezone. Its scholarly content and citations are
  unchanged. News-source attribution and third-party license notices are retained;
  these are not author-identifying project contacts.
- The downloadable review package excludes Git history, environment files,
  private run logs, raw crawls, unused images, caches and local output folders.
- Data generation remains manual-only. Language cleanup and packaging make no
  paid API calls and do not create new certification evidence.

## Snapshot inventory

| Snapshot | Supplied items | Status |
| --- | ---: | --- |
| August 15, 2026 | 200 | English archived snapshot, original schema |
| August 18, 2026 | 171 | English-only subset of the original 200-item legacy split |
| September 5, 2026 | 121 | Incomplete construction preview with recorded trial audits |

The August 18 projection excludes 29 non-English-source records. Retained
questions, answers, evidence, timestamps and panel records are unchanged.
No translated passage is passed off as verbatim source evidence. See
`data/releases/anonymous-review-export.json` for the projection manifest.
The non-English v1 data and internal-language notes are not distributed here.
This revision does not substantiate new model results or a complete daily run.

## Checks before sharing

```bash
python -m unittest discover -s tests -v
python src/check_anonymity.py
python src/check_navigation.py
python src/check_secrets.py
python src/package_anonymous.py --output anonymous-review.zip
```

The anonymity scanner supports an optional `ANON_IDENTITY_TOKENS` environment
variable containing comma-separated private identifiers. Values are never
printed or written into the report. Do not put such identifiers into a committed
test fixture, denylist, example command, or configuration file.

The navigation check rejects HTML hyperlinks and Markdown text links throughout
the artifact, and verifies that embedded media exist locally. Runtime source
attribution and date switching have JavaScript regression tests. These checks
cover the distributed files, not a host's own interface. Source-host account
buttons and image-viewer wrappers added by a hosting platform cannot be disabled
by README content. Share only the anonymous mirror for review. The dated
navigation-audit marker makes stale copies easy to spot.

## Anonymous-host settings

The repository proxy and interactive website are separate features. The
interactive `/w/` route requires website hosting to be enabled by the anonymous
project owner. A disabled website must not redirect reviewers to a personal host.
After a source update, refresh the anonymous mirror and verify its README, HTML,
PDF and download contents, not just the source branch. Configure expiration to
remove/archive access rather than redirect to the original source repository.

If website hosting is unavailable, download the anonymous archive, extract it,
and run `python -m http.server 8000 --bind 127.0.0.1` in its root directory.
Open `http://127.0.0.1:8000/`. This local server makes no model API calls.
