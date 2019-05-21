from typing import Dict
from unittest import TestCase
from unittest.mock import Mock

from .. import permissions as sut


class TestOSCoreClient:
    def __init__(self, data):
        self.data = data

    def fetch_permissions(
        self, person_id: str, org_ref: sut.UUIDType
    ) -> sut.FetchedPermissionsDoc:
        result: Dict = {"global": self.data.get("global", [])}
        result.update({org_ref: self.data.get(org_ref, [])})
        return result

    def fetch_permissions_for_location(
        self, person_id: str, location_id: int, location_type: sut.RefType
    ) -> sut.FetchedPermissionsDoc:
        result: Dict = {"global": self.data.get("global", [])}
        key = f"{location_type}:{location_id}"
        result.update({key: self.data.get(key, [])})
        return result


class PermissionsClientTest(TestCase):
    def setUp(self):
        test_data = {
            "org": ["read:invoices"],
            "company:1": ["read:orders", "write:orders"],
            "vendor:2": ["read:team"],
            "global": ["read:global"],
        }
        self.client = sut.PermissionsClient(
            TestOSCoreClient(test_data), cache_name=None
        )

    def test_cache_key(self):
        self.assertEqual(
            self.client._cache_key("person", "123"), "permissions_client:person:123"
        )
        self.assertEqual(
            self.client._cache_key("person2", "456", "company"),
            "permissions_client:person2:456:company",
        )

    def test_global_cache_key(self):
        self.assertEqual(
            self.client._global_cache_key("person"), "permissions_client:person:global"
        )

    def test_cache_read_no_cache(self):
        # Just testing that this doesn't error
        self.assertEqual(self.client._cache_read("person", "org"), None)

    def test_cache_read_with_empty_cache(self):
        cache_mock = Mock()
        self.client.cache = cache_mock

        cache_mock.get_many.return_value = {}

        self.assertEqual(self.client._cache_read("person", "org"), None)

        cache_mock.get_many.assert_called_once_with(
            ["permissions_client:person:global", "permissions_client:person:org"]
        )

    def test_cache_read_with_populated_cache(self):
        cache_mock = Mock()
        self.client.cache = cache_mock

        cached_doc = {
            "permissions_client:person:global": "|",
            "permissions_client:person:org": "read:invoices|",
        }
        cache_mock.get_many.return_value = cached_doc

        self.assertEqual(self.client._cache_read("person", "org"), cached_doc)

        cache_mock.get_many.assert_called_once_with(
            ["permissions_client:person:global", "permissions_client:person:org"]
        )

    def test_cache_transform(self):
        permissions_doc = {"org": ["read:invoices"], "global": []}

        cached_doc = {
            "permissions_client:person:org": "read:invoices|",
            "permissions_client:person:global": "|",
        }

        self.assertEqual(
            self.client._cache_transform("person", permissions_doc), cached_doc
        )

    def test_cache_write(self):
        cache_mock = Mock()
        self.client.cache = cache_mock
        self.client.cache_period_seconds = 123

        permissions_doc = {"org": ["read:invoices"], "global": []}

        cached_doc = {
            "permissions_client:person:org": "read:invoices|",
            "permissions_client:person:global": "|",
        }

        self.assertEqual(
            self.client._cache_transform("person", permissions_doc), cached_doc
        )

        self.client._cache_write(cached_doc)
        cache_mock.set_many.assert_called_once_with(cached_doc, timeout=123)

    def test_has_permission_org(self):
        self.assertTrue(self.client.has_permission("person", "read:invoices", "org"))
        self.assertFalse(self.client.has_permission("person", "read:stuff", "org"))
        # Implicit global
        self.assertTrue(self.client.has_permission("person", "read:global", "org"))

    def test_has_permission_location(self):
        self.assertTrue(
            self.client.has_permission("person", "read:orders", 1, "company")
        )
        self.assertFalse(
            self.client.has_permission("person", "read:stuff", 1, "company")
        )
        self.assertTrue(self.client.has_permission("person", "read:team", 2, "vendor"))
        self.assertFalse(
            self.client.has_permission("person", "read:stuff", 2, "vendor")
        )
        # Implicit global
        self.assertTrue(
            self.client.has_permission("person", "read:global", 1, "company")
        )
        self.assertTrue(
            self.client.has_permission("person", "read:global", 2, "vendor")
        )

    def test_has_global_permission(self):
        self.assertTrue(self.client.has_global_permission("person", "read:global"))
        self.assertFalse(self.client.has_global_permission("person", "read:stuff"))
