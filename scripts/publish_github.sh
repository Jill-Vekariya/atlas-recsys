#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo 'Install GitHub CLI first: https://cli.github.com'; exit 1; }
gh auth status >/dev/null
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -b main
git config --get user.name >/dev/null || { echo 'Configure your Git author name before publishing.'; exit 1; }
git config --get user.email >/dev/null || { echo 'Configure your Git author email before publishing.'; exit 1; }
if git remote get-url origin >/dev/null 2>&1; then
  echo 'An origin already exists. Inspect it and push manually to avoid choosing the wrong repository.'
  exit 1
fi
repo="${ATLAS_REPOSITORY:-atlas-recsys}"
visibility="${ATLAS_VISIBILITY:-private}"
case "$visibility" in public|private) ;; *) echo 'Use public or private visibility'; exit 1 ;; esac
git add .
if ! git diff --cached --quiet; then
  git commit -m 'Build Atlas recommendation platform and reproducible benchmarks'
fi
gh repo create "$repo" "--$visibility" --source . --remote origin --push
