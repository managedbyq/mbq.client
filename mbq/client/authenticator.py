

class Authenticator:

    def __init__(self, service_name, token_manager):
        self._token_manager = token_manager
        self.service_name = service_name

    def __call__(self, request):
        request.headers['Authorization'] = 'Bearer {}'.format(
            self._token_manager.get_token(service_name=self.service_name)
        )
        return request
