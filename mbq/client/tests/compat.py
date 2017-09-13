try:
    from unittest.mock import call, MagicMock, patch  # noqa
except ImportError:
    from mock import call, MagicMock, patch  # noqa
