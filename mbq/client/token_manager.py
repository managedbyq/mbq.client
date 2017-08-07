from .lib.auth0 import get_access_token


class TokenManager(object):

    def __init__(self, settings, storage):
        self.storage = storage
        self.settings = settings

    def get_token(self, service_name):
        token = self.storage.get('token:{}'.format(service_name))
        return token or self.refresh_token(service_name)

    def refresh_token(self, service_name):
        token = get_access_token(
            self.settings['api_ids'][service_name],
            self.settings['client_id'],
            self.settings['client_secret'],
            self.settings['domain'],
        )

        self.storage.set(
            'token:{}'.format(service_name),
            token
        )
        return token

    def refresh_all_tokens(self):
        for service_name in self.settings['api_ids']:
            self.refresh_token(service_name)
