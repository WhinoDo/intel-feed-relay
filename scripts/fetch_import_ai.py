"""Refresh Import AI without replacing the last valid snapshot on failure."""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path


SOURCES = (
    ("https://importai.substack.com/feed", False),
    ("https://jack-clark.net/feed/", False),
    ("https://importai.substack.com/api/v1/archive?sort=new&offset=0&limit=30", True),
    ("https://rsshub.app/substack/importai", False),
    ("https://morss.it/https://importai.substack.com/feed", False),
)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds 8 MiB")
    return payload


def archive_to_rss(payload):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Import AI"
    ET.SubElement(channel, "link").text = "https://importai.substack.com"
    ET.SubElement(channel, "description").text = "Import AI (relay)"
    for post in json.loads(payload):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post["title"]
        ET.SubElement(item, "link").text = post["canonical_url"]
        date = datetime.fromisoformat(post["post_date"].replace("Z", "+00:00"))
        ET.SubElement(item, "pubDate").text = format_datetime(date)
        ET.SubElement(item, "description").text = post.get("subtitle") or ""
    return ET.tostring(root, encoding="utf-8")


def validate(payload):
    text = payload.decode("utf-8")
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", text)
    root = ET.fromstring(text)
    channel = root.find("channel") if root.tag == "rss" else None
    if channel is None or not channel.findall("item"):
        raise ValueError("not a nonempty RSS feed")
    dates = []
    for item in channel.findall("item"):
        if not item.findtext("title") or not item.findtext("link"):
            raise ValueError("missing article identity")
        date = parsedate_to_datetime(item.findtext("pubDate") or "")
        dates.append(date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date)
    for item in channel.findall("item")[30:]:
        channel.remove(item)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), max(dates)


def refresh(path, fetch=download):
    previous = None
    if path.exists():
        try:
            _, previous = validate(path.read_bytes())
        except (ValueError, ET.ParseError, UnicodeError):
            pass
    for url, archive in SOURCES:
        try:
            payload = fetch(url)
            payload, latest = validate(archive_to_rss(payload) if archive else payload)
            if previous is not None and latest < previous:
                raise ValueError("candidate is older than the saved feed")
        except Exception as error:
            # Never print response bodies, which may be upstream error pages.
            print(f"Import AI fetch failed ({url.split('/')[2]}): {type(error).__name__}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(".import-ai.xml.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        print(f"Import AI refreshed; latest article: {latest.isoformat()}")
        return 0
    print("::warning::Import AI refresh failed; saved snapshot retained and may be stale")
    return 1


if __name__ == "__main__":
    sys.exit(refresh(Path("out/import-ai.xml")))
