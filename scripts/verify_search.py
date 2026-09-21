#!/usr/bin/env python3
"""Check native search/TXT exports for accidentally indexed site navigation."""
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
posts = json.loads((ROOT / 'archive.json').read_text())
json_rows = json.loads((ROOT / 'search.json').read_text())
csv_rows = list(csv.DictReader((ROOT / 'search.csv').open()))
assert len(json_rows) == len(csv_rows) == len(posts)
originals = {post['title']: post['text'].lower() for post in posts}
for row in json_rows + csv_rows:
    for term in ('breck', 'skip to content', '← all writing', 'html | txt', 'view source'):
        if term not in originals[row['title']]:
            assert term not in row['text'].lower(), (row['title'], term)
for post in posts:
    exported = (ROOT / (post['slug'] + '.txt')).read_text().lower()
    for term in ('breck', 'skip to content', '← all writing', 'html | txt', 'view source'):
        if term not in post['text'].lower():
            assert term not in exported, (post['slug'], term)
print(f"PASS: {len(posts)} essays have clean search, JSON, CSV, and TXT exports.")
