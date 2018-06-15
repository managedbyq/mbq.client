from unittest import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

from .compat import patch
from mbq.client.client import ServiceClient


class CorrelationIDTestCase(TestCase):

    def test_correlation_id_getter_provided(self):
        self.client = ServiceClient(
            'https://foo.com/',
            correlation_id_getter=lambda: 'hello-world'
        )
        with patch('requests.get') as requests_mock:
            self.client.get('/url')
            self.assertEquals(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEquals('hello-world', headers['X-Correlation-Id'])

    def test_correlation_id_getter_not_provided(self):
        self.client = ServiceClient('https://foo.com/')
        with patch('requests.get') as requests_mock:
            self.client.get('/url')
            self.assertEquals(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertIsNone(headers.get('X-Correlation-Id'))

    def test_multivalued_correlation_id_getter_provided(self):
        cid_getter_mock = mock.Mock()
        cid_getter_mock.side_effect = ['hello-world', 'goodbye-world']
        self.client = ServiceClient(
            'https://foo.com/',
            correlation_id_getter=cid_getter_mock
        )

        with patch('requests.get') as requests_mock:
            self.client.get('/url')
            self.assertEquals(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEquals('hello-world', headers.get('X-Correlation-Id'))

            self.client.get('/url')
            self.assertEquals(2, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEquals('goodbye-world', headers.get('X-Correlation-Id'))
