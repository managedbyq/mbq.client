try:
    from urlparse import urlparse  # noqa
except ImportError:
    from urllib.parse import urlparse  # noqa
