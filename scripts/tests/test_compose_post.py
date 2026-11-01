import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from instagrapi.image_util import prepare_image

from scripts.publish.compose_post import compose, compose_generation, backfill
from scripts.publish.instagram_client import prepare_images


class CompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.look = self.root / 'look-001'
        self.lineart = self.look / 'linearts/test/v001.png'
        self.lineart.parent.mkdir(parents=True)
        Image.new('RGB', (180, 320), 'red').save(self.look / 'original.jpg')
        drawing = Image.new('RGB', (200, 400), 'white')
        ImageDraw.Draw(drawing).rectangle((50, 20, 150, 380), outline='black', width=4)
        drawing.save(self.lineart)
        self.generation = dict(status='completed', model='test',
                               output_path='look-001/linearts/test/v001.png')
        self.job = dict(brand='chanel', season='cruise-2026-27', look=1,
                        image_path='look-001/original.jpg', published_at=None,
                        generations=[self.generation])
        self.queue = self.root / 'queue.json'

    def write(self):
        self.queue.write_text(json.dumps({'queue': [self.job]}), encoding='utf-8')

    def test_portrait_layout_and_upload_preserves_card(self):
        original = self.lineart.read_bytes()
        result = compose(self.job, self.generation, self.root)
        with Image.open(result) as image:
            self.assertEqual(image.size, (1080, 1440))
            # Thumbnail occupies its reserved column; left edge remains white.
            self.assertGreater(image.getpixel((918, 1100))[0], 200)
            self.assertLess(image.getpixel((918, 1100))[1], 40)
            self.assertGreater(min(image.getpixel((0, 0))), 245)
            self.assertLess(max(image.getpixel((788, 1280))), 60)
        upload = self.root / 'upload'
        upload.mkdir()
        prepared = prepare_images([result], upload)
        with Image.open(prepared[0]) as image:
            self.assertEqual(image.size, (1080, 1350))
        _, encoded_size = prepare_image(str(prepared[0]), max_side=1080)
        self.assertEqual(tuple(encoded_size), (1080, 1350))
        self.assertEqual(self.lineart.read_bytes(), original)

    def test_long_season_and_landscape_original(self):
        self.job['season'] = 'spring-summer-2026-ready-to-wear'
        Image.new('RGB', (900, 200), 'blue').save(self.look / 'original.jpg')
        self.assertTrue(compose_generation(self.job, self.generation, self.root))
        self.assertEqual(self.generation['post_status'], 'completed')

    def test_bad_source_and_retry_leave_generation_completed(self):
        source = self.look / 'source.json'
        source.write_text('invalid')
        self.assertFalse(compose_generation(self.job, self.generation, self.root))
        self.assertEqual(self.generation['status'], 'completed')
        self.assertEqual(self.generation['post_status'], 'failed')
        source.write_text('{}')
        self.assertTrue(compose_generation(self.job, self.generation, self.root))
        self.assertNotIn('post_error', self.generation)

    def test_missing_original_blocks_composition(self):
        self.job['image_path'] = 'missing.jpg'
        self.assertFalse(compose_generation(self.job, self.generation, self.root))
        self.assertEqual(self.generation['status'], 'completed')

    def test_backfill_idempotent_and_does_not_change_publish_state(self):
        self.write()
        self.assertEqual(backfill(self.queue, self.root), 0)
        before = self.queue.read_bytes()
        self.assertEqual(backfill(self.queue, self.root), 0)
        self.assertEqual(self.queue.read_bytes(), before)
        job = json.loads(before)['queue'][0]
        self.assertIsNone(job['published_at'])
        self.assertNotIn('publish_status', job)

    def test_backfill_skips_published_or_uncertain_posts(self):
        for status in ('publishing', 'needs_review', 'published'):
            self.job['publish_status'] = status
            self.job['published_at'] = 'previous' if status == 'published' else None
            self.write()
            before = self.queue.read_bytes()
            backfill(self.queue, self.root)
            self.assertEqual(self.queue.read_bytes(), before)

    def test_external_path_rejected(self):
        self.generation['output_path'] = '../outside.png'
        with self.assertRaises(ValueError):
            compose(self.job, self.generation, self.root)


if __name__ == '__main__':
    unittest.main()
