#!/usr/bin/env bash
# Publish docs/site to the public website repo (GitHub Pages):
#   https://github.com/utkualsir/sharkyclips-site -> https://utkualsir.github.io/sharkyclips-site/
# docs/site is the source; the public repo holds only these static files (no source code).
# Commits use the GitHub no-reply address so no personal email lands in the public history.
# Usage: bash docs/publish-site.sh "commit message"
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
msg="${1:-Update website}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
gh repo clone utkualsir/sharkyclips-site "$tmp/site" -- -q
find "$tmp/site" -mindepth 1 -maxdepth 1 ! -name .git ! -name README.md -exec rm -rf {} +
cp -r "$here/site/." "$tmp/site/"
touch "$tmp/site/.nojekyll"
cd "$tmp/site"
git config user.name utkualsir
git config user.email "$(gh api user -q .id)+utkualsir@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then echo "Website already up to date."; exit 0; fi
git commit -q -m "$msg"
git push -q origin main
echo "Pushed. GitHub Pages updates in about a minute: https://utkualsir.github.io/sharkyclips-site/"
