# django-news-pr-filter

The django-news fork of sakhawy/django-news-pr-filter. `main.py` is a single `uv run` script with no dependencies beyond the `gh` CLI; it drafts the "Updates to Django" section of the Django News newsletter.

## Commits and branches

- Work directly on `main` of this fork (git@github.com:django-news/django-news-pr-filter.git); no feature branches or PRs.
- Commit and push when a piece of work is finished.

## Checks

- `python3 -m unittest` (offline tests; no network)
- `uv run main.py -s 2026-09-28 -e 2026-10-04` should match the "Updates to Django" synopsis in Django News issue 358 (13 PRs, 11 contributors, 2 first-time contributors).
