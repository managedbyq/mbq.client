

# Installation

```bash
    pip install mbq.client
```

# Getting Started

Key Concepts:

`ServiceClient` wraps python's requests library to enable token based service to service authentication
`Authenticator` provides Auth0 token based authentication
`AccessToken` A refreshable token that supports different persistent storage backends.

# Django Integration

`DjangoCacheStorage` is a thin wrapper that stores token in your django project's cache.

## Example

```python
    from django.core.cache import cache
    from mbq.client import ServiceClient, Authenticator, AccessToken, DjangoCacheStorage

    access_token = AccessToken(
        service_name='my_service',
        storage=DjangoCacheStorage(cache),
        settings={
            'api_ids': {'my_service': 'id'},
            'client_id': 'client_id',
            'client_secret': 'your_secret'
            'domain': 'auth0domain'
        }
    )

    client = ServiceClient(
        auth=Authenticator(
            access_token
        )
    )


    client.get()
    client.post()
    client.patch()
    client.put()
    client.delete()


    access_token.refresh()
    access_token() #retrieves token

```