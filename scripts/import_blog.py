#!/usr/bin/env python3
"""Recreate the Scroll archive from saved Posthaven archive pages.

Requires beautifulsoup4. Run from the repository root. Downloads are optional;
the checked-in originals make conversion repeatable without network access.
"""
import argparse
import hashlib
import html
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://blog.samaltman.com/'
assets = {}
failure_file = ROOT / 'originals/media-failures.json'
unavailable = {item['url'] for item in json.loads(failure_file.read_text())} if failure_file.exists() else set()

def clean(text):
    return re.sub(r'\s+', ' ', text).strip()

def esc(text):
    return html.escape(str(text), quote=True)

def indent(source, depth=1):
    return '\n'.join(' ' * depth + line for line in source.splitlines())

def element(cue='', text='', attrs=None, children=()):
    line = (cue + ' ' if cue and text else cue) + html.escape(str(text), quote=False)
    result = [line]
    for key, value in (attrs or {}).items():
        result.append(' ' + key + (' ' + esc(value) if str(value) else ''))
    result.extend(indent(child) for child in children)
    return '\n'.join(result)

def prose(text, *directives, **attrs):
    return element('', text, attrs, directives)

def link(text, url, **attrs):
    # A bare linked paragraph; use tag a + href only for cards containing children.
    cue = url if url.startswith(('http://', 'https://')) or url.endswith('.html') else 'link ' + url
    return prose(text, cue, **attrs)

def local_link(url):
    absolute = urljoin(BASE, url)
    parsed = urlparse(absolute)
    slug = parsed.path.strip('/')
    if parsed.hostname == 'blog.samaltman.com' and slug in slugs:
        return slug + '.html' + ('#' + parsed.fragment if parsed.fragment else '')
    return absolute

def inline(node, directives):
    if isinstance(node, NavigableString):
        return html.escape(str(node), quote=False)
    if node.name in ('script', 'style'):
        return ''
    content = ''.join(inline(child, directives) for child in node.children)
    label = clean(content)
    if node.name == 'a':
        if node.get('href') and label:
            url = local_link(node['href'])
            cue = url if url.startswith(('http://', 'https://')) or re.search(r'\.html(?:#.*)?$', url) else 'link ' + url
            directives.append((cue, label))
        if node.get('id') or node.get('name'):
            directives.append(('id', node.get('id', node.get('name'))))
    cue = {'b': 'bold', 'strong': 'bold', 'i': 'italics', 'em': 'italics', 'u': 'underline', 'sup': 'superscript', 'sub': 'subscript', 'code': 'code'}.get(node.name)
    if cue and label:
        directives.append((cue, label))
    return content

BLOCKS = {'p', 'div', 'ol', 'ul', 'li', 'blockquote', 'img', 'iframe', 'hr', 'h1', 'h2', 'h3', 'h4'}

