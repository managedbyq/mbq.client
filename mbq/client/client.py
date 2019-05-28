import logging
from io import BufferedReader, BytesIO
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


class ServiceClient:
    def __init__(self, api_url, auth=None, headers=None, post_process_response=None,
                 correlation_id_getter=None, default_timeout=30):
        """ We use correlation_ids to track the flow of a request between different services.
        It is the responsibility of users of ServiceClient to implement a correlation_id_getter
        """
        self._api_url = api_url
        self._auth = auth
        self._headers = headers
        self._post_process_response = post_process_response
        self._timeout = default_timeout
        self.correlation_id_getter = correlation_id_getter
        self.session = requests.Session()

    def _make_url(self, url):
        parsed = urlparse(url)
        if not any([parsed.scheme, parsed.netloc]):
            url = '{}{}'.format(self._api_url, url)

        return url

    def _make_request(self, method, url, *args, **kwargs):
        if self._headers:
            kwargs['headers'] = dict(self._headers, **kwargs.get('headers', {}))
        else:
            kwargs['headers'] = kwargs.get('headers', {})

        if self.correlation_id_getter is not None:
            cid = self.correlation_id_getter()
            if cid is not None:
                kwargs['headers']['X-Correlation-Id'] = cid

        if self._auth and 'auth' not in kwargs:
            kwargs['auth'] = self._auth

        if self._timeout and 'timeout' not in kwargs:
            kwargs['timeout'] = self._timeout

        url = self._make_url(url)

        response = getattr(self.session, method)(url, *args, **kwargs)

        try:
            response.raise_for_status()
        except: # noqa
            msg = '{} Bad Response: {}'.format(response.status_code, response.content)
            logger.error(msg)
            raise

        try:
            if self._post_process_response is not None:
                data = self._post_process_response(response.json())
            else:
                data = response.json()
        except: # noqa
            if response.headers.get('content-length') == '0':
                data = None
            else:
                data = BufferedReader(BytesIO(response.content))

        return data

    def get(self, *args, **kwargs):
        return self._make_request('get', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._make_request('post', *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self._make_request('patch', *args, **kwargs)

    def put(self, *args, **kwargs):
        return self._make_request('put', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._make_request('delete', *args, **kwargs)
