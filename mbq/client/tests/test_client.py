from unittest import TestCase

from .compat import patch
from mbq.client.client import ServiceClient


class CorrelationIDTestCase(TestCase):
    def setUp(self):
        self.client = ServiceClient('https://foo.com/')

    def test_correlation_id_provided(self):
        with patch('requests.get') as requests_mock:
            self.client.get('/url', correlation_id='hello-world')
            self.assertEquals(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertEquals('hello-world', headers['X-Correlation-Id'])

    def test_correlation_id_not_provided(self):
        with patch('requests.get') as requests_mock:
            self.client.get('/url')
            self.assertEquals(1, requests_mock.call_count)
            headers = requests_mock.call_args[1]['headers']
            self.assertTrue(headers['X-Correlation-Id'])