def body_scroll(body, slug):
    lines = []
    def emit(nodes, prefix='', depth=0):
        directives = []
        text = clean(''.join(inline(node, directives) for node in nodes)).strip()
        if not text:
            return
        if not prefix and (re.match(r'^(?:[0-9]+[.)]|[-*])\s', text) or text.startswith(('http://', 'https://'))):
            prefix = 'h2' if ('bold', text) in directives else 'p'  # Escape command-like prose; promote whole bold numbered headings.
            if prefix == 'h2':
                directives.remove(('bold', text))
        # Bare prose uses Scroll's catchall; explicit cues are for structural elements.
        if re.fullmatch(r'h[1-4]', prefix):
            prefix = '#' * int(prefix[1])
        lines.append(' ' * depth + (prefix + ' ' if prefix else '') + text)
        if any(cue.startswith(('http', 'link ')) or '.html' in cue for cue, _ in directives) or re.search(r'https?://|www\.|@', text):
            lines.append(' ' * (depth + 1) + 'linkify false')
        for cue, label in dict.fromkeys(directives):
            selector = '' if label == text and cue != 'id' else ' ' + label
            lines.append(' ' * (depth + 1) + cue + selector)
        lines.append('')

    def walk(parent, depth=0, prefix=''):
        pending = []
        def flush():
            emit(pending, prefix, depth)
            pending.clear()
        for node in parent.children:
            if not isinstance(node, NavigableString) and node.name in ('script', 'style'):
                continue
            if not isinstance(node, NavigableString) and node.name == 'br':
                flush()
                continue
            if isinstance(node, NavigableString) or node.name not in BLOCKS:
                pending.append(node)
                continue
            flush()
            if node.name == 'img':
                url = node.get('data-large-src') or node.get('src')
                if not url:
                    continue
                ext = Path(urlparse(url).path).suffix.lower()
                if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'):
                    ext = '.jpg'
                filename = 'assets/' + hashlib.sha256(url.encode()).hexdigest()[:16] + ext
                assets[url] = filename
                if url in unavailable:
                    lines.extend(indent(element('', 'An image in the original post is no longer available. Original image link ↗', attrs={'addClass': 'unavailable-image'}, children=[url + ' Original image link ↗']), depth).splitlines())
                    continue
                lines.extend([' ' * depth + filename, ' ' * (depth + 1) + 'alt ' + (node.get('alt') or 'Image from ' + title_by_slug[slug]), ''])
            elif node.name == 'iframe':
                url = node.get('src', '').replace('http://', 'https://')
                lines.extend([' ' * depth + 'Read the embedded document.', ' ' * (depth + 1) + url, ''])
            elif node.name == 'hr':
                lines.extend([' ' * depth + '---', ''])
            elif node.name in ('ol', 'ul'):
                for number, item in enumerate(node.find_all('li', recursive=False), 1):
                    walk(item, depth, f'{number}.' if node.name == 'ol' else '-')
            elif node.name == 'blockquote':
                walk(node, depth, '>')
            else:
                walk(node, depth, node.name if node.name in ('li', 'h1', 'h2', 'h3', 'h4') else prefix)
        flush()
    walk(body)
    # An unindented blank closes a Scroll tree: never put one between list items.
    return '\n'.join(line for i, line in enumerate(lines) if line or (i + 1 < len(lines) and lines[i + 1] and not lines[i + 1].startswith(' '))).strip()

parser = argparse.ArgumentParser()
parser.add_argument('--download', action='store_true', help='Refresh archive pages before conversion')
parser.add_argument('--media', action='store_true', help='Download missing article images')
args = parser.parse_args()
(ROOT / 'originals').mkdir(exist_ok=True)
(ROOT / 'assets').mkdir(exist_ok=True)
if args.download:
    page = 1
    while True:
        output = ROOT / f'originals/page-{page}.html'
        subprocess.run(['curl', '-fLsS', '--retry', '3', BASE + '?page=' + str(page), '-o', str(output)], check=True)
        soup = BeautifulSoup(output.read_text(), 'html.parser')
        if not soup.select_one('.pagination .next a'):
            break
        page += 1
    for stale in (ROOT / 'originals').glob('page-*.html'):
        if int(stale.stem.split('-')[1]) > page:
            stale.unlink()

posts = []
for file in sorted((ROOT / 'originals').glob('page-*.html'), key=lambda f: int(f.stem.split('-')[1])):
    soup = BeautifulSoup(file.read_text(), 'html.parser')
    for article in soup.select('article.post'):
        anchor = article.select_one('.post-title a')
        url = anchor['href']
        slug = urlparse(url).path.strip('/')
        timestamp = int(article.select_one('[data-unix-time]')['data-unix-time'])
        date = datetime.fromtimestamp(timestamp, timezone.utc)
        body = article.select_one('.posthaven-post-body')
        plain = clean(body.get_text(' ', strip=True))
        posts.append(dict(title=anchor.get_text(strip=True), slug=slug, url=url, date=date.strftime('%Y-%m-%d'), year=date.year, displayDate=date.strftime('%B %-d, %Y'), minutes=max(1, math.ceil(len(plain.split()) / 230)), text=plain, body=body, original=file.name))
assert len({p['slug'] for p in posts}) == len(posts), 'Duplicate permalinks'
slugs = {p['slug'] for p in posts}
title_by_slug = {p['slug']: p['title'] for p in posts}

