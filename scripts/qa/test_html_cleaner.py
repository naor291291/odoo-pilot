"""Security updates must preserve Odoo's Hebrew rich text without executable HTML."""
import unittest
from importlib.metadata import version
from lxml_html_clean import clean_html, Cleaner
from odoo.tools import html_sanitize


class HtmlCleanerTests(unittest.TestCase):
    def test_reviewed_runtime_override_is_selected(self):
        self.assertEqual(version('lxml-html-clean'), '0.4.6')

    def test_base_tag_cannot_redirect_relative_links(self):
        source = '<base href="https://qa.invalid/"><a href="/my/field-work">עבודה</a>'
        for cleaner in (clean_html, html_sanitize):
            result = cleaner(source)
            self.assertNotIn('<base', result)
            self.assertIn('/my/field-work', result)

    def test_unicode_css_import_is_rejected(self):
        cleaner = Cleaner()
        for escape in (r'\69mport', r'\0069mport', r'\69 mport', r'\49mport'):
            self.assertTrue(cleaner._has_sneaky_javascript('@' + escape + ' url(https://qa.invalid/x.css);'))

    def test_native_rich_text_preserves_hebrew_and_removes_active_tags(self):
        source = '<p dir="rtl"><strong>דיווח עבודה</strong></p><svg><script>void(0)</script></svg><math><script>void(0)</script></math><noscript><script>void(0)</script></noscript>'
        result = html_sanitize(source)
        self.assertIn('דיווח עבודה', result)
        self.assertIn('<strong>', result)
        # Empty SVG/Math containers are harmless; require removal of executable content.
        self.assertNotIn('void(0)', result)
        for tag in ('<script', '<noscript'):
            self.assertNotIn(tag, result)


if __name__ == '__main__':
    unittest.main()
