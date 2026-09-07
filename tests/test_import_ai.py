import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.fetch_import_ai import MAX_RESPONSE_BYTES, SOURCES, download, refresh, validate


def feed(date, title="Import AI"):
    return (
        f"<rss><channel><item><title>{title}</title>"
        f"<link>https://importai.substack.com/p/test</link><pubDate>{date}</pubDate>"
        "</item></channel></rss>"
    ).encode()


OLD = feed("Mon, 03 Aug 2026 13:31:22 GMT")
NEW = feed("Mon, 31 Aug 2026 13:31:06 GMT")


class RefreshTests(unittest.TestCase):
    def setUp(self):
        output = patch("sys.stdout", new=io.StringIO())
        output.start()
        self.addCleanup(output.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "import-ai.xml"
        self.path.write_bytes(OLD)

    def test_saved_file_does_not_skip_fallback(self):
        archive = json.dumps([{
            "title": "Import AI 471", "canonical_url": "https://importai.substack.com/p/471",
            "post_date": "2026-08-31T13:31:06Z", "subtitle": "A & B",
        }]).encode()
        fetch = Mock(side_effect=[TimeoutError(), TimeoutError(), archive])
        self.assertEqual(refresh(self.path, fetch), 0)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(validate(self.path.read_bytes())[1], validate(NEW)[1])
        self.assertIn(b"A &amp; B", self.path.read_bytes())

    def test_all_network_failures_preserve_saved_snapshot(self):
        fetch = Mock(side_effect=TimeoutError)
        self.assertEqual(refresh(self.path, fetch), 1)
        self.assertEqual(fetch.call_count, len(SOURCES))
        self.assertEqual(self.path.read_bytes(), OLD)

    def test_error_pages_and_empty_archive_preserve_saved_snapshot(self):
        fetch = Mock(side_effect=[b"<html>Blocked</html>", b"invalid", b"[]", b"<rss><channel/></rss>", b"invalid"])
        self.assertEqual(refresh(self.path, fetch), 1)
        self.assertEqual(self.path.read_bytes(), OLD)

    def test_candidate_cannot_roll_back_to_older_articles(self):
        self.path.write_bytes(NEW)
        fetch = Mock(side_effect=[OLD, OLD, b"[]", OLD, OLD])
        self.assertEqual(refresh(self.path, fetch), 1)
        self.assertEqual(self.path.read_bytes(), NEW)

    def test_valid_direct_response_stops_fallbacks(self):
        fetch = Mock(return_value=NEW)
        self.assertEqual(refresh(self.path, fetch), 0)
        fetch.assert_called_once_with(SOURCES[0][0])
        self.assertEqual(validate(self.path.read_bytes())[1], validate(NEW)[1])
        self.assertFalse(self.path.with_name(".import-ai.xml.tmp").exists())

    def test_no_snapshot_is_created_on_total_failure(self):
        self.path.unlink()
        self.assertEqual(refresh(self.path, Mock(side_effect=TimeoutError)), 1)
        self.assertFalse(self.path.exists())

    def test_author_feed_fallback_keeps_original_official_link(self):
        author_link = b"https://jack-clark.net/2026/08/31/import-ai-471/"
        author_feed = NEW.replace(b"https://importai.substack.com/p/test", author_link)
        fetch = Mock(side_effect=[TimeoutError(), author_feed])
        self.assertEqual(refresh(self.path, fetch), 0)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args.args[0], "https://jack-clark.net/feed/")
        self.assertIn(author_link, self.path.read_bytes())
        self.assertEqual(validate(self.path.read_bytes())[1], validate(NEW)[1])


class ResponseSizeTests(unittest.TestCase):
    def test_response_at_limit_is_accepted(self):
        payload = b"x" * MAX_RESPONSE_BYTES
        with patch("scripts.fetch_import_ai.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            self.assertEqual(download(SOURCES[0][0]), payload)

    def test_response_over_limit_is_rejected(self):
        payload = b"x" * (MAX_RESPONSE_BYTES + 1)
        with patch("scripts.fetch_import_ai.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            with self.assertRaisesRegex(ValueError, "exceeds 8 MiB"):
                download(SOURCES[0][0])


if __name__ == "__main__":
    unittest.main()
