import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.lineart import openai_lineart as chatgpt


class GenerationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.original = Path(folder.name) / 'photo.jpg'
        self.original.write_bytes(b'input')
        self.output = Path(folder.name) / 'linearts' / 'v001.png'

    def test_generates_png_and_owns_client(self):
        png = b'\x89PNG\r\n\x1a\nimage'
        client = MagicMock()
        client.images.edit.return_value = SimpleNamespace(data=[
            SimpleNamespace(b64_json=base64.b64encode(png).decode())])
        with patch.object(chatgpt, 'load_api_key', return_value='test-key'), \
                patch('openai.OpenAI') as factory:
            factory.return_value.__enter__.return_value = client
            chatgpt.generate(self.original, self.output, model='chosen-model')
        factory.assert_called_once_with(api_key='test-key', timeout=600, max_retries=0)
        self.assertEqual(client.images.edit.call_args.kwargs['model'], 'chosen-model')
        self.assertEqual(self.output.read_bytes(), png)
        self.assertFalse(self.output.with_suffix('.png.part').exists())

    def test_redacts_api_errors(self):
        with patch.object(chatgpt, 'load_api_key', return_value='test-key'), \
                patch('openai.OpenAI', side_effect=RuntimeError('bad test-key')):
            with self.assertRaisesRegex(RuntimeError, r'bad \[REDACTED\]') as error:
                chatgpt.generate(self.original, self.output)
        self.assertNotIn('test-key', str(error.exception))
        self.assertFalse(self.output.exists())

    def test_missing_key_fails_before_client_creation(self):
        with patch.object(chatgpt, 'load_api_key', return_value=None), \
                patch('openai.OpenAI') as factory:
            with self.assertRaisesRegex(ValueError, 'Missing OPENAI_API_KEY'):
                chatgpt.generate(self.original, self.output)
            factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
