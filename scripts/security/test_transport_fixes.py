"""Bounded regressions for three High advisories; no external network or secrets."""
import importlib.metadata
import ssl
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from OpenSSL import SSL
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from urllib3.connection import HTTPSConnection, ProxyConfig


class TransportFixes(unittest.TestCase):
    def test_reviewed_versions(self):
        for name, version in [('cryptography', '50.0.2'), ('pyOpenSSL', '26.4.0'), ('urllib3', '2.8.0')]:
            self.assertEqual(importlib.metadata.version(name), version)

    def test_rsa_implicit_rejection_backend(self):
        # CVE-2023-50782: fixed wheel must use a hardened native backend.
        # Feature/version evidence, not a statistical timing-attack certification.
        self.assertTrue(backend._lib.Cryptography_HAS_IMPLICIT_RSA_REJECTION)

    def test_rsa_round_trip(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        message = b'synthetic compatibility fixture'
        ciphertext = key.public_key().encrypt(message, padding.PKCS1v15())
        self.assertEqual(key.decrypt(ciphertext, padding.PKCS1v15()), message)

    def cookie_result(self, cookie):
        # Allocate an oversized buffer even when checking vulnerable baselines:
        # never reproduce the actual out-of-bounds native write.
        connection = SSL.Connection(SSL.Context(SSL.DTLS_METHOD), None)
        helper = SSL._CookieGenerateCallbackHelper(lambda _: cookie)
        output = SSL._ffi.new('unsigned char[]', b'Z' * 1024)
        length = SSL._ffi.new('unsigned int *', 999)
        result = helper.callback(connection._ssl, output, length)
        return result, bytes(SSL._ffi.buffer(output, 1024)), length[0], helper

    def test_dtls_oversized_cookie_rejected_before_write(self):
        result, output, length, helper = self.cookie_result(b'A' * 257)
        self.assertEqual(result, 0)
        self.assertEqual(output, b'Z' * 1024)
        self.assertEqual(length, 999)
        self.assertIsInstance(helper._problems[0], ValueError)

    def test_dtls_short_cookie_preserved(self):
        result, output, length, helper = self.cookie_result(b'synthetic')
        self.assertEqual((result, length, output[:9]), (1, 9, b'synthetic'))
        self.assertFalse(helper._problems)

    def proxy_parameters(self, forwarding):
        proxy_context = ssl.create_default_context()
        target_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        target_context.check_hostname = False
        target_context.verify_mode = ssl.CERT_NONE
        conn = HTTPSConnection('target.invalid', ssl_context=target_context,
            cert_reqs=ssl.CERT_NONE, cert_file='target-only.pem',
            key_file='target-only.key', server_hostname='target.invalid',
            assert_hostname='target.invalid', assert_fingerprint='target-fingerprint',
            proxy_config=ProxyConfig(proxy_context, forwarding, 'proxy.invalid', None))
        with patch('urllib3.connection._ssl_wrap_socket_and_match_hostname',
                   return_value=SimpleNamespace(socket=object(), is_verified=True)) as wrap:
            conn._connect_tls_proxy('proxy.invalid', object())
        args = wrap.call_args.kwargs
        self.assertIs(args['ssl_context'], proxy_context)
        self.assertEqual(args['cert_reqs'], ssl.CERT_REQUIRED)
        self.assertEqual(proxy_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(args['server_hostname'], 'proxy.invalid')
        self.assertEqual(args['assert_hostname'], 'proxy.invalid')
        for name in ('cert_file', 'key_file', 'key_password', 'assert_fingerprint'):
            self.assertIsNone(args[name])

    def test_https_forwarding_proxy_policy_is_separate(self):
        self.proxy_parameters(True)

    def test_https_connect_proxy_policy_is_separate(self):
        self.proxy_parameters(False)


if __name__ == '__main__':
    unittest.main()
