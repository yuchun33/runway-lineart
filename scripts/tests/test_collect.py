import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.collectors import balenciaga as collect


class CollectTests(unittest.TestCase):
    def test_balenciaga_filename_and_lazy_srcset(self):
        base = 'https://balenciaga.dam.kering.com/asset/cb4fca80-a9b1-4cd3-85da-e7ec19483026'
        filename = 'BALENCIAGA_COUTURE-55_LOOK04_A_FRONT_0252.jpg'
        html = f'''<img class="cms-section__lookbookimg lazyloaded" alt=""
            src="{base}/Medium/{filename}"
            data-srcset="{base}/Small_thumbnail/{filename} 200w,
                         {base}/Medium/{filename} 733w,
                         {base}/Large/{filename} 1466w">
            <img src="{base}/Medium/{filename}">'''
        self.assertEqual(collect.extract_looks(html, collect.DEFAULT_URL), {
            4: f'{base}/Large/{filename}',
        })

    def test_balenciaga_parent_data_cid(self):
        html = '''<li data-cid="couture-collection-55-look1">
            <a href="/en-us/lookbook?cid=couture-collection-55-look1">
            <img alt="" data-src="/original.jpg"></a></li>
            <li><img src="/unrelated.jpg"></li>'''
        self.assertEqual(collect.extract_looks(html, collect.DEFAULT_URL), {
            1: 'https://www.balenciaga.com/original.jpg',
        })

    def test_numbered_looks_and_responsive_duplicates(self):
        html = '''<img src="/backstage.jpg">
        <div aria-label="Look 002"><picture>
        <source srcset="/small.jpg 400w, /large.jpg 2000w">
        <img src="/fallback.jpg"></picture></div>
        <img alt="Look 1" src="/one.webp"><img src="/editorial.jpg">'''
        self.assertEqual(collect.extract_looks(html, collect.DEFAULT_URL), {
            1: 'https://www.balenciaga.com/one.webp',
            2: 'https://www.balenciaga.com/large.jpg',
        })

    def test_download_layout_and_skip(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return b'\xff\xd8\xffimage'

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            html = root / 'page.html'
            html.write_text('<img alt="Look 3" src="https://example.com/3.jpg">')
            arguments = ['--season', 'couture-55', '--html', str(html), '--output', str(root)]
            with patch.object(collect, 'request', return_value=Response()) as request, patch.object(collect.time, 'sleep'):
                self.assertEqual(collect.main(arguments), 0)
                original = root / 'balenciaga/couture-55/look-003/original.jpg'
                self.assertEqual(original.read_bytes(), b'\xff\xd8\xffimage')
                self.assertEqual(collect.main(arguments), 0)
                self.assertEqual(request.call_count, 1)

    def test_reject_html_as_image(self):
        with self.assertRaises(ValueError):
            collect.image_extension(b'<html>Forbidden</html>')

    def test_reject_path_traversal(self):
        with self.assertRaises(SystemExit):
            collect.main(['--season', '../escape'])


if __name__ == '__main__':
    unittest.main()
