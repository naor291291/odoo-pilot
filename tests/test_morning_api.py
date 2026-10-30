"""Provider contract and failure tests; runnable without an Odoo installation."""
import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch


path = Path(__file__).resolve().parents[1] / 'addons/field_work_photos/services/morning_api.py'
spec = importlib.util.spec_from_file_location('morning_api', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MorningAPI, MorningError = module.MorningAPI, module.MorningError
CLIENT = '11111111-1111-4111-8111-111111111111'
DOC = '22222222-2222-4222-8222-222222222222'


class TestMorningAPI(unittest.TestCase):
    def auth(self, token='fake-access-token'):
        return 200, {'accessToken': token, 'expiresAt': int(time.time()) + 3600, 'tokenType': 'Bearer'}

    def client(self, replies, environment='sandbox'):
        sender = Mock(side_effect=replies)
        return MorningAPI(environment, 'fake-key', 'fake-secret', send=sender), sender

    def test_sandbox_oauth_and_document_search_use_current_contract(self):
        client, sender = self.client([self.auth(), (200, {'items': []})])
        client.search_documents(CLIENT, 305, '12345', page=2)
        auth, search = sender.call_args_list
        self.assertEqual(auth.args[0], 'https://api.sandbox.morning.dev/idp/v1/oauth/token')
        self.assertEqual(auth.args[2], {'grant_type': 'client_credentials', 'client_id': 'fake-key', 'client_secret': 'fake-secret'})
        self.assertEqual(search.args[0], 'https://sandbox.d.greeninvoice.co.il/api/v1/documents/search')
        self.assertEqual(search.args[2], {'clientId': CLIENT, 'type': [305], 'number': 12345, 'page': 2, 'pageSize': 25, 'sort': 'documentDate'})
        self.assertNotIn('client_secret', search.args[2])

    def test_production_hosts_are_separate(self):
        client, sender = self.client([self.auth(), (200, {'id': CLIENT})], 'production')
        client.get_client(CLIENT)
        self.assertEqual(sender.call_args_list[0].args[0], 'https://api.morning.co/idp/v1/oauth/token')
        self.assertEqual(sender.call_args.args[0], 'https://api.greeninvoice.co.il/api/v1/clients/' + CLIENT)

    def test_reuses_token_within_operation(self):
        client, sender = self.client([self.auth(), (200, {'id': DOC}), (200, {'origin': 'https://example.test/doc'})])
        client.get_document(DOC)
        client.get_document_links(DOC)
        self.assertEqual(sender.call_count, 3)
        self.assertEqual(sender.call_args.args[1], 'GET')

    def test_refreshes_rejected_token_once(self):
        client, sender = self.client([self.auth('old'), (401, {}), self.auth('new'), (200, {'id': CLIENT})])
        self.assertEqual(client.get_client(CLIENT)['id'], CLIENT)
        self.assertEqual(sender.call_args.args[3]['Authorization'], 'Bearer new')

    def test_repeated_unauthorized_fails_without_retry_loop_or_secret(self):
        client, sender = self.client([self.auth(), (401, {}), self.auth(), (401, {'echo': 'fake-secret'})])
        with self.assertRaises(MorningError) as caught:
            client.get_client(CLIENT)
        self.assertEqual(sender.call_count, 4)
        self.assertNotIn('fake-secret', str(caught.exception))

    def test_429_fails_promptly_without_sleep_or_repeated_calls(self):
        client, sender = self.client([self.auth(), (429, {})])
        with self.assertRaisesRegex(MorningError, 'קצב'):
            client.get_document(DOC)
        self.assertEqual(sender.call_count, 2)

    def test_subscription_error_is_actionable(self):
        client, _ = self.client([(400, {'error': 'unauthorized_client'})])
        with self.assertRaisesRegex(MorningError, 'Best'):
            client.get_client(CLIENT)

    def test_ids_cannot_inject_a_different_endpoint(self):
        client, sender = self.client([])
        for value in ('../documents', 'https://evil.test', DOC + '/close', ''):
            with self.assertRaises(MorningError):
                client.get_document(value)
        sender.assert_not_called()

    def test_invalid_search_does_not_authenticate(self):
        client, sender = self.client([])
        for name in ('', ' א ', None):
            with self.assertRaises(MorningError):
                client.search_clients(name)
        with self.assertRaises(MorningError):
            client.search_documents(CLIENT, 305, 'not-a-number')
        with self.assertRaises(MorningError):
            client.search_documents(CLIENT, 330)
        sender.assert_not_called()

    def test_active_client_search_is_paginated(self):
        client, sender = self.client([self.auth(), (200, {'items': []})])
        client.search_clients(' יעקב ', page=3)
        self.assertEqual(sender.call_args.args[2], {'name': 'יעקב', 'active': True, 'page': 3, 'pageSize': 25})

    def test_bad_auth_response_is_rejected(self):
        for response in ({}, {'accessToken': 'x', 'expiresAt': 0}, {'accessToken': 'x', 'expiresAt': float('nan')}, {'accessToken': 7, 'expiresAt': time.time()+3600}):
            client, sender = self.client([(200, response)])
            with self.assertRaises(MorningError):
                client.get_client(CLIENT)
            self.assertEqual(sender.call_count, 1)

    def test_missing_keys_and_invalid_environment_fail_locally(self):
        for values in [('sandbox', '', ''), ('unknown', 'a', 'b')]:
            with self.assertRaises(MorningError):
                MorningAPI(*values)

    def test_unexpected_response_and_5xx_do_not_echo_provider_data(self):
        for response in [(200, []), (503, {'echo': 'fake-secret'})]:
            client, _ = self.client([self.auth(), response])
            with self.assertRaises(MorningError) as caught:
                client.get_document(DOC)
            self.assertNotIn('fake-secret', str(caught.exception))

    def test_transport_has_timeout_and_size_limit(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.code = 200
        response.read.return_value = b'{}'
        opener = Mock()
        opener.open.return_value = response
        with patch.object(module.urllib.request, 'build_opener', return_value=opener):
            status, body = module.transport('https://example.test', 'GET', None, {})
        self.assertEqual((status, body), (200, {}))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 15)
        response.read.assert_called_once_with(2 * 1024 * 1024 + 1)

    def test_transport_does_not_follow_redirects(self):
        self.assertIsNone(module.NoRedirect().redirect_request(None, None, 302, 'redirect', {}, 'https://elsewhere.test'))


if __name__ == '__main__':
    unittest.main()
