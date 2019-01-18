import requests


def get_access_token(audience, client_id, client_secret, domain):
    response = requests.post(
        'https://{}/oauth/token'.format(domain),
        json={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'audience': audience,
        }
    )
    response.raise_for_status()
    return response.json().get('access_token')
