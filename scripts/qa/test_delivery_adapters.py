"""Exercise actual SMTP/Meta adapter serialization with all transports mocked."""
import importlib.util
import os
from pathlib import Path
import smtplib
import unittest
from unittest.mock import MagicMock, patch

SOURCE = Path(__file__).resolve().parents[2] / 'addons/field_work_photos/models/field_delivery_provider.py'
spec = importlib.util.spec_from_file_location('qa_delivery_provider', SOURCE)
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


class DeliveryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'FIELD_WORK_SMTP_HOST': 'smtp.example.invalid', 'FIELD_WORK_SMTP_FROM': 'sender@example.invalid',
            'FIELD_WORK_SMTP_USERNAME': 'sender@example.invalid', 'FIELD_WORK_SMTP_PASSWORD': 'synthetic-only',
            'FIELD_WORK_SMTP_PORT': '465', 'FIELD_WORK_SMTP_SECURITY': 'ssl',
            'FIELD_WORK_WHATSAPP_API_VERSION': 'v99.0', 'FIELD_WORK_WHATSAPP_PHONE_ID': '1234',
            'FIELD_WORK_WHATSAPP_TOKEN': 'synthetic-only', 'FIELD_WORK_WHATSAPP_QUOTE_TEMPLATE': 'qa_quote',
            'FIELD_WORK_WHATSAPP_LANGUAGE': 'he',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.pdf = b'%PDF-1.4 synthetic transport fixture'

    def send_email(self):
        return provider.send_email('recipient@example.invalid', 'הצעת מחיר', 'שלום', 'quote.pdf', self.pdf)

    def test_ssl_sends_exact_pdf_and_hebrew_body(self):
        with patch.object(provider.smtplib, 'SMTP_SSL') as smtp:
            self.send_email()
            client = smtp.return_value
            message = client.send_message.call_args.args[0]
            self.assertEqual(str(message['To']), 'recipient@example.invalid')
            self.assertEqual(str(message['Subject']), 'הצעת מחיר')
            self.assertEqual(message.get_body().get_content().strip(), 'שלום')
            attachment, = message.iter_attachments()
            self.assertEqual(attachment.get_content(), self.pdf)
            self.assertEqual(attachment.get_filename(), 'quote.pdf')
            client.close.assert_called_once()

    def test_starttls_precedes_authentication(self):
        with patch.dict(os.environ, {'FIELD_WORK_SMTP_SECURITY': 'starttls', 'FIELD_WORK_SMTP_PORT': '587'}), \
                patch.object(provider.smtplib, 'SMTP') as smtp:
            self.send_email()
            self.assertEqual([c[0] for c in smtp.return_value.method_calls],
                             ['starttls', 'login', 'send_message', 'close'])

    def test_smtp_rejection_is_redacted_and_closes_connection(self):
        with patch.object(provider.smtplib, 'SMTP_SSL') as smtp:
            smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'sensitive provider detail')
            with self.assertRaises(provider.DeliveryRejected) as error:
                self.send_email()
            self.assertNotIn('sensitive', str(error.exception))
            smtp.return_value.send_message.assert_not_called()
            smtp.return_value.close.assert_called_once()

    def test_invalid_configuration_never_opens_transport(self):
        with patch.dict(os.environ, {'FIELD_WORK_SMTP_SECURITY': 'plain'}), \
                patch.object(provider.smtplib, 'SMTP_SSL') as secure, patch.object(provider.smtplib, 'SMTP') as plain:
            with self.assertRaises(provider.DeliveryRejected):
                self.send_email()
            secure.assert_not_called()
            plain.assert_not_called()

    def test_whatsapp_uploads_private_bytes_then_uses_media_id(self):
        upload = MagicMock(status_code=200)
        upload.json.return_value = {'id': '9876'}
        sent = MagicMock(status_code=200)
        sent.json.return_value = {'messages': [{'id': 'wamid.fixture'}]}
        with patch.object(provider.requests, 'post', side_effect=[upload, sent]) as post:
            result = provider.send_whatsapp('quote', '972500000000', 'Q-1', 'quote.pdf', self.pdf)
            self.assertEqual(result, 'wamid.fixture')
            first, second = post.call_args_list
            self.assertEqual(first.kwargs['files']['file'][1], self.pdf)
            template = second.kwargs['json']['template']
            document = template['components'][0]['parameters'][0]['document']
            self.assertEqual(document, {'id': '9876', 'filename': 'quote.pdf'})
            self.assertEqual(template['components'][1]['parameters'][0]['text'], 'Q-1')
            for call in post.call_args_list:
                self.assertFalse(call.kwargs['allow_redirects'])
                self.assertIn('timeout', call.kwargs)

    def test_whatsapp_rejected_upload_never_sends_message(self):
        with patch.object(provider.requests, 'post', return_value=MagicMock(status_code=400)) as post:
            with self.assertRaises(provider.DeliveryRejected):
                provider.send_whatsapp('quote', '972500000000', 'Q-1', 'quote.pdf', self.pdf)
            self.assertEqual(post.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