def footer():
    return 'footer.scroll\n'

for i, post in enumerate(posts):
    slug = post['slug']
    post['scrollFile'] = slug + '.scroll'
    source = f"title {esc(post['title'])}\ndescription {esc(post['text'][:160])}\ndate {post['date']}\ncanonicalUrl {post['url']}\n\npost-header.scroll\n\n{body_scroll(post['body'], slug)}\n\n{footer()}"
    (ROOT / post['scrollFile']).write_text(source)

controls = element('div', attrs={'addClass': 'archive-controls'}, children=[
    element('label', attrs={'addClass': 'search'}, children=[
        element('span', '⌕', {'aria-hidden': 'true'}),
        element('input', attrs={'id': 'search', 'type': 'search', 'aria-label': 'Filter titles', 'placeholder': 'Filter titles…', 'autocomplete': 'off'}),
        element('kbd', '/')])])
groups = []
for year in sorted({p['year'] for p in posts}, reverse=True):
    rows = [element('a', attrs={'addClass': 'post-row', 'href': post['slug'] + '.html', 'data-slug': post['slug']}, children=[
        element('time', datetime.strptime(post['date'], '%Y-%m-%d').strftime('%b %d'), {'datetime': post['date']}),
        element('span', post['title'], {'addClass': 'post-title'}),
        element('span', f"{post['minutes']} min", {'addClass': 'read-time'}),
        element('span', '↗', {'addClass': 'row-arrow', 'aria-hidden': 'true'})]) for post in posts if post['year'] == year]
    groups.append(element('section', attrs={'addClass': 'year-group', 'data-year': year, 'aria-label': f'Writing from {year}'}, children=[element('h3', str(year)), element('div', attrs={'addClass': 'year-posts'}, children=rows)]))
archive = element('section', attrs={'id': 'archive', 'addClass': 'archive', 'aria-labelledby': 'archive-heading'}, children=[
    element('div', attrs={'addClass': 'archive-intro'}, children=[element('span', 'THE PERSONAL BLOG OF SAM ALTMAN'), element('span', f"2013 — {posts[0]['year']}")]),
    element('div', attrs={'addClass': 'archive-heading'}, children=[
        element('div', children=[element('span', 'THE ARCHIVE', {'addClass': 'eyebrow'}), element('h1', 'All writing', {'id': 'archive-heading'}, [element('span', str(len(posts)), {'addClass': 'count'})])]), controls]),
    element('div', attrs={'id': 'search-status', 'addClass': 'search-status', 'aria-live': 'polite'}),
    *groups, element('div', attrs={'id': 'empty', 'aria-live': 'polite'})])
home = 'title buSamAltman — Archive\ndescription A 3rd backup of Sam Altman’s blog for personal training.\npermalink index.html\ncanonicalUrl https://blog.samaltman.com/\nbuildHtml\nhead.scroll\n\n'
home += element('main', attrs={'id': 'main'}, children=[archive])
home += '\n\nhomeFooter.scroll\n\nsite.js\n'
(ROOT / 'readme.scroll').write_text(home)
(ROOT / 'archive.json').write_text(json.dumps([{k: v for k, v in p.items() if k != 'body'} for p in posts], ensure_ascii=False, indent=2) + '\n')
(ROOT / 'originals/media.json').write_text(json.dumps(assets, indent=2) + '\n')
if args.media:
    from concurrent.futures import ThreadPoolExecutor
    def download(item):
        url, filename = item
        dest = ROOT / filename
        if dest.exists() and dest.stat().st_size:
            return None
        result = subprocess.run(['curl', '-fLsS', '--retry', '2', '--max-time', '60', url, '-o', str(dest)], capture_output=True)
        return {'url': url, 'file': filename, 'error': result.stderr.decode()} if result.returncode else None
    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [error for error in pool.map(download, assets.items()) if error]
    (ROOT / 'originals/media-failures.json').write_text(json.dumps(failures, indent=2) + '\n')
    print('Media:', len(assets), 'images;', len(failures), 'failures')
print('Converted', len(posts), 'posts; wrote readme.scroll → index.html')
