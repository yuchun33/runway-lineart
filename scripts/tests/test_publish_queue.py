import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from scripts import publish_queue as worker


class PublishQueueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.queue = self.root / 'queue.json'
        for name in ('original.jpg', 'lineart.png'):
            Image.new('RGB', (30, 50), 'white').save(self.root / name)
        self.jobs = [dict(brand='chanel', season='test', look=i,
                          image_path='original.jpg', status='partial', published_at=None,
                          generations=[dict(status='completed', output_path='lineart.png', model='test', post_status='completed', post_path='lineart.png'),
                                       dict(status='queued', output_path='later.png', model='later')])
                     for i in (1, 2)]
        self.write()
        for name, value in [('ROOT', self.root), ('QUEUE', self.queue)]:
            patcher = patch.object(worker, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(worker, 'publish', return_value=SimpleNamespace(pk=123, code='abc'))
        self.publish = patcher.start()
        self.addCleanup(patcher.stop)

    def write(self):
        worker.save(self.queue, {'queue': self.jobs})

    def read(self):
        return json.loads(self.queue.read_text())['queue']

    def test_first_partial_job_and_slide_order(self):
        worker.process()
        first, second = self.read()
        self.assertEqual(first['publish_status'], 'published')
        self.assertIsNotNone(first['published_at'])
        self.assertEqual(first['instagram_media_id'], '123')
        self.assertIsNone(second['published_at'])
        self.assertEqual(self.publish.call_args.args[0],
                         [self.root / 'lineart.png'])

    def test_skip_published_and_not_ready(self):
        self.jobs[0]['published_at'] = 'previous'
        self.jobs[1]['generations'][0]['status'] = 'queued'
        self.write()
        worker.process()
        self.publish.assert_not_called()

    def test_missing_output_skipped(self):
        self.jobs[0]['generations'][0]['post_path'] = 'missing.png'
        self.write()
        worker.process()
        self.assertIsNone(self.read()[0]['published_at'])
        self.assertIsNotNone(self.read()[1]['published_at'])

    def test_dry_run_does_not_write_or_send(self):
        before = self.queue.read_bytes()
        worker.process(dry_run=True)
        self.assertEqual(self.queue.read_bytes(), before)
        self.publish.assert_not_called()

    def test_failure_blocks_future_attempts(self):
        self.publish.side_effect = RuntimeError('uncertain response')
        with self.assertRaises(RuntimeError):
            worker.process()
        self.assertEqual(self.read()[0]['publish_status'], 'needs_review')
        with self.assertRaises(RuntimeError):
            worker.process()
        self.assertEqual(self.publish.call_count, 1)

    def test_checkpoint_then_send_and_block_interrupted_checkpoint(self):
        worker.process(prepare=True)
        self.publish.assert_not_called()
        self.assertEqual(self.read()[0]['publish_status'], 'publishing')
        with self.assertRaises(RuntimeError):
            worker.process(prepare=True)
        worker.process(send_prepared=True)
        self.publish.assert_called_once()
        self.assertEqual(self.read()[0]['publish_status'], 'published')

    def test_corrupt_image_never_marks_or_sends(self):
        (self.root / 'lineart.png').write_bytes(b'broken')
        before = self.queue.read_bytes()
        with self.assertRaises(Exception):
            worker.process()
        self.assertEqual(self.queue.read_bytes(), before)
        self.publish.assert_not_called()

    def test_concurrent_edit_does_not_send(self):
        original = worker.content

        def edited(job):
            result = original(job)
            self.queue.write_text('{"queue": []}')
            return result

        with patch.object(worker, 'content', side_effect=edited):
            with self.assertRaises(RuntimeError):
                worker.process()
        self.publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
