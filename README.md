# Django News PR Filter

Drafts the "Updates to Django" section for https://django-news.com from the PRs merged into [django/django](https://github.com/django/django) during a week.

It prints a Markdown block ready to paste into Buttondown:

- the presenter line, when you pass `--presenter`
- the synopsis paragraph: how many PRs were merged, by how many contributors, and who the first-time contributors were
- "New in Django X.Y:" bullets, taken from the release notes those PRs added to `docs/releases/*.txt`

## Installation

1. Install [uv](https://docs.astral.sh/uv/) and the [`gh` CLI](https://github.com/cli/cli?tab=readme-ov-file#installation).

2. Authenticate `gh` with GitHub:

```bash
gh auth login
```

There are no other dependencies.

## Usage

```bash
uv run src/django_news_pr_filter/main.py | pbcopy
```

`uv run` creates the virtualenv and installs the package on first use. `uv run django-news-pr-filter` does the same, or install it with `uv tool install .` and run `django-news-pr-filter` directly.

Without arguments, it covers last week (Monday until Sunday) and writes the Markdown to stdout. Progress and editor notes go to stderr, so they never end up in the copied text.

Example output:

```md
## Updates to Django

Last week we had [13 pull requests](https://github.com/django/django/pulls?q=is%3Apr%20merged%3A2026-09-28..2026-10-04) merged into Django by 11 different contributors - including 2 first-time contributors! Congratulations to [Juliana Nicacio](https://github.com/Mitchina) and [Max Azatian](https://github.com/HardMax71) for having their first commits merged into Django - welcome on board!

New in Django 6.1:

- [Fixed a bug](https://github.com/django/django/pull/22057) in Django 6.1 where the `UUID4` function persisted uppercase values on Oracle. ... ([#37376](https://code.djangoproject.com/ticket/37376)).
- [Fixed a visual regression](https://github.com/django/django/pull/22054) in Django 6.1 where an extra empty breadcrumb was rendered on the admindocs model index page ([#37378](https://code.djangoproject.com/ticket/37378)).
```

The bullets are a draft: they copy the release note wording, so trim or reword them and drop the ones that aren't newsworthy.

The editor notes on stderr list:

- PRs that touched the release notes without adding a new note (typo fixes, reflowed old notes), in case one is worth a mention
- long-running PRs, opened more than six months before the end of the week

### Options

```
usage: django-news-pr-filter [-h] [-s START_DATE] [-e END_DATE] [-o OUTPUT_FILE] [--presenter PRESENTER]
                             [--presenter-url PRESENTER_URL] [--presenter-org PRESENTER_ORG] [-v]

  -s, --start-date      First day of merged PRs to include (default: last Monday).
  -e, --end-date        Last day of merged PRs to include (default: last Sunday).
  -o, --output-file     Write the Markdown to this file instead of stdout.
  --presenter           Adds the "presented by" line with this name, e.g. Raffaella.
  --presenter-url       Link for the presenter's name, e.g. https://mastodon.social/@raffaellasuardini.
  --presenter-org       Presenter's organization (default: Djangonaut Space).
  -v, --verbose         Log every `gh` call.
```

## How it works

- **Merged PRs:** one `gh pr list` search for `merged:START..END`.
- **First-time contributors:** an author is a first-timer when they had no PR merged into Django before the start of the week (one GitHub search per author). People whose earlier contributions predate GitHub PRs can show up as first-timers, so give the names a glance.
- **Release notes:** for each PR that touched `docs/releases/*.txt`, it reads the lines the PR added. Edits to existing notes are skipped, except for replacing the `* ...` placeholder. Section headings, code blocks, and directives are dropped. RST roles become Markdown: `:ticket:` and `:cve:` become links, and code roles like `:class:` become inline code. The opening words of each note link to its PR.

## Tests

```bash
uv run pytest
```
