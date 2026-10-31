import json
import tempfile
import unittest
from pathlib import Path

from scripts.update_web_data import build_data


class WebDataTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.look = self.root / 'output/image/chanel/ss27/look-001'
        self.look.mkdir(parents=True)
        (self.look / 'original.jpg').write_bytes(b'original')
        (self.root / 'web').mkdir()

    def test_multiple_models_and_versions(self):
        for model, version in [('openai', 'v001'), ('openai', 'v002'), ('gemini', 'v001')]:
            file = self.look / 'linearts' / model / (version + '.png')
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'image')
        look = build_data(self.root)['brands'][0]['looks'][0]
        self.assertEqual(len(look['linearts']), 3)
        self.assertEqual(look['original']['src'], '../output/image/chanel/ss27/look-001/original.jpg')
        self.assertEqual({item['model'] for item in look['linearts']}, {'openai', 'gemini'})

    def test_preserves_display_names_and_removes_missing_placeholder(self):
        old = {'brands': [{'id': 'chanel', 'name': 'Custom brand', 'looks': [{
            'id': 'ss27-look-001', 'name': 'Custom Look',
            'original': {'alt': 'Custom alt'}, 'linearts': [{'src': '../missing.png'}]}]}]}
        (self.root / 'web/data.json').write_text(json.dumps(old))
        brand = build_data(self.root)['brands'][0]
        self.assertEqual(brand['name'], 'Custom brand')
        self.assertEqual(brand['looks'][0]['name'], 'Custom Look')
        self.assertEqual(brand['looks'][0]['original']['alt'], 'Custom alt')
        self.assertEqual(brand['looks'][0]['linearts'], [])

    def test_rejects_ambiguous_original(self):
        (self.look / 'original.png').write_bytes(b'duplicate')
        with self.assertRaisesRegex(ValueError, 'Expected one original'):
            build_data(self.root)


if __name__ == '__main__':
    unittest.main()
