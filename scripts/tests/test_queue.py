import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_queue as worker


class QueueTests(unittest.TestCase):
    def setUp(self):
        composer = patch.object(worker, 'compose_generation', return_value=True)
        composer.start()
        self.addCleanup(composer.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.queue = self.root / 'queue.json'
        (self.root / 'photo.jpg').write_bytes(b'input')
        self.jobs = [{'image_path': 'photo.jpg', 'status': 'queued', 'generations': [
            {'provider': provider, 'model': 'test-model', 'output_path': f'{number}-{provider}.png', 'status': 'queued'}
            for provider in ('openai', 'gemini')]} for number in (1, 2)]
        worker.save(self.queue, {'queue': self.jobs})
        for name, value in [('ROOT', self.root), ('QUEUE', self.queue)]:
            mock = patch.object(worker, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def read(self):
        return json.loads(self.queue.read_text())['queue']

    def generate(self, original, destination, model):
        destination.write_bytes(b'\x89PNG\r\n\x1a\nimage')

    def test_one_photo_two_providers(self):
        with patch.object(worker.openai_lineart, 'generate', side_effect=self.generate) as first, \
                patch.object(worker.gemini_lineart, 'generate', side_effect=self.generate) as second:
            self.assertEqual(worker.process(), 0)
        first.assert_called_once()
        second.assert_called_once()
        self.assertEqual([job['status'] for job in self.read()], ['completed', 'queued'])

    def test_provider_filter_preserves_other_task(self):
        with patch.object(worker.openai_lineart, 'generate') as first, \
                patch.object(worker.gemini_lineart, 'generate', side_effect=self.generate) as second:
            self.assertEqual(worker.process(provider='gemini'), 0)
        first.assert_not_called()
        second.assert_called_once()
        job = self.read()[0]
        self.assertEqual(job['status'], 'partial')
        self.assertEqual([g['status'] for g in job['generations']], ['queued', 'completed'])

    def test_model_filter_selects_first_matching_photo(self):
        self.jobs[1]['generations'][0]['model'] = 'chosen-model'
        worker.save(self.queue, {'queue': self.jobs})
        with patch.object(worker.openai_lineart, 'generate', side_effect=self.generate) as first, \
                patch.object(worker.gemini_lineart, 'generate') as second:
            self.assertEqual(worker.process(model='chosen-model'), 0)
        first.assert_called_once()
        second.assert_not_called()
        self.assertEqual(first.call_args.kwargs['model'], 'chosen-model')
        self.assertEqual([job['status'] for job in self.read()], ['queued', 'partial'])

    def test_no_matching_model_does_not_change_queue(self):
        before = self.queue.read_bytes()
        self.assertEqual(worker.process(model='not-in-queue'), 0)
        self.assertEqual(self.queue.read_bytes(), before)

    def test_partial_failure_and_explicit_retry(self):
        with patch.object(worker.openai_lineart, 'generate', side_effect=RuntimeError('failed')), \
                patch.object(worker.gemini_lineart, 'generate', side_effect=self.generate) as second:
            self.assertEqual(worker.process(), 1)
        second.assert_called_once()
        jobs = self.read()
        self.assertEqual(jobs[0]['status'], 'partial')
        self.assertEqual([g['status'] for g in jobs[0]['generations']], ['failed', 'completed'])
        jobs[0]['generations'][0]['status'] = 'queued'
        worker.save(self.queue, {'queue': jobs})
        with patch.object(worker.openai_lineart, 'generate', side_effect=self.generate) as first, \
                patch.object(worker.gemini_lineart, 'generate') as second:
            self.assertEqual(worker.process(), 0)
        first.assert_called_once()
        second.assert_not_called()
        self.assertEqual(self.read()[0]['status'], 'completed')

    def test_existing_outputs_and_completed_children_skipped(self):
        for generation in self.jobs[0]['generations']:
            (self.root / generation['output_path']).write_bytes(b'\x89PNG\r\n\x1a\nimage')
        with patch.object(worker.openai_lineart, 'generate') as first, \
                patch.object(worker.gemini_lineart, 'generate') as second:
            self.assertEqual(worker.process(), 0)
        first.assert_not_called()
        second.assert_not_called()
        self.assertEqual(self.read()[0]['status'], 'completed')

    def test_dry_run_and_processing_guard(self):
        before = self.queue.read_bytes()
        self.assertEqual(worker.process(dry_run=True), 0)
        self.assertEqual(self.queue.read_bytes(), before)
        self.jobs[0]['generations'][0]['status'] = 'processing'
        worker.save(self.queue, {'queue': self.jobs})
        with self.assertRaisesRegex(RuntimeError, 'needs review'):
            worker.process()


if __name__ == '__main__':
    unittest.main()
