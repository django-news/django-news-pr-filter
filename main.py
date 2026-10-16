#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Drafts the "Updates to Django" section for https://django-news.com.

Pulls the PRs merged into django/django during a week (Monday until Sunday)
with the `gh` CLI and prints a Markdown block ready to paste into Buttondown:

- the presenter line, when --presenter is given
- the synopsis paragraph (PR count, contributors, first-time contributors)
- "New in Django X.Y:" bullets taken from the release notes those PRs added

Notes for the editor (PRs we could not turn into bullets, long-running PRs)
are printed to stderr so they never end up in the newsletter.
"""

import argparse
import dataclasses
import datetime
import json
import logging
import re
import subprocess
import sys
import urllib.parse

REPO = "django/django"
PRS_LIMIT = 200
RELEASE_NOTES_RE = re.compile(r"^docs/releases/(?P<version>\d+\.\d+(?:\.\d+)?)\.txt$")

DEFAULT_PRESENTER_ORG = "Djangonaut Space"

logger = logging.getLogger("django-news-pr-filter")


@dataclasses.dataclass
class Author:
    login: str
    name: str = ""

    @property
    def url(self) -> str:
        return f"https://github.com/{self.login}"

    @property
    def display_name(self) -> str:
        return self.name.strip() or self.login


@dataclasses.dataclass
class PR:
    number: int
    title: str
    url: str
    author: Author
    created: datetime.date
    release_note_files: list[str]


@dataclasses.dataclass
class ReleaseNote:
    version: str  # "6.1", the X.Y the note is grouped under
    text: str  # Markdown
    pr: PR


def gh(*args: str) -> str:
    logger.debug("gh %s", " ".join(args))
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"`gh {' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout


def parse_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f'Invalid date format {value}. Should be "YYYY-MM-DD".'
        )


def last_week(today: datetime.date) -> tuple[datetime.date, datetime.date]:
    monday = today - datetime.timedelta(days=today.weekday() + 7)
    return monday, monday + datetime.timedelta(days=6)


# --- GitHub ---


def fetch_prs(start: datetime.date, end: datetime.date) -> list[PR]:
    output = gh(
        "pr", "list",
        "--repo", REPO,
        "--state", "merged",
        "--search", f"merged:{start}..{end}",
        "--limit", str(PRS_LIMIT),
        "--json", "number,title,url,author,files,createdAt",
    )  # fmt: skip
    prs = []
    for item in json.loads(output):
        author = item["author"] or {}
        prs.append(
            PR(
                number=item["number"],
                title=item["title"],
                url=item["url"],
                author=Author(login=author.get("login", "ghost"), name=author.get("name") or ""),
                created=datetime.date.fromisoformat(item["createdAt"][:10]),
                release_note_files=[
                    f["path"] for f in item["files"] if RELEASE_NOTES_RE.match(f["path"])
                ],
            )
        )
    if len(prs) == PRS_LIMIT:
        logger.warning("Hit the %s PR limit, results may be incomplete.", PRS_LIMIT)
    return prs


def is_first_time_contributor(login: str, start: datetime.date) -> bool:
    """True when `login` had no PR merged into Django before `start`."""
    query = f"repo:{REPO} is:pr is:merged author:{login} merged:<{start}"
    count = gh("api", "-X", "GET", "search/issues", "-f", f"q={query}", "-q", ".total_count")
    return int(count) == 0


def fetch_diff(pr: PR) -> str:
    return gh("pr", "diff", str(pr.number), "--repo", REPO)


# --- Release notes ---


def added_release_notes(diff: str) -> dict[str, list[str]]:
    """
    Returns the RST blocks a diff adds to docs/releases/*.txt, keyed by the
    release notes version ("6.1.2").

    Only pure additions count. Edits to existing notes (rewording, reflowing
    old release notes) are skipped, except for replacing the "* ..."
    placeholder that unreleased notes start with.
    """
    notes: dict[str, list[str]] = {}
    version = None
    removed: list[str] = []
    added: list[str] = []

    def flush():
        if version and added and all(line.strip() in ("", "...", "* ...") for line in removed):
            notes.setdefault(version, []).extend(split_blocks(added))
        removed.clear()
        added.clear()

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            flush()
            path = line.split(" b/", 1)[-1]
            match = RELEASE_NOTES_RE.match(path)
            version = match["version"] if match else None
        elif line.startswith(("+++", "---")):
            continue
        elif line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
        else:
            flush()
    flush()
    return notes


def split_blocks(lines: list[str]) -> list[str]:
    """Splits added RST lines into bullet/paragraph blocks, dropping headings,
    directives, and code blocks."""
    blocks = []
    current: list[str] = []
    for line in [*lines, ""]:
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append(current)
        current = []

    results = []
    for block in blocks:
        # Section headings are a line followed by an underline (=, -, ~, ^).
        if any(re.fullmatch(r"([=\-~^*])\1+", line.strip()) for line in block):
            continue
        first = block[0]
        if first.lstrip().startswith(".. ") or first.startswith("    "):
            continue
        bullets = []
        for line in block:
            if line.startswith("* "):
                bullets.append([line[2:]])
            elif bullets:
                bullets[-1].append(line)
            else:
                bullets.append([line])
        for bullet in bullets:
            text = " ".join(part.strip() for part in bullet)
            if text and text != "...":
                results.append(text)
    return results


PLAIN_ROLES = {"doc", "ref", "term"}


def _role(match: re.Match) -> str:
    role, content = match["role"], match["content"]
    if role == "ticket":
        return f"[#{content}](https://code.djangoproject.com/ticket/{content})"
    if role == "cve":
        return f"[CVE-{content}](https://www.cve.org/CVERecord?id=CVE-{content})"
    if role in ("rfc", "pep"):
        return f"{role.upper()} {content}"

    if explicit := re.fullmatch(r"(?s)(?P<text>.+?)\s*<[^>]+>", content):
        text = explicit["text"]
    else:
        text = content.lstrip(".")
        if text.startswith("~"):
            text = text[1:].rsplit(".", 1)[-1]
    return text if role in PLAIN_ROLES else f"`{text}`"


def rst_to_markdown(text: str) -> str:
    text = re.sub(r":(?:[\w-]+:)?(?P<role>[\w-]+):`(?P<content>[^`]+)`", _role, text)
    text = re.sub(r"``(.+?)``", r"`\1`", text)
    text = re.sub(r"\\(.)", r"\1", text)  # ``ManyToManyField``\s
    return text


LEAD_STOP_WORDS = {"in", "where", "when", "that", "which", "with", "for", "on", "if"}


def link_lead(text: str, url: str) -> str:
    """Links the opening words of a note to its PR, the way the newsletter does:
    "[Fixed a visual regression](...) in Django 6.1 where ..." or
    "[The new](...) `setting` ...". Falls back to a trailing PR link."""
    words = text.split(" ")
    fixed = text.startswith("Fixed")
    lead = []
    for word in words[: 5 if fixed else 2]:
        if any(char in word for char in "`[]()") or (fixed and word in LEAD_STOP_WORDS):
            break
        lead.append(word)
    if len(lead) < 2:
        number = url.rstrip("/").rsplit("/", 1)[-1]
        return f"{text} ([PR #{number}]({url}))"
    rest = " ".join(words[len(lead) :])
    return f"[{' '.join(lead)}]({url}) {rest}".rstrip()


def collect_release_notes(prs: list[PR]) -> tuple[list[ReleaseNote], list[PR]]:
    notes: list[ReleaseNote] = []
    skipped: list[PR] = []
    seen: set[str] = set()
    for pr in prs:
        if not pr.release_note_files:
            continue
        found = False
        for version, blocks in added_release_notes(fetch_diff(pr)).items():
            for block in blocks:
                text = rst_to_markdown(block)
                if text in seen:  # the same note backported to several files
                    continue
                seen.add(text)
                found = True
                major_minor = ".".join(version.split(".")[:2])
                notes.append(ReleaseNote(major_minor, link_lead(text, pr.url), pr))
        if not found:
            skipped.append(pr)
    return notes, skipped


# --- Markdown ---


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def synopsis(prs: list[PR], first_timers: list[Author], start, end) -> str:
    query = urllib.parse.quote(f"is:pr merged:{start}..{end}")
    contributors = {pr.author.login for pr in prs}
    text = (
        f"Last week we had [{plural(len(prs), 'pull request')}]"
        f"(https://github.com/{REPO}/pulls?q={query}) merged into Django by "
        f"{plural(len(contributors), 'different contributor')}"
    )
    if not first_timers:
        return f"{text}."
    if len(first_timers) == 1:
        text += " - including a first-time contributor!"
    else:
        text += f" - including {len(first_timers)} first-time contributors!"
    names = join_names([f"[{a.display_name}]({a.url})" for a in first_timers])
    return (
        f"{text} Congratulations to {names} for having their first commits "
        f"merged into Django - welcome on board!"
    )


def render(presenter_line: str | None, synopsis_text: str, notes: list[ReleaseNote]) -> str:
    parts = ["## Updates to Django", presenter_line, synopsis_text]
    parts = [part for part in parts if part]
    versions = sorted(
        {note.version for note in notes},
        key=lambda v: tuple(int(n) for n in v.split(".")),
        reverse=True,
    )
    for version in versions:
        bullets = "\n".join(f"- {n.text}" for n in notes if n.version == version)
        parts.append(f"New in Django {version}:\n\n{bullets}")
    return "\n\n".join(parts) + "\n"


def presenter_line(name: str, url: str, org: str) -> str:
    who = f"[{name}]({url})" if url else name
    return f'Today, "Updates to Django" is presented by {who} from {org}! 🚀'


def main(argv=None) -> int:
    default_start, default_end = last_week(datetime.date.today())
    parser = argparse.ArgumentParser(
        prog="django-news-pr-filter",
        description="Drafts the 'Updates to Django' section from last week's merged PRs.",
    )
    parser.add_argument("-s", "--start-date", "--start_date", type=parse_date, default=default_start,
                        help=f"First day of merged PRs to include (default: {default_start}).")  # fmt: skip
    parser.add_argument("-e", "--end-date", "--end_date", type=parse_date, default=default_end,
                        help=f"Last day of merged PRs to include (default: {default_end}).")  # fmt: skip
    parser.add_argument("-o", "--output-file", "--output_file",
                        help="Write the Markdown to this file instead of stdout.")  # fmt: skip
    parser.add_argument("--presenter",
                        help="Adds the 'presented by' line, e.g. --presenter Raffaella.")  # fmt: skip
    parser.add_argument("--presenter-url")
    parser.add_argument("--presenter-org", default=DEFAULT_PRESENTER_ORG)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
    start, end = args.start_date, args.end_date

    logger.info("Loading PRs merged %s..%s", start, end)
    prs = fetch_prs(start, end)
    logger.info("Found %s", plural(len(prs), "PR"))

    first_timers = []
    for author in {pr.author.login: pr.author for pr in prs}.values():
        if is_first_time_contributor(author.login, start):
            logger.info("First-time contributor: %s", author.display_name)
            first_timers.append(author)

    notes, skipped = collect_release_notes(prs)

    markdown = render(
        presenter_line(args.presenter, args.presenter_url, args.presenter_org)
        if args.presenter
        else None,
        synopsis(prs, first_timers, start, end),
        notes,
    )
    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(markdown)
        logger.info("Wrote %s", args.output_file)
    else:
        sys.stdout.write(markdown)

    # Editor notes go to stderr so they never end up in the newsletter.
    for pr in skipped:
        logger.info("Touched release notes but added no new note (edit?): %s %s", pr.url, pr.title)
    six_months_ago = end - datetime.timedelta(days=182)
    for pr in prs:
        if pr.created < six_months_ago:
            logger.info("Long-running PR (opened %s): %s %s", pr.created, pr.url, pr.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
