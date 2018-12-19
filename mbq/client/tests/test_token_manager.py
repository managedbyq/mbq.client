from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from mbq.client.token_manager import TokenManager


class TokenManagerTestCase(TestCase):

    def setUp(self):

        self.get = MagicMock()

        self.set = MagicMock()

        self.storage_mock = MagicMock(
            set=self.set,
            get=self.get
        )

        self.get_auth0_token = MagicMock()

        get_auth0_token_patch = patch(
            'mbq.client.token_manager.get_access_token',
            self.get_auth0_token
        )
        get_auth0_token_patch.start()
        self.addCleanup(get_auth0_token_patch.stop)

        self.token_manager = TokenManager(
            {
                'api_ids': {'test': 'test_id', 'other_service': 'other_id'},
                'client_id': 'client_id',
                'client_secret': 'shh... it\'s a secret',
                'domain': 'auth0.com',
            },
            storage=self.storage_mock
        )

    def test_refresh_token(self):

        expected_token = 'fake_token'
        self.get_auth0_token.return_value = expected_token

        token = self.token_manager.refresh_token('test')

        self.assertEqual(token, expected_token)

        self.get_auth0_token.assert_called_once_with(
            'test_id',
            'client_id',
            'shh... it\'s a secret',
            'auth0.com'
        )

        self.set.assert_called_once_with(
            'token:test',
            expected_token
        )

    def test_refresh_all_tokens(self):

        refresh_token_mock = MagicMock()
        self.token_manager.refresh_token = refresh_token_mock

        self.token_manager.refresh_all_tokens()

        refresh_token_mock.assert_has_calls(
            [call('test'), call('other_service')], any_order=True
        )
