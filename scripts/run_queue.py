"""Process one photo and its queued model generations per invocation."""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Support both the existing script entrypoint and python -m scripts.run_queue.
if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lineart import openai_lineart, gemini_lineart
from scripts.lineart.common import ROOT

PROVIDERS = {'openai': openai_lineart, 'gemini': gemini_lineart}
QUEUE = Path(__file__).with_name('queue.json')


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def status_of(generations):
    states = [item['status'] for item in generations]
    if all(state == 'completed' for state in states):
        return 'completed'
    if 'processing' in states:
        return 'processing'
    if 'completed' in states:
        return 'partial'
    if 'queued' in states:
        return 'queued'
    return 'failed'


def process(dry_run=False, provider=None, model=None):
    if provider is not None and provider not in PROVIDERS:
        raise ValueError(f'Unknown provider: {provider}')

    def selected(item):
        return (item.get('status') == 'queued'
                and (provider is None or item.get('provider') == provider)
                and (model is None or item.get('model') == model))

    raw = QUEUE.read_text(encoding='utf-8-sig')
    data = json.loads(raw)
    queue = data['queue']
    if any(job.get('status') == 'processing' or any(
            item.get('status') == 'processing' for item in job.get('generations', [])) for job in queue):
        raise RuntimeError('A processing job needs review before continuing (possibly interrupted).')
    job = next((job for job in queue if job.get('status') in {'queued', 'partial', 'failed'}
                and any(selected(item) for item in job.get('generations', []))), None)
    if job is None:
        logging.info('No queued generations.')
        return 0
    generations = job['generations']
    outputs = [(ROOT / item['output_path']).resolve() for item in generations]
    if len(set(outputs)) != len(outputs):
        raise ValueError('Model generations must use different output paths')

    def update():
        nonlocal raw
        if QUEUE.read_text(encoding='utf-8-sig') != raw:
            raise RuntimeError('queue.json changed during processing; refusing to overwrite it.')
        save(QUEUE, data)
        raw = QUEUE.read_text(encoding='utf-8-sig')

    failures = 0
    for item in generations:
        if not selected(item):
            continue
        if dry_run:
            logging.info('Next: %s -> %s (%s / %s)', job['image_path'],
                         item['output_path'], item['provider'], item['model'])
            continue
        item.update(status='processing', started_at=now())
        item.pop('error', None)
        item.pop('failed_at', None)
        job.update(status='processing', started_at=job.get('started_at') or now())
        job.pop('completed_at', None)
        update()
        try:
            original = (ROOT / job['image_path']).resolve()
            destination = (ROOT / item['output_path']).resolve()
            if not original.is_file():
                raise ValueError(f'Input missing: {original}')
            if original == destination or destination.suffix.lower() != '.png':
                raise ValueError('Output must be a separate PNG file')
            backend = PROVIDERS[item['provider']]
            if not destination.exists():
                backend.generate(original, destination, model=item['model'])
            if not destination.is_file() or not destination.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Output missing or not a PNG image')
            item.update(status='completed', completed_at=now())
            logging.info('Saved %s', destination)
        except Exception as exc:
            failures += 1
            item.update(status='failed', failed_at=now(), error=str(exc))
            logging.error('%s: %s', item['provider'], exc)
        job['status'] = status_of(generations)
        if job['status'] == 'completed':
            job['completed_at'] = now()
        update()
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--provider', choices=PROVIDERS, help='Only process queued tasks for this provider')
    parser.add_argument('--model', help='Only process this exact model ID from queue.json')
    args = parser.parse_args()
    log_dir = ROOT / 'output' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / 'queue.log', encoding='utf-8')])
    try:
        return process(args.dry_run, provider=args.provider, model=args.model)
    except Exception as exc:
        logging.error('%s', exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
