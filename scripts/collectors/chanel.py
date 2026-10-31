"""Download Chanel collection Looks using their explicit localized image labels."""

import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .balenciaga import main as collect_main

DEFAULT_URL = 'https://www.chanel.com/tw/fashion/cruise-2026-27/l/FshCollection27C/the-looks/'
LABEL = re.compile(r'^\s*(?:造型|款式造型|Look)\s*0*(\d{1,3})\b', re.I)
FILENAME = re.compile(r'/FSH-\d+-(\d{3})\.(?:jpg|jpeg|png|webp)(?:[?#]|$)', re.I)
EDITORIAL_FILENAME = re.compile(r'/FSH-\d+-mobile-(\d{3})\.jpg(?:[?#]|$)', re.I)
# CDN transformation URLs contain commas; splitting srcset on every comma corrupts them.
SRCSET = re.compile(r'(\S+)\s+(\d+(?:\.\d+)?)[wx](?:\s*,|\s*$)')


class ChanelParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.looks = {}

    def handle_starttag(self, tag, attributes):
        if tag != 'img':
            return
        attrs = dict(attributes)
        match = LABEL.search(attrs.get('alt', ''))
        if (not match and not attrs.get('alt')
                and re.search(r'/fashion/collection/metiers-art-[^/]+-looks/', urlsplit(self.base_url).path)
                and 'fs-image__img' in attrs.get('class', '').split()):
            match = EDITORIAL_FILENAME.search(attrs.get('data-src') or attrs.get('src', ''))
        if not match:
            return
        number = int(match[1])
        if number < 1:
            return
        candidates = []
        for key in ('data-srcset', 'srcset'):
            candidates.extend((float(width), url) for url, width in SRCSET.findall(attrs.get(key, '')))
        for key in ('data-src', 'src'):
            if attrs.get(key):
                candidates.append((0, attrs[key]))
        for width, source in candidates:
            url = urljoin(self.base_url, source)
            host = urlsplit(url).hostname or ''
            if urlsplit(url).scheme not in {'http', 'https'} or not (host == 'chanel.com' or host.endswith('.chanel.com')):
                continue
            filename = FILENAME.search(url) or EDITORIAL_FILENAME.search(url)
            if filename and int(filename[1]) != number:
                continue
            previous = self.looks.get(number)
            if previous is None or width > previous[0]:
                self.looks[number] = (width, url)

    handle_startendtag = handle_starttag


def extract_looks(html, url):
    parser = ChanelParser(url)
    parser.feed(html)
    return {number: value[1] for number, value in sorted(parser.looks.items())}


def main(argv=None):
    return collect_main(argv, brand='chanel', default_url=DEFAULT_URL, extractor=extract_looks)


if __name__ == '__main__':
    sys.exit(main())
