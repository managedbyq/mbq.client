from copy import deepcopy
from typing import Dict, List, Union
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

        test_fn.assert_called_once_with("arg_1", "arg_2", arg3="arg3", arg4="arg4")

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
        result: Dict = {"global": self.data["people"][person_id].get("global", [])}
        result.update({org_ref: self.data["people"][person_id].get(org_ref, [])})
        return result

    def fetch_permissions_for_location(
        self, person_id: str, location_id: int, location_type: sut.RefType
    ) -> sut.FetchedPermissionsDoc:
        result: Dict = {"global": self.data["people"][person_id].get("global", [])}
        key = f"{location_type}:{location_id}"
        result.update({key: self.data["people"][person_id].get(key, [])})
        return result

    def fetch_all_permissions(self, person_id: str) -> sut.FetchedPermissionsDoc:
        return deepcopy(self.data["people"][person_id])

    def fetch_org_refs_for_permission(
        self, person_id: str, scope: str
    ) -> List[Union[sut.UUIDType, str]]:
        return [
            name
            for (name, scopes) in self.data["people"][person_id].items()
            if scope in self.data["people"][person_id][name]
        ]

    def fetch_persons_with_permission(
        self, scope: str, org_ref: sut.UUIDType
    ) -> List[str]:
        return [
            person_id
            for person_id, permissions in self.data["people"].items()
            if scope in permissions.get(org_ref, [])
        ]

    def fetch_persons_with_permission_for_location(
        self, scope: str, ref_type: sut.RefType, org_ref: int
    ) -> List[str]:
        return [
            person_id
            for person_id, permissions in self.data["people"].items()
            if scope in permissions.get(f"{ref_type}:{org_ref}", [])
        ]

    def register_staffmembership_permission_scope(
        self, name: str, service: str
    ) -> None:
        self.data["scopes"][name] = service

    def unregister_staffmembership_permission_scope(self, name: str) -> None:
        self.data["scopes"].pop(name)


