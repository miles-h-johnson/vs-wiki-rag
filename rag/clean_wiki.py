from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIKI_DIR = (ROOT / "../vs_modding_wiki").resolve()
CLEANED_DIRNAME = "cleaned"

LINKED_IMAGE_RE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\(<[^>]*>(?:\s+\"[^\"]*\")?\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
BLANK_RUN_RE = re.compile(r"\n{3,}")

# The wiki appends one or two navboxes to every page; they are pure link lists and
# dominate retrieval for navigation-style queries if left in.
FOOTER_MARKERS = ("**Wondering where some links have gone?**", "**Modding**")


def is_navigation_page(relative_path: Path) -> bool:
    return relative_path.name == "index.md" or relative_path.stem.endswith("_Portal")


def strip_footer(lines: list[str]) -> list[str]:
    # Search only after the last heading: some pages embed an example navbox mid-page.
    last_heading = max((i for i, line in enumerate(lines) if line.startswith("#")), default=0)
    for i in range(last_heading, len(lines)):
        line = lines[i]
        if line.strip() in FOOTER_MARKERS:
            following = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if line.strip() != "**Modding**" or following == "---":
                return lines[:i]
    return lines


def clean_page(text: str) -> str:
    text = LINKED_IMAGE_RE.sub("", text)
    text = IMAGE_RE.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    lines = strip_footer(lines)
    cleaned = "\n".join(lines).strip()
    return BLANK_RUN_RE.sub("\n\n", cleaned) + "\n"


def clean_all(wiki_dir: Path) -> int:
    out_dir = wiki_dir / CLEANED_DIRNAME
    written = 0
    for source in sorted(wiki_dir.rglob("*.md")):
        relative = source.relative_to(wiki_dir)
        if relative.parts[0] == CLEANED_DIRNAME or is_navigation_page(relative):
            continue
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(clean_page(source.read_text(encoding="utf-8")), encoding="utf-8")
        written += 1
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strip navigation and images from the downloaded wiki")
    parser.add_argument("--wiki-dir", type=Path, default=WIKI_DIR, help="Folder written by download_vs_modding_wiki.py")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = clean_all(args.wiki_dir)
    print(f"Wrote {count} cleaned pages to {args.wiki_dir / CLEANED_DIRNAME}")


if __name__ == "__main__":
    main()
