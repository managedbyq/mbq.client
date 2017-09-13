import os
from tempfile import NamedTemporaryFile
from unittest import TestCase

from mbq.client.storage import FileStorage


class FileStorageTestCase(TestCase):

    def setUp(self):
        self.test_filename = NamedTemporaryFile(delete=False).name
        self.storage = FileStorage(self.test_filename)

    def tearDown(self):
        os.remove(self.test_filename)

    def test_storage(self):
        # When the file is empty, we should receive None for any key.
        self.assertIsNone(self.storage.get('key1'))

        # We should be able to write a key/value,
        self.storage.set('key1', 'value1')
        # retrieve it,
        self.assertEqual(self.storage.get('key1'), 'value1')
        # and still receive None for missing keys.
        self.assertIsNone(self.storage.get('key2'))

        # We should be able to write a 2nd key,
        self.storage.set('key2', 'value2')
        # retrieve it,
        self.assertEqual(self.storage.get('key2'), 'value2')
        # still retrieve the earlier key we wrote,
        self.assertEqual(self.storage.get('key1'), 'value1')
        # and still receive None for missing keys.
        self.assertIsNone(self.storage.get('key3'))

        # We should be able to update an existing key,
        self.storage.set('key2', 'some-new-value')
        # see the value change when retrieving,
        self.assertEqual(self.storage.get('key2'), 'some-new-value')
        # the other values should remain unchanged,
        self.assertEqual(self.storage.get('key1'), 'value1')
        # and we should still receive None for missing keys.
        self.assertIsNone(self.storage.get('key3'))

        # If we re-init the storage object with the same file,
        self.storage = FileStorage(self.test_filename)
        # all keys should be persisted.
        self.assertEqual(self.storage.get('key2'), 'some-new-value')
        self.assertEqual(self.storage.get('key1'), 'value1')
        self.assertIsNone(self.storage.get('key3'))
