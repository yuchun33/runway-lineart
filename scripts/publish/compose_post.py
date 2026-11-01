"""Compose deterministic 1080x1440 Instagram cards; no model/API calls."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lineart.common import ROOT

SIZE = (1080, 1440)


def local_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path outside project: {value}')
    return path


def rgb_image(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGBA')
        white = Image.new('RGBA', image.size, 'white')
        return Image.alpha_composite(white, image).convert('RGB')


def source_info(job, root=ROOT):
    source = local_path(root, job['image_path']).with_name('source.json')
    return json.loads(source.read_text(encoding='utf-8-sig')) if source.is_file() else {}


def compose(job, generation, root=ROOT):
    original = local_path(root, job['image_path'])
    lineart = local_path(root, generation['output_path'])
    if lineart.parent.parent.name != 'linearts':
        raise ValueError('Expected linearts/<model>/<version>.png output path')
    target = lineart.parent.parent.parent / 'posts' / lineart.parent.name / (lineart.stem + '.jpg')
    source_info(job, root)  # Validate source JSON when present; queue supplies labels.
    canvas = Image.new('RGB', SIZE, 'white')
    drawing = rgb_image(lineart)
    # Trim only near-white outside margins, preserving all ink and clothing.
    ink = ImageChops.difference(drawing, Image.new('RGB', drawing.size, 'white')).convert('L')
    bounds = ink.point(lambda pixel: 255 if pixel > 20 else 0).getbbox()
    if bounds:
        drawing = drawing.crop(bounds)
    drawing = ImageOps.contain(drawing, (740, 1376), Image.Resampling.LANCZOS)
    canvas.paste(drawing, (24 + (740 - drawing.width) // 2, (1440 - drawing.height) // 2))
    photo = ImageOps.contain(rgb_image(original), (260, 350), Image.Resampling.LANCZOS)
    canvas.paste(photo, (788 + (260 - photo.width) // 2, 1260 - photo.height))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((788, 1276, 1048, 1408), outline='black', width=2)
    lines = [job['brand'].replace('-', ' ').title(), str(job['season']), f"Look {int(job['look']):03d}"]
    for index, text in enumerate(lines):
        # Pillow's bundled scalable Aileron font is identical on Windows/Linux.
        for size in range(28, 7, -1):
            font = ImageFont.load_default(size=size)
            if draw.textlength(text, font=font) <= 236:
                break
        if draw.textlength(text, font=font) > 236:
            raise ValueError('Information text is too long for the card')
        draw.text((918, 1300 + index * 38), text, font=font, fill='black', anchor='mm')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.jpg.tmp')
    canvas.save(temporary, format='JPEG', quality=95, subsampling=0)
    temporary.replace(target)
    return target


def compose_generation(job, generation, root=ROOT):
    """Keep composition failure independent of successful lineart generation."""
    try:
        target = compose(job, generation, root)
        generation.update(post_status='completed', post_path=target.relative_to(root.resolve()).as_posix(),
                          post_completed_at=datetime.now(timezone.utc).isoformat())
        generation.pop('post_error', None)
        return True
    except Exception as exc:
        generation.update(post_status='failed', post_error=str(exc))
        logging.error('Composition failed: %s', exc)
        return False


def backfill(queue_path, root=ROOT, limit=None, force=False):
    # Lazy import avoids a cycle when run_queue invokes compose_generation.
    from scripts.run_queue import save
    raw = queue_path.read_text(encoding='utf-8-sig')
    data = json.loads(raw)
    count = failures = 0
    for job in data['queue']:
        if job.get('published_at') or job.get('publish_status') in {'publishing', 'needs_review'}:
            continue
        for generation in job.get('generations', []):
            if generation.get('status') != 'completed':
                continue
            if not force and generation.get('post_status') == 'completed' and local_path(root, generation['post_path']).is_file():
                continue
            if limit is not None and count >= limit:
                break
            failures += not compose_generation(job, generation, root)
            count += 1
            if queue_path.read_text(encoding='utf-8-sig') != raw:
                raise RuntimeError('queue.json changed during composition')
            save(queue_path, data)
            raw = queue_path.read_text(encoding='utf-8-sig')
    logging.info('Composed %s card(s), %s failed.', count, failures)
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Maximum number of cards to compose')
    parser.add_argument('--force', action='store_true', help='Rebuild existing unpublished cards')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    logging.basicConfig(level=logging.INFO)
    return backfill(ROOT / 'scripts/queue.json', limit=args.limit, force=args.force)


if __name__ == '__main__':
    raise SystemExit(main())