class PermissionsClientTest(TestCase):
    def setUp(self):
        self.test_data = {
            "people": {
                "person_1": {
                    "org": ["read:invoices"],
                    "vendor:1": ["read:orders", "read:team"],
                    "org2": ["read:invoices", "write:invoices"],
                    "company:1": ["read:orders", "write:orders", "read:invoices"],
                    "company:2": ["read:orders", "read:invoices"],
                    "vendor:2": ["read:orders", "read:team"],
                    "vendor:3": ["read:orders", "read:team", "read:invoices"],
                    "vendor:4": ["read:invoices"],
                    "global": ["read:global"],
                },
                "person_2": {
                    "org": ["read:invoices"],
                    "company:1": ["read:orders", "write:orders", "read:invoices"],
                    "org3": ["read:invoices"],
                    "company:3": ["read:orders", "write:orders", "read:invoices"],
                },
            },
            "scopes": {},
        }
        self.client = sut.PermissionsClient(
            TestOSCoreClient(self.test_data), cache_name=None
        )

        self.client._collector = MagicMock()

    def test_cache_key(self):
        self.assertEqual(
            self.client._cache_key("person_1", sut.RefSpec("123")),
            "permissions_client:person_1:123",
        )
        self.assertEqual(
            self.client._cache_key("person2", sut.RefSpec("456", "company")),
            "permissions_client:person2:456:company",
        )

    def test_global_cache_key(self):
        self.assertEqual(
            self.client._global_cache_key("person_1"),
            "permissions_client:person_1:global",
        )

    def test_cache_read_no_cache(self):
        # Just testing that this doesn't error
        self.assertEqual(
            self.client._cache_read("person_1", [sut.RefSpec("org")]), None
        )

    def test_cache_read_with_empty_cache(self):
        cache_mock = Mock()
        self.client.cache = cache_mock

        cache_mock.get_many.return_value = {}

        self.assertEqual(
            self.client._cache_read("person_1", [sut.RefSpec("org")]), None
        )

        cache_mock.get_many.assert_called_once_with(
            ["permissions_client:person_1:global", "permissions_client:person_1:org"]
        )

    def test_cache_read_with_populated_cache(self):
        cache_mock = Mock()
        self.client.cache = cache_mock

        cached_doc = {
            "permissions_client:person_1:global": "|",
            "permissions_client:person_1:org": "read:invoices|",
        }
        cache_mock.get_many.return_value = cached_doc

        self.assertEqual(
            self.client._cache_read("person_1", [sut.RefSpec("org")]), cached_doc
        )

        cache_mock.get_many.assert_called_once_with(
            ["permissions_client:person_1:global", "permissions_client:person_1:org"]
        )

    def test_cache_transform(self):
        permissions_doc = {"org": ["read:invoices"], "global": []}

        cached_doc = {
            "permissions_client:person_1:org": "read:invoices|",
            "permissions_client:person_1:global": "|",
        }

        self.assertEqual(
            self.client._cache_transform("person_1", permissions_doc), cached_doc
        )

    def test_cache_write(self):
        cache_mock = Mock()
        self.client.cache = cache_mock
        self.client.cache_period_seconds = 123

        permissions_doc = {"org": ["read:invoices"], "global": []}

        cached_doc = {
            "permissions_client:person_1:org": "read:invoices|",
            "permissions_client:person_1:global": "|",
        }

        self.assertEqual(
            self.client._cache_transform("person_1", permissions_doc), cached_doc
        )

        self.client._cache_write(cached_doc)
        cache_mock.set_many.assert_called_once_with(cached_doc, timeout=123)

    def test_registered_hooks_has_permission_org(self):
        test_example_fn = Mock()
        self.client.registrar.register("has_permission_completed", test_example_fn)
        self.assertTrue(self.client.has_permission("person_1", "read:invoices", "org"))
        test_example_fn.assert_any_call(
            "person_1", "read:invoices", "org", ref_type=None, result=True
        )

    def test_registered_hooks_has_permission_location(self):
        test_example_fn = Mock()
        self.client.registrar.register("has_permission_completed", test_example_fn)
        self.assertTrue(
            self.client.has_permission("person_1", "read:orders", 1, "company")
        )
        test_example_fn.assert_any_call(
            "person_1", "read:orders", 1, ref_type="company", result=True
        )

    def test_registered_hooks_has_all_permissions(self):
        test_example_fn = Mock()
        self.client.registrar.register("has_all_permissions_completed", test_example_fn)
        self.assertTrue(
            self.client.has_all_permissions(
                "person_1", "read:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        test_example_fn.assert_any_call(
            "person_1", "read:orders", org_refs=[1, 2], ref_type="company", result=True
        )

    def test_registered_hooks_has_global_permissions(self):
        test_example_fn = Mock()
        self.client.registrar.register(
            "has_global_permission_completed", test_example_fn
        )
        self.assertTrue(self.client.has_global_permission("person_1", "read:global"))
        test_example_fn.assert_any_call("person_1", "read:global", result=True)

    def test_has_permission_org(self):
        self.assertTrue(self.client.has_permission("person_1", "read:invoices", "org"))
        self.assertFalse(self.client.has_permission("person_1", "read:stuff", "org"))
        # Implicit global
        self.assertTrue(self.client.has_permission("person_1", "read:global", "org"))

    def test_has_permission_location(self):
        self.assertTrue(
            self.client.has_permission("person_1", "read:orders", 1, "company")
        )
        self.assertFalse(
            self.client.has_permission("person_1", "read:stuff", 1, "company")
        )
        self.assertTrue(
            self.client.has_permission("person_1", "read:team", 2, "vendor")
        )
        self.assertFalse(
            self.client.has_permission("person_1", "read:stuff", 2, "vendor")
        )
        # Implicit global
        self.assertTrue(
            self.client.has_permission("person_1", "read:global", 1, "company")
        )
        self.assertTrue(
            self.client.has_permission("person_1", "read:global", 2, "vendor")
        )

    def test_has_global_permission(self):
        self.assertTrue(self.client.has_global_permission("person_1", "read:global"))
        self.assertFalse(self.client.has_global_permission("person_1", "read:stuff"))

    def test_has_all_permissions(self):
        self.assertTrue(
            self.client.has_all_permissions(
                "person_1", "read:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        self.assertFalse(
            self.client.has_all_permissions(
                "person_1", "write:orders", org_refs=[1, 2], ref_type="company"
            )
        )
        self.assertTrue(
            self.client.has_all_permissions(
                "person_1", "read:orders", org_refs=[1], ref_type="company"
            )
        )

        self.assertTrue(
            self.client.has_all_permissions(
                "person_1", "read:invoices", org_refs=["org", "org2"]
            )
        )
        self.assertFalse(
            self.client.has_all_permissions(
                "person_1", "write:invoices", org_refs=["org", "org2"]
            )
        )

        self.assertTrue(
            self.client.has_all_permissions(
                "person_1", "read:global", org_refs=[1, 2, 3, 4, 5], ref_type="vendor"
            )
        )
        self.assertTrue(
            self.client.has_all_permissions("person_1", "read:global", org_refs=["org"])
        )

    def test_get_org_refs_for_permission(self):
        self.assertEqual(
            self.client.get_org_refs_for_permission("person_1", "read:invoices"),
            sut.ConvenientOrgRefs(set(["org", "org2"]), set([1, 2]), set([3, 4])),
        )
        self.assertEqual(
            self.client.get_org_refs_for_permission("person_1", "read:stuff"),
            sut.ConvenientOrgRefs(),
        )

    def test_registered_hooks_test_get_org_refs_for_permission(self):
        test_example_fn = Mock()
        self.client.registrar.register(
            "get_org_refs_for_permission_completed", test_example_fn
        )

        self.client.get_org_refs_for_permission("person_1", "read:invoices")

        test_example_fn.assert_any_call(
            "person_1",
            "read:invoices",
            result=sut.ConvenientOrgRefs({"org", "org2"}, {1, 2}, {3, 4}),
        )

    def test_parse_raw_org_refs(self):
        raw_org_refs = ["vendor:3", "org2", "company:1", "org", "company:2", "vendor:4"]
        self.assertEqual(
            self.client._parse_raw_org_refs(raw_org_refs),
            sut.ConvenientOrgRefs(set(["org", "org2"]), set([1, 2]), set([3, 4])),
        )
        self.assertEqual(
            self.client._parse_raw_org_refs([]),
            sut.ConvenientOrgRefs(set(), set(), set()),
        )

    def test_get_persons_with_permissions(self):
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission("read:invoices", "org")
            ),
            {"person_1", "person_2"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", "org2"
                )
            ),
            {"person_1"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", "org3"
                )
            ),
            {"person_2"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", "minitrue"
                )
            ),
            set(),
        )

    def test_get_persons_with_permissions_for_location(self):
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", 1, "company"
                )
            ),
            {"person_1", "person_2"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:orders", 1, "vendor"
                )
            ),
            {"person_1"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", 3, "company"
                )
            ),
            {"person_2"},
        )
        self.assertEqual(
            set(
                p
                for p in self.client.get_persons_with_permission(
                    "read:invoices", 1234, "company"
                )
            ),
            set(),
        )

    def test_registered_hooks_test_get_persons_with_permission(self):
        test_example_fn = Mock()
        self.client.registrar.register(
            "get_persons_with_permission_completed", test_example_fn
        )

        self.client.get_persons_with_permission("read:invoices", "org")

        test_example_fn.assert_any_call(
            "read:invoices", "org", ref_type=None, result=["person_1", "person_2"]
        )

        self.client.get_persons_with_permission("read:invoices", 1, "company")

        test_example_fn.assert_any_call(
            "read:invoices", 1, ref_type="company", result=["person_1", "person_2"]
        )

    def test_register_and_unregister_scopes(self):
        self.client.register_staffmembership_permission_scope(
            "example_scope1", "example_service1"
        )
        self.client.register_staffmembership_permission_scope(
            "example_scope2", "example_service1"
        )
        self.client.register_staffmembership_permission_scope(
            "example_scope3", "example_service2"
        )
        self.client.register_staffmembership_permission_scope(
            "example_scope4", "example_service2"
        )
        self.assertEqual(
            self.test_data["scopes"],
            {
                "example_scope1": "example_service1",
                "example_scope2": "example_service1",
                "example_scope3": "example_service2",
                "example_scope4": "example_service2",
            },
        )
        self.client.unregister_staffmembership_permission_scope("example_scope1")
        self.client.unregister_staffmembership_permission_scope("example_scope2")
        self.client.unregister_staffmembership_permission_scope("example_scope3")
        self.client.unregister_staffmembership_permission_scope("example_scope4")
        self.assertEqual(self.test_data["scopes"], {})
