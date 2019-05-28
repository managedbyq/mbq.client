from unittest import TestCase
from unittest.mock import Mock, patch

from mbq.client.client import ServiceClient


class CorrelationIDTestCase(TestCase):

    def test_correlation_id_getter_provided(self):
        self.client = ServiceClient(
            'https://foo.com/',
            correlation_id_getter=lambda: 'hello-world'
        )
        with patch('requests.Session.get') as requests_mock:
            self.client.get('/url')
            self.assertEqual(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('hello-world', headers['X-Correlation-Id'])

    def test_correlation_id_getter_not_provided(self):
        self.client = ServiceClient('https://foo.com/')
        with patch('requests.Session.get') as requests_mock:
            self.client.get('/url')
            self.assertEqual(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertIsNone(headers.get('X-Correlation-Id'))

    def test_multivalued_correlation_id_getter_provided(self):
        cid_getter_mock = Mock()
        cid_getter_mock.side_effect = ['hello-world', 'goodbye-world']
        self.client = ServiceClient(
            'https://foo.com/',
            correlation_id_getter=cid_getter_mock
        )

        with patch('requests.Session.get') as requests_mock:
            self.client.get('/url')
            self.assertEqual(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('hello-world', headers.get('X-Correlation-Id'))

            self.client.get('/url')
            self.assertEqual(2, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('goodbye-world', headers.get('X-Correlation-Id'))

    def test_headers(self):
        with patch('requests.Session.get') as requests_mock:
            self.client = ServiceClient(
                'https://foo.com/',
                headers={'Test-Header': 'header-value'}
            )
            self.client.get('/url')
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('header-value', headers.get('Test-Header'))

        with patch('requests.Session.get') as requests_mock:
            self.client = ServiceClient(
                'https://foo.com/',
            )
            self.client.get('/url', headers={'Test-Get-Header': 'get-header-value'})
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('get-header-value', headers.get('Test-Get-Header'))

        with patch('requests.Session.get') as requests_mock:
            self.client = ServiceClient(
                'https://foo.com/',
                headers={'Test-Service-Header': 'service-header-value'}
            )
            self.client.get('/url', headers={'Test-Get-Header-2': 'get-header-value-2'})
            headers = requests_mock.call_args[1]['headers']
            self.assertEqual('get-header-value-2', headers.get('Test-Get-Header-2'))
            self.assertEqual('service-header-value', headers.get('Test-Service-Header'))
