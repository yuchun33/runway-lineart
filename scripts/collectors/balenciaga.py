"""Collect numbered runway looks from Balenciaga collection pages."""

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_URL = 'https://www.balenciaga.com/en-us/55th-collection'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
# Underscores are word characters: \b misses filenames such as COUTURE-55_LOOK04.
LOOK_NUMBER = re.compile(r'(?<![a-z0-9])look[\s_./-]*0*(\d{1,3})(?!\d)', re.I)


class LookParser(HTMLParser):
    """Use explicit Look numbers, never number unrelated editorial pictures."""

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.stack = []
        self.looks = {}

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        context = ' '.join(str(attrs.get(key, '')) for key in
                           ('alt', 'title', 'id', 'class', 'data-look', 'data-cid', 'aria-label'))
        if attrs.get('data-look', '').isdigit():
            context += ' Look ' + attrs['data-look']
        parent = self.stack[-1][1] if self.stack else ''
        label = context if LOOK_NUMBER.search(context) else parent
        if tag not in {'img', 'source', 'br', 'hr', 'meta', 'link', 'input', 'area', 'wbr'}:
            self.stack.append((tag, label))
        if tag not in {'img', 'source', 'a'}:
            return
        candidates = []
        for key in ('data-srcset', 'srcset'):
            for entry in attrs.get(key, '').split(','):
                parts = entry.split()
                if parts:
                    size = float(parts[1][:-1]) if len(parts) > 1 and re.fullmatch(r'[\d.]+[wx]', parts[1]) else 0
                    candidates.append((size, parts[0]))
        for key in ('data-src', 'src', 'href'):
            if attrs.get(key):
                candidates.append((0, attrs[key]))
        for size, source in candidates:
            url = urljoin(self.base_url, source)
            if urlsplit(url).scheme not in {'https', 'http'}:
                continue
            if not re.search(r'\.(?:jpe?g|png|webp|avif)(?:[?#]|$)', url, re.I):
                continue
            match = LOOK_NUMBER.search(context) or LOOK_NUMBER.search(url) or LOOK_NUMBER.search(label)
            if not match:
                continue
            number = int(match[1])
            if number < 1:
                continue
            previous = self.looks.get(number)
            if previous is None or size > previous[0]:
                self.looks[number] = (size, url)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def extract_looks(html, url):
    parser = LookParser(url)
    parser.feed(html)
    return {number: value[1] for number, value in sorted(parser.looks.items())}


def request(url, referer):
    return urlopen(Request(url, headers={**HEADERS, 'Referer': referer}), timeout=60)


def browser_html(url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Browser mode needs playwright: pip install playwright; '
                           'then python -m playwright install chromium') from exc
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            page = browser.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            input('In the browser, finish loading the collection and click View more '
                  'until all Looks appear; then press Enter here: ')
            return page.content()
        finally:
            browser.close()


def image_extension(data):
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    if data[4:8] == b'ftyp' and b'avif' in data[8:32]:
        return '.avif'
    raise ValueError('Response is not a supported image (possibly a blocked request)')


def main(argv=None, *, brand='balenciaga', default_url=DEFAULT_URL, extractor=extract_looks):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--url', default=default_url, help='Official collection URL')
    cli.add_argument('--season', required=True, help='Folder name, e.g. couture-55 or 2026-fw')
    cli.add_argument('--output', type=Path, default=ROOT / 'output' / 'image')
    source = cli.add_mutually_exclusive_group()
    source.add_argument('--html', type=Path, help='Use locally saved collection HTML')
    source.add_argument('--browser', action='store_true', help='Load via an interactive Chromium browser')
    cli.add_argument('--dry-run', action='store_true', help='List Look URLs without downloading')
    cli.add_argument('--limit', type=int, help='Download only the first N Looks')
    args = cli.parse_args(argv)
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', args.season):
        cli.error('--season must contain letters, numbers, hyphens or underscores')
    if args.limit is not None and args.limit < 1:
        cli.error('--limit must be positive')
    if urlsplit(args.url).hostname not in {f'www.{brand}.com', f'{brand}.com'}:
        cli.error(f'--url must be an official {brand} page')
    try:
        if args.html:
            html = args.html.read_text(encoding='utf-8-sig')
        elif args.browser:
            html = browser_html(args.url)
        else:
            with request(args.url, args.url) as response:
                html = response.read().decode('utf-8')
        looks = extractor(html, args.url)
        if not looks:
            raise ValueError('No explicitly numbered Look images found. Use --browser or '
                             '--html with the fully loaded gallery; editorial images are not collected.')
        entries = list(looks.items())[:args.limit]
        print(f'Found {len(looks)} Looks; processing {len(entries)}.')
        failures = 0
        for number, url in entries:
            directory = args.output.resolve() / brand / args.season / f'look-{number:03d}'
            if args.dry_run:
                print(f'{directory}/original.* <- {url}')
                continue
            if any(directory.glob('original.*')):
                print(f'Skip existing: {directory.name}')
                continue
            try:
                with request(url, args.url) as response:
                    data = response.read()
                extension = image_extension(data)
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory / ('original' + extension)
                temporary = directory / ('original' + extension + '.part')
                temporary.write_bytes(data)
                temporary.replace(destination)
                (directory / 'source.json').write_text(json.dumps({
                    'collection_url': args.url, 'image_url': url, 'look': number,
                    'season': args.season,
                }, indent=2) + '\n', encoding='utf-8')
                print(f'Saved: {destination}')
            except (OSError, ValueError) as exc:
                failures += 1
                print(f'Look {number} failed: {exc}', file=sys.stderr)
            time.sleep(0.5)
        return 1 if failures else 0
    except HTTPError as exc:
        print(f'HTTP {exc.code}: {exc.url}. If the collection page is blocked, '
              'retry with --browser or --html.', file=sys.stderr)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Collection failed: {exc}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
