import base64
from io import BytesIO

from PIL import Image
from odoo.tests import HttpCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestNativeImageRuntime(HttpCase):
    def test_native_partner_image_upload_and_http_resize(self):
        user = new_test_user(self.env, login='native_image_operator', groups='base.group_user')
        self.authenticate(user.login, user.login)
        for image_format in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(image_format=image_format):
                stream = BytesIO()
                Image.new('RGB', (320, 160), 'blue').save(stream, image_format)
                partner = self.env['res.partner'].create({
                    'name': 'Synthetic native image ' + image_format,
                    'image_1920': base64.b64encode(stream.getvalue()),
                })
                # Exercises native fields.Image and its stored resized derivatives.
                with Image.open(BytesIO(base64.b64decode(partner.image_128))) as image:
                    self.assertLessEqual(max(image.size), 128)
                response = self.url_open(f'/web/image/res.partner/{partner.id}/image_128')
                self.assertEqual(response.status_code, 200)
                with Image.open(BytesIO(response.content)) as image:
                    self.assertLessEqual(max(image.size), 128)

    def test_patched_pillow_selected_by_odoo(self):
        import PIL
        self.assertEqual(PIL.__version__, '13.0.0')
        # Full native plug-in registration must not downgrade or select the distro copy.
        Image.init()
        self.assertIn('TIFF', Image.SAVE)
        stream = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(stream, 'TIFF')
        stream.seek(0)
        with Image.open(stream) as image:
            image.load()
            self.assertEqual(image.size, (8, 8))
