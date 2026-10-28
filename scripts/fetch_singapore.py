"""Download the Singapore-law contracts in datasets/singapore/manifest.yaml and save them as text.

SEC asks every automated request to say who is making it, so this needs a User-Agent with a
contact, for example:
    set SEC_USER_AGENT=Your Name your.email@example.com
    python scripts/fetch_singapore.py

Raw HTML goes to data/singapore/raw/ and plain text to data/singapore/text/ (both gitignored).
"""

import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "singapore" / "manifest.yaml"
OUT = ROOT / "data" / "singapore"
BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "title"}


class _TextParser(HTMLParser):
    """Keeps the visible text and starts a new line at block-level tags."""

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    text = "".join(parser.parts).replace("\xa0", " ")
    # I collapse runs of spaces inside lines, then keep at most one blank line between blocks
    # so paragraph numbering in the viewer stays sensible.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def main() -> None:
    agent = os.environ.get("SEC_USER_AGENT")
    if not agent:
        sys.exit("Set SEC_USER_AGENT to your name and email first (SEC requires a contact).")
    contracts = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["contracts"]
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    (OUT / "text").mkdir(parents=True, exist_ok=True)
    for c in contracts:
        raw = OUT / "raw" / f"{c['id']}.htm"
        if not raw.exists():
            req = urllib.request.Request(c["url"], headers={"User-Agent": agent})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw.write_bytes(resp.read())
            # SEC allows 10 requests a second; one every half second is well inside that.
            time.sleep(0.5)
        text = html_to_text(raw.read_bytes().decode("utf-8", errors="replace"))
        (OUT / "text" / f"{c['id']}.txt").write_text(text, encoding="utf-8")
        # A quick check that the download is the contract I expected.
        law = re.search(r"laws? of (the Republic of )?Singapore", text, re.IGNORECASE)
        print(f"{c['id']}: {len(text):,} chars, Singapore law {'found' if law else 'NOT found'}")


if __name__ == "__main__":
    main()
