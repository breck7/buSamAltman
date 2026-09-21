#!/usr/bin/env python3
"""Check complete text preservation and every generated local link/asset."""
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
originals = {}
for file in (ROOT / 'originals').glob('page-*.html'):
    soup = BeautifulSoup(file.read_text(), 'html.parser')
    for post in soup.select('article.post'):
        body = post.select_one('.posthaven-post-body')
        for node in body.select('script,style'):
            node.decompose()
        originals[post.select_one('.post-title a')['href']] = re.sub(r'\s+', '', body.get_text())

posts = json.loads((ROOT / 'archive.json').read_text())
assert len(posts) == len(originals)
for post in posts:
    page = BeautifulSoup((ROOT / (post['slug'] + '.html')).read_text(), 'html.parser')
    body = page.select_one('.prose')
    for node in body.select('.unavailable-image'):
        node.decompose()
    actual = re.sub(r'\s+', '', body.get_text()).replace('Readtheembeddeddocument.', '')
    assert actual == originals[post['url']], 'Text mismatch: ' + post['slug']

for file in ROOT.glob('*.html'):
    page = BeautifulSoup(file.read_text(), 'html.parser')
    assert len(page.select('main, [role=main]')) == 1, file.name
    assert len(page.select('h1')) == 1, file.name
    for node in page.select('[href],[src]'):
        url = node.get('href', node.get('src', ''))
        if url.startswith(('https:', 'http:', 'mailto:', 'data:', '#')):
            continue
        target = url.split('#')[0].split('?')[0]
        assert (ROOT / target).exists(), f'Missing local target: {file.name}: {url}'
assert len(list(ROOT.glob('*.html'))) == len(posts) + 2
print(f'PASS: all {len(posts)} posts preserve original text; all 123 pages and local links verified.')
