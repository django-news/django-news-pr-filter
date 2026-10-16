import datetime
import unittest

from django_news_pr_filter.main import (
    PR,
    Author,
    added_release_notes,
    last_week,
    link_lead,
    rst_to_markdown,
    synopsis,
)

URL = "https://github.com/django/django/pull/22057"

BUGFIX_DIFF = """\
diff --git a/django/db/models/functions/text.py b/django/db/models/functions/text.py
+    return value.lower()
diff --git a/docs/releases/6.1.2.txt b/docs/releases/6.1.2.txt
index 7aedfda4b467..c5814dd1bca8 100644
--- a/docs/releases/6.1.2.txt
+++ b/docs/releases/6.1.2.txt
@@ -21,6 +21,12 @@ Bugfixes
 * Fixed a bug in Django 6.1 where the ``fields.W225`` system check incorrectly
   warned that ``null`` has no effect on ``GeneratedField`` (:ticket:`37348`).

+* Fixed a bug in Django 6.1 where the
+  :class:`~django.db.models.functions.UUID4` function persisted uppercase
+  values on Oracle (:ticket:`37376`).
+
 * Fixed a bug in Django 6.1 where ``FETCH_PEERS`` did not batch instances
"""

PLACEHOLDER_DIFF = """\
diff --git a/docs/releases/6.2.txt b/docs/releases/6.2.txt
--- a/docs/releases/6.2.txt
+++ b/docs/releases/6.2.txt
@@ -147,7 +147,9 @@ Decorators
 Email
 ~~~~~

-* ...
+* The :setting:`ADMINS` and :setting:`SERVER_EMAIL` settings now support
+  :class:`~email.headerregistry.Address` objects.

"""

REFLOW_DIFF = """\
diff --git a/docs/releases/2.0.txt b/docs/releases/2.0.txt
--- a/docs/releases/2.0.txt
+++ b/docs/releases/2.0.txt
@@ -280,9 +280,8 @@ Models
 * The new :meth:`connection.execute_wrapper()
-  <django.db.backends.base.DatabaseWrapper.execute_wrapper>` method allows
-  :doc:`installing wrappers around execution of database queries
-  </topics/db/instrumentation>`.
+  <django.db.connection.execute_wrapper>` method allows :doc:`installing
+  wrappers around execution of database queries </topics/db/instrumentation>`.
"""

FEATURE_DIFF = """\
diff --git a/docs/releases/6.2.txt b/docs/releases/6.2.txt
--- a/docs/releases/6.2.txt
+++ b/docs/releases/6.2.txt
@@ -30,0 +30,12 @@
+Shiny new thing
+---------------
+
+The new :class:`~django.Thing` does things::
+
+    thing = Thing()
+
+.. versionadded:: 6.2
+
"""


class AddedReleaseNotesTests(unittest.TestCase):
    def test_bugfix(self):
        self.assertEqual(
            added_release_notes(BUGFIX_DIFF),
            {
                "6.1.2": [
                    "Fixed a bug in Django 6.1 where the "
                    ":class:`~django.db.models.functions.UUID4` function persisted "
                    "uppercase values on Oracle (:ticket:`37376`)."
                ]
            },
        )

    def test_replaces_placeholder(self):
        notes = added_release_notes(PLACEHOLDER_DIFF)
        self.assertEqual(list(notes), ["6.2"])
        self.assertTrue(notes["6.2"][0].startswith("The :setting:`ADMINS`"))

    def test_skips_edits_to_existing_notes(self):
        self.assertEqual(added_release_notes(REFLOW_DIFF), {})

    def test_skips_headings_code_and_directives(self):
        self.assertEqual(
            added_release_notes(FEATURE_DIFF),
            {"6.2": ["The new :class:`~django.Thing` does things::"]},
        )


class RstToMarkdownTests(unittest.TestCase):
    def test_roles(self):
        cases = {
            ":class:`~django.db.models.functions.UUID4`": "`UUID4`",
            ":meth:`.QuerySet.in_bulk`": "`QuerySet.in_bulk`",
            ":meth:`distinct(*fields) <.QuerySet.distinct>`": "`distinct(*fields)`",
            ":setting:`MAILERS`": "`MAILERS`",
            ":ref:`network rasters <gdal-raster-network>`": "network rasters",
            ":doc:`fetch modes </topics/db/fetch-modes>`": "fetch modes",
            ":rfc:`2231`": "RFC 2231",
            "(:ticket:`37376`)": "([#37376](https://code.djangoproject.com/ticket/37376))",
            ":cve:`2026-15830`": "[CVE-2026-15830](https://www.cve.org/CVERecord?id=CVE-2026-15830)",
            "``ManyToManyField``\\s": "`ManyToManyField`s",
        }
        for rst, markdown in cases.items():
            with self.subTest(rst=rst):
                self.assertEqual(rst_to_markdown(rst), markdown)


class LinkLeadTests(unittest.TestCase):
    def test_fixed(self):
        self.assertEqual(
            link_lead("Fixed a visual regression in Django 6.1 where ...", URL),
            f"[Fixed a visual regression]({URL}) in Django 6.1 where ...",
        )

    def test_feature(self):
        self.assertEqual(
            link_lead("The new `maybe_aclosing` returns ...", URL),
            f"[The new]({URL}) `maybe_aclosing` returns ...",
        )

    def test_falls_back_to_trailing_link(self):
        self.assertEqual(
            link_lead("The `ADMINS` setting ...", URL),
            f"The `ADMINS` setting ... ([PR #22057]({URL}))",
        )


class SynopsisTests(unittest.TestCase):
    start = datetime.date(2026, 9, 28)
    end = datetime.date(2026, 10, 4)

    def pr(self, login, name=""):
        return PR(1, "", URL, Author(login, name), self.start, [])

    def test_no_first_timers(self):
        prs = [self.pr("a"), self.pr("a"), self.pr("b")]
        self.assertEqual(
            synopsis(prs, [], self.start, self.end),
            "Last week we had [3 pull requests](https://github.com/django/django/pulls"
            "?q=is%3Apr%20merged%3A2026-09-28..2026-10-04) merged into Django by "
            "2 different contributors.",
        )

    def test_first_timers(self):
        authors = [Author("a", "Ann "), Author("b"), Author("c", "Cy")]
        text = synopsis([self.pr(a.login) for a in authors], authors, self.start, self.end)
        self.assertIn(
            " - including 3 first-time contributors! Congratulations to "
            "[Ann](https://github.com/a), [b](https://github.com/b) and "
            "[Cy](https://github.com/c) for having their first commits merged "
            "into Django - welcome on board!",
            text,
        )

    def test_one_first_timer(self):
        author = Author("a", "Ann")
        text = synopsis([self.pr("a")], [author], self.start, self.end)
        self.assertIn("1 pull request]", text)
        self.assertIn("by 1 different contributor - including a first-time contributor!", text)


class LastWeekTests(unittest.TestCase):
    def test_monday_to_sunday(self):
        self.assertEqual(
            last_week(datetime.date(2026, 10, 9)),
            (datetime.date(2026, 9, 28), datetime.date(2026, 10, 4)),
        )


if __name__ == "__main__":
    unittest.main()
