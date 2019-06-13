from copy import deepcopy
from typing import Dict
from unittest import TestCase
from unittest.mock import MagicMock, Mock

from .. import permissions as sut


class TestRegistrar(TestCase):
    def setUp(self):
        self.registrar = sut.Registrar()

    def test_register_and_emit(self):
        test_fn = Mock()
        self.registrar.register("test_event", test_fn)

        self.registrar.emit("test_event", "arg_1", "arg_2", arg3="arg3", arg4="arg4")

        test_fn.assert_called_once_with(
            "arg_1", "arg_2", arg3="arg3", arg4="arg4"
        )

    def test_emit_unregistered(self):
        test_fn = Mock()
        self.registrar.emit("test_event", "arg_1", "arg_2", arg3="arg3", arg4="arg4")
        test_fn.assert_not_called()

    def test_register_error_handler(self):
        test_fn_raises_exception = Mock()
        exception = Exception("here comes the boom")
        test_fn_raises_exception.side_effect = exception
        error_handler_fn = Mock()

        self.registrar.register("test_event", test_fn_raises_exception)
        self.registrar.register_error_handler(error_handler_fn)

        self.registrar.emit("test_event", "arg_1", "arg_2", arg3="arg3", arg4="arg4")

        test_fn_raises_exception.assert_called_once_with(
            "arg_1", "arg_2", arg3="arg3", arg4="arg4"
        )
        error_handler_fn.assert_called_once_with("test_event", exception)


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

    def fetch_all_permissions(self, person_id: str) -> sut.FetchedPermissionsDoc:
        return deepcopy(self.data)


class PermissionsClientTest(TestCase):
    def setUp(self):
        test_data = {
            "org": ["read:invoices"],
            "org2": ["read:invoices", "write:invoices"],
            "company:1": ["read:orders", "write:orders"],
            "company:2": ["read:orders"],
            "vendor:2": ["read:team"],
            "global": ["read:global"],
        }
        self.client = sut.PermissionsClient(
            TestOSCoreClient(test_data), cache_name=None
        )

        self.client._collector = MagicMock()

    def test_cache_key(self):
        self.assertEqual(
            self.client._cache_key("person", sut.RefSpec("123")),
            "permissions_client:person:123",
        )
        self.assertEqual(
            self.client._cache_key("person2", sut.RefSpec("456", "company")),
            "permissions_client:person2:456:company",
        )

    def test_global_cache_key(self):
        self.assertEqual(
            self.client._global_cache_key("person"), "permissions_client:person:global"
        )

    def test_cache_read_no_cache(self):
        # Just testing that this doesn't error
        self.assertEqual(self.client._cache_read("person", [sut.RefSpec("org")]), None)

    def test_cache_read_with_empty_cache(self):
        cache_mock = Mock()
        self.client.cache = cache_mock

        cache_mock.get_many.return_value = {}

        self.assertEqual(self.client._cache_read("person", [sut.RefSpec("org")]), None)

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

        self.assertEqual(
            self.client._cache_read("person", [sut.RefSpec("org")]), cached_doc
        )

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

    def test_registered_hooks_has_permission_org(self):
        test_example_fn = Mock()
        self.client.registrar.register("has_permission_completed", test_example_fn)
        self.assertTrue(self.client.has_permission("person", "read:invoices", "org"))
        test_example_fn.assert_any_call(
            "person", "read:invoices", "org", ref_type=None, result=True
        )

    def test_registered_hooks_has_permission_location(self):
        test_example_fn = Mock()
        self.client.registrar.register("has_permission_completed", test_example_fn)
        self.assertTrue(
            self.client.has_permission("person", "read:orders", 1, "company")
        )
        test_example_fn.assert_any_call(
            "person", "read:orders", 1, ref_type="company", result=True
        )

    def test_registered_hooks_has_all_permissions(self):
        test_example_fn = Mock()
        self.client.registrar.register(
            "has_all_permissions_completed", test_example_fn
        )
        self.assertTrue(
            self.client.has_all_permissions(
                "person", "read:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        test_example_fn.assert_any_call(
            "person", "read:orders", org_refs=[1, 2], ref_type="company", result=True
        )

    def test_registered_hooks_has_global_permissions(self):
        test_example_fn = Mock()
        self.client.registrar.register(
            "has_global_permission_completed", test_example_fn
        )
        self.assertTrue(self.client.has_global_permission("person", "read:global"))
        test_example_fn.assert_any_call("person", "read:global", result=True)

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

    def test_has_all_permissions(self):
        self.assertTrue(
            self.client.has_all_permissions(
                "person", "read:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        self.assertFalse(
            self.client.has_all_permissions(
                "person", "write:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        self.assertTrue(
            self.client.has_all_permissions(
                "person", "read:orders", org_refs=[1], ref_type="company"
            )
        )

        self.assertTrue(
            self.client.has_all_permissions(
                "person", "read:invoices", org_refs=["org", "org2"]
            )
        )
        self.assertFalse(
            self.client.has_all_permissions(
                "person", "write:invoices", org_refs=["org", "org2"]
            )
        )

        self.assertTrue(
            self.client.has_all_permissions(
                "person", "read:global", org_refs=[1, 2, 3, 4, 5], ref_type="vendor"
            )
        )
        self.assertTrue(
            self.client.has_all_permissions("person", "read:global", org_refs=["org"])
        )
