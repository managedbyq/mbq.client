
[![Library Version](https://img.shields.io/pypi/v/mbq.client.svg)](https://pypi.python.org/pypi/mbq.client)
[![Library License](https://img.shields.io/pypi/l/mbq.client.svg)](https://pypi.python.org/pypi/mbq.client)
[![Support Python Versions](https://img.shields.io/pypi/pyversions/mbq.client.svg)](https://pypi.python.org/pypi/mbq.client)
[![Build Status](https://img.shields.io/travis/managedbyq/mbq.tokens/master.svg)](https://travis-ci.org/managedbyq/mbq.client)


# Installation

```bash
    pip install mbq.client
```

# Getting Started

Key Concepts:

`ServiceClient` wraps python's requests library to enable token based service to service authentication
`Authenticator` provides Auth0 token based authentication
`TokenManager` A manager that stores refreshable tokens with support for different persistent storage backends.

# Django Integration

`DjangoCacheStorage` is a thin wrapper that stores token in your django project's cache.

## Example

```python
    from django.core.cache import cache
    from mbq.client import ServiceClient, Authenticator, TokenManager, DjangoCacheStorage

    token_manager = TokenManager(
        settings={
            'api_ids': {'my_service': 'id'},
            'client_id': 'client_id',
            'client_secret': 'your_secret'
            'domain': 'auth0domain'
        },
        storage=DjangoCacheStorage(cache),
    )

    my_service_client = ServiceClient(
        auth=Authenticator(
            service_name='my_service',
            token_manager=token_manager
        )
    )


    my_service_client.get()
    my_service_client.post()
    my_service_client.patch()
    my_service_client.put()
    my_service_client.delete()


    access_token.refresh()
    access_token() #retrieves token

```