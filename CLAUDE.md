# django-news-pr-filter

The django-news fork of sakhawy/django-news-pr-filter. It is a `src`-layout package (`src/django_news_pr_filter/main.py`, tests in `tests/`) with a Typer CLI that shells out to the `gh` CLI; it drafts the "Updates to Django" section of the Django News newsletter.

## Commits and branches

- Work directly on `main` of this fork (git@github.com:django-news/django-news-pr-filter.git); no feature branches or PRs.
- Commit and push when a piece of work is finished.

## Checks

- `uv run pytest` (offline tests; no network)
- `uv run django-news-pr-filter -s 2026-09-28 -e 2026-10-04` should match the "Updates to Django" synopsis in Django News issue 358 (13 PRs, 11 contributors, 2 first-time contributors).
