try:
    from unittest import mock
except ImportError:
    import mock  # noqa

MagicMock = mock.MagicMock
patch = mock.patch
call = mock.call
