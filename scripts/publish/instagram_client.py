"""Publish local images to Instagram using instagrapi."""

import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from instagrapi import Client
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]


def prepare_images(paths, destination):
    """Convert PNG/JPEG images to JPEG without modifying the originals."""
    prepared = []
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            if source.format not in {'JPEG', 'PNG'}:
                raise ValueError(f'Only PNG and JPEG images are supported: {path}')
            image = ImageOps.exif_transpose(source).convert('RGBA')
            background = Image.new('RGBA', image.size, 'white')
            background.alpha_composite(image)
            image = background.convert('RGB')
            # instagrapi's feed encoder crops ratios below 4:5. Fit the whole
            # 3:4 card into that canvas so the encoder never crops its content.
            image = ImageOps.contain(image, (1080, 1350), Image.Resampling.LANCZOS)
            canvas = Image.new('RGB', (1080, 1350), 'white')
            canvas.paste(image, ((1080 - image.width) // 2, (1350 - image.height) // 2))
            target = destination / f'{index:02d}.jpg'
            canvas.save(target, quality=95)
            prepared.append(target)
    return prepared


def publish(paths, caption='', session_file=None, dry_run=False):
    paths = [Path(path).resolve() for path in paths]
    if not 1 <= len(paths) <= 10:
        raise ValueError('Provide between 1 and 10 images.')
    for path in paths:
        if not path.is_file():
            raise ValueError(f'Image does not exist: {path}')
    if len(caption) > 2200:
        raise ValueError('Caption must be at most 2200 characters.')
    session_file = Path(session_file) if session_file else ROOT / 'local/session.json'
    with TemporaryDirectory(prefix='runway-instagram-') as temporary:
        images = prepare_images(paths, Path(temporary))
        if dry_run:
            print(f'Dry run: {len(images)} image(s), 1080x1350 JPEG, caption: {caption!r}')
            return None
        load_dotenv(ROOT / '.env')
        username = os.getenv('INSTAGRAM_USERNAME')
        password = os.getenv('INSTAGRAM_PASSWORD')
        client = Client()
        if session_file.is_file():
            client.load_settings(session_file)
            # Use the account authorized by this session, regardless of .env.
            client.account_info()
        else:
            if not username or not password:
                raise ValueError('Provide local/session.json or set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env.')
            client.login(username, password, verification_code=os.getenv('INSTAGRAM_VERIFICATION_CODE', ''))
        session_file.parent.mkdir(parents=True, exist_ok=True)
        client.dump_settings(session_file)
        # Do not retry uploads automatically: an uncertain response may already
        # represent a published post.
        if len(images) == 1:
            media = client.photo_upload(images[0], caption=caption)
        else:
            media = client.album_upload(images, caption=caption)
        client.dump_settings(session_file)
        print(f'Published: https://www.instagram.com/p/{media.code}/')
        return media


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', nargs='+', type=Path, help='PNG/JPEG images in slide order')
    captions = parser.add_mutually_exclusive_group()
    captions.add_argument('--caption', default='', help='Post caption')
    captions.add_argument('--caption-file', type=Path, help='UTF-8 text file containing the caption')
    parser.add_argument('--session-file', type=Path, help='Saved login settings (default: local/session.json)')
    parser.add_argument('--dry-run', action='store_true', help='Validate and convert images without logging in or posting')
    args = parser.parse_args()
    try:
        caption = args.caption_file.read_text(encoding='utf-8-sig') if args.caption_file else args.caption
        publish(args.images, caption, args.session_file, args.dry_run)
    except Exception as exc:
        # Avoid printing API responses, which may contain account/session data.
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(f'Error: {exc}', file=sys.stderr)
        else:
            print(f'Publishing failed ({type(exc).__name__}). Check Instagram before retrying.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
