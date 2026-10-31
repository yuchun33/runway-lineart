import unittest

from scripts.collectors.chanel import DEFAULT_URL, extract_looks


class ChanelTests(unittest.TestCase):
    def test_metiers_art_empty_alt_numbered_images(self):
        url = 'https://www.chanel.com/tw/fashion/collection/metiers-art-2026-looks/'
        base = 'https://www.chanel.com/images/q_auto:good,f_auto,fl_lossy,dpr_1.1'
        html = f'''<img class="fs-image__img" alt=""
          src="{base}/w_202/FSH-1778676938794-mobile-001.jpg"
          srcset="{base}/w_202/FSH-1778676938794-mobile-001.jpg 202w,
                  {base}/w_904/FSH-1778676938794-mobile-001.jpg 904w">
          <img class="fs-image__img" alt="" src="/images/FSH-123-mobile-oabdefault.png">'''
        self.assertEqual(extract_looks(html, url), {1: f'{base}/w_904/FSH-1778676938794-mobile-001.jpg'})
        self.assertEqual(extract_looks(html, DEFAULT_URL), {})

    def test_localized_alt_and_commas_in_srcset(self):
        base = 'https://www.chanel.com/images/q_auto:good,f_auto,fl_lossy,dpr_1.1'
        html = f'''<img alt="造型 1 – 2026/27 Cruise"
          src="{base}/w_172/FSH-1777401717929-001.jpg"
          srcset="{base}/w_172/FSH-1777401717929-001.jpg 172w,
                  {base}/w_768/FSH-1777401717929-001.jpg 768w">
          <img alt="" src="https://www.chanel.com/menu.jpg">'''
        self.assertEqual(extract_looks(html, DEFAULT_URL), {
            1: f'{base}/w_768/FSH-1777401717929-001.jpg',
        })

    def test_duplicate_and_mismatched_number(self):
        html = '''<img alt="Look 2 - Cruise" src="/images/FSH-123-002.jpg">
        <img alt="Look 2 - Cruise" src="/images/FSH-123-002.jpg">
        <img alt="Look 3 - Cruise" src="/images/FSH-123-004.jpg">'''
        self.assertEqual(extract_looks(html, DEFAULT_URL), {
            2: 'https://www.chanel.com/images/FSH-123-002.jpg',
        })


if __name__ == '__main__':
    unittest.main()
