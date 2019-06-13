import logging
import urllib
import uuid
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union, cast, overload
from uuid import UUID

import requests
from typing_extensions import Literal, Protocol

import mbq.metrics

from .. import ServiceClient


logger = logging.getLogger(__name__)

UUIDType = Union[str, UUID]
# External type returned from internal and external OS Core clients. Keys
# are the org refs if UUIDs, or {ref_type}:{ref_id} if legacy int types.
# Values are lists of scopes. Should also include a "global" literal key.
FetchedPermissionsDoc = Dict[str, List[str]]
# Internal type stored in the cache. Keys are cache keys with prefixes, colons, etc.
# Values are pipe-delimited strings with an additional pipe on the end.
CachedPermissionsDoc = Dict[str, str]
RefType = Union[Literal["company", "vendor"]]


@dataclass
class RefSpec:
    ref: Union[UUIDType, Literal["global"], int]
    type: Optional[RefType] = None


class ClientError(Exception):
    """Raised from within OSCoreClient implementations to denote the fetch
    failed due to a client-side error.
    """

    pass


class ServerError(Exception):
    """Raised from within OSCoreClient implementations to denote the fetch
    failed due to a server-side error.
    """

    pass


class OSCoreClient(Protocol):
    def fetch_permissions(
        self, person_id: str, org_ref: UUIDType
    ) -> FetchedPermissionsDoc:
        ...

    def fetch_permissions_for_location(
        self, person_id: str, location_id: int, location_type: RefType
    ) -> FetchedPermissionsDoc:
        ...

    def fetch_all_permissions(self, person_id: str) -> FetchedPermissionsDoc:
        ...


class OSCoreServiceClient:
    def __init__(self, client: ServiceClient):
        # The copying and munging here is attempting to deal with differences
        # in how the individual ServiceClients are configured. We can get rid
        # of it if we standardize within the services.

        # Note that we are doing a shallow copy so the Authenticator instance
        # will be shared
        self.client = copy(client)

        self.client._post_process_response = None
        self.client._headers = None

        parsed = urllib.parse.urlparse(self.client._api_url)
        self.client._api_url = f"{parsed.scheme}://{parsed.netloc}"

    def fetch_permissions(
        self, person_id: str, org_ref: UUIDType
    ) -> FetchedPermissionsDoc:
        logger.debug(f"Fetching permissions from OS Core: {person_id}, {org_ref}")

        try:
            return self.client.get(
                f"/api/v1/people/{person_id}/permissions/by-org-ref",
                params={"org_ref": org_ref},
            )
        except requests.exceptions.HTTPError as e:
            response = getattr(e, "response", None)
            if response is not None and response.status_code // 100 == 4:
                raise ClientError("Invalid request") from e
            raise ServerError("Server error") from e
        except Exception as e:
            raise ServerError("Server error") from e

    def fetch_permissions_for_location(
        self, person_id: str, location_id: int, location_type: RefType
    ) -> FetchedPermissionsDoc:
        logger.debug(
            f"Fetching permissions from OS Core: {person_id}, {location_type} {location_id}"
        )

        try:
            return self.client.get(
                f"/api/v1/people/{person_id}/permissions/by-location",
                params={"location_id": location_id, "location_type": location_type},
            )
        except requests.exceptions.HTTPError as e:
            response = getattr(e, "response", None)
            if response is not None and response.status_code // 100 == 4:
                raise ClientError("Invalid request") from e
            raise ServerError("Server error") from e
        except Exception as e:
            raise ServerError("Server error") from e

    def fetch_all_permissions(self, person_id: str) -> FetchedPermissionsDoc:
        logger.debug(f"Fetching all permissions from OS Core: {person_id}")

        try:
            return self.client.get(f"/api/v1/people/{person_id}/permissions/all")
        except requests.exceptions.HTTPError as e:
            response = getattr(e, "response", None)
            if response is not None and response.status_code // 100 == 4:
                raise ClientError("Invalid request") from e
            raise ServerError("Server error") from e
        except Exception as e:
            raise ServerError("Server error") from e


class Registrar:
    def __init__(self):
        self._callback_error_name = "callback_error"
        self._registry: Dict[str, List[Callable[..., None]]] = defaultdict(list)

    def register_error_handler(self, fn: Callable[[str, Exception], None]) -> None:
        """ Use this method to add a callback (fn) which will be executed when a callback
        raises an exception
        """
        self._registry[self._callback_error_name].append(fn)

    def register(self, name: str, fn: Callable[..., None]) -> None:
        """ Use this method to add a callback (fn) which will be executed when an event
        (name) is emitted
        """
        self._registry[name].append(fn)

    def emit(self, name: str, *args, **kwargs) -> None:
        """ Use this method to emit an event and trigger registered callbacks"""
        for fn in self._registry[name]:
            try:
                fn(*args, **kwargs)
            except Exception as e:
                if name != self._callback_error_name:
                    self.emit(self._callback_error_name, name, e)
                else:
                    raise


class PermissionsClient:
    """Cache-aware client for consuming the Permissions API from OS Core.

    os_core_client: OSCoreClient Protocol implementation used to talk to OS Core. From
                    remote services, this should be a wrapped ServiceClient instance.
                    Use the provided OSCoreServiceClient wrapper in this contrib.
                    From OS Core itself, this should make local function calls.
    cache_name: Name of the Django cache to use, default "default". Pass None
                to disable caching.
    cache_period_seconds: Expiration time on cache keys in seconds.
    """

    _cache_prefix = "permissions_client"
    _collector = None

    def __init__(
        self,
        os_core_client: OSCoreClient,
        cache_name="default",
        cache_period_seconds=120,
    ):
        self.registrar = Registrar()
        self.os_core_client = os_core_client

        if cache_name is not None:
            from django.core.cache import caches  # type: ignore

            self.cache = caches[cache_name] if cache_name else None
            self.cache_period_seconds = cache_period_seconds
        else:
            self.cache = None
            self.cache_period_seconds = None

    @property
    def collector(self):
        if self._collector is None:
            if mbq.metrics._initialized is False:
                raise RuntimeError("mbq.metrics is not initialized")
            self._collector = mbq.metrics.Collector(
                namespace="mbq.client.permissions",
                tags={
                    "service": mbq.metrics._service,
                    "env": mbq.metrics._env.long_name,
                },
            )
        return self._collector

    def _cache_key(self, person_id: str, spec: RefSpec) -> str:
        if spec.type is not None:
            return f"{self._cache_prefix}:{person_id}:{spec.ref}:{spec.type}"
        return f"{self._cache_prefix}:{person_id}:{spec.ref}"

    def _global_cache_key(self, person_id: str) -> str:
        return f"{self._cache_prefix}:{person_id}:global"

    def _cache_read(
        self, person_id: str, ref_specs: List[RefSpec]
    ) -> Optional[CachedPermissionsDoc]:
        if not self.cache:
            return None

        keys = [self._global_cache_key(person_id)]
        for spec in ref_specs:
            if spec.ref != "global":
                keys.append(self._cache_key(person_id, spec))

        try:
            with self.collector.timed("cache.read.time"):
                fetched = self.cache.get_many(keys)
        except Exception as e:
            raise ServerError("Error reading from cache") from e

        if len(fetched.keys()) != len(keys):
            logger.debug(f"Not all keys found in cache, got: {fetched}")
            self.collector.increment("cache.read", tags={"result": "miss"})
            return None

        logger.debug(f"Successful cache read: {fetched}")
        self.collector.increment("cache.read", tags={"result": "hit"})

        return fetched

    def _cache_transform(
        self, person_id: str, permissions_doc: FetchedPermissionsDoc
    ) -> CachedPermissionsDoc:
        logger.debug(f"Transforming to cache representation: {permissions_doc}")

        cache_doc = {}
        for ref, scopes in permissions_doc.items():
            org_ref: str
            ref_type: Optional[RefType] = None

            if ":" in ref:
                split = ref.split(":")
                ref_type, org_ref = cast(RefType, split[0]), split[1]
            else:
                org_ref = ref

            joined_scopes = f"{'|'.join(scopes)}|"
            cache_doc[
                self._cache_key(person_id, RefSpec(org_ref, ref_type))
            ] = joined_scopes

        return cache_doc

    def _cache_write(self, doc: CachedPermissionsDoc) -> None:
        if self.cache:
            logger.debug(f"Writing to cache: {doc}")
            try:
                with self.collector.timed("cache.write.time"):
                    self.cache.set_many(doc, timeout=self.cache_period_seconds)
                self.collector.increment("cache.write")
            except Exception as e:
                raise ServerError("Error writing to cache") from e

    def _has_permission(
        self, person_id: UUIDType, scope: str, specs: List[RefSpec]
    ) -> bool:
        """Returns bool of whether the given person has the given
        scope on ALL RefSpecs specified.
        """
        person_id = str(person_id)

        cached_doc = self._cache_read(person_id, specs)

        if not cached_doc:
            if len(specs) > 1 or specs[0].ref == "global":
                logger.debug("Using fetch_all_permissions")
                fetched_doc = self.os_core_client.fetch_all_permissions(person_id)
            else:
                spec = specs[0]
                if spec.type is not None:
                    logger.debug("Using fetch_permissions_for_location")
                    fetched_doc = self.os_core_client.fetch_permissions_for_location(
                        person_id, int(spec.ref), spec.type
                    )
                else:
                    logger.debug("Using fetch_permissions")
                    assert isinstance(spec.ref, (uuid.UUID, str))
                    fetched_doc = self.os_core_client.fetch_permissions(
                        person_id, spec.ref
                    )
            cached_doc = self._cache_transform(person_id, fetched_doc)
            self._cache_write(cached_doc)

        found = True
        if f"{scope}|" in cached_doc.get(self._global_cache_key(person_id), ""):
            pass
        else:
            for spec in specs:
                cache_key = self._cache_key(person_id, spec)
                if f"{scope}|" not in cached_doc.get(cache_key, ""):
                    found = False
                    break

        return found

    def has_global_permission(self, person_id: UUIDType, scope: str) -> bool:
        """Test whether the scope is granted to the person on the global scope."""
        with self.collector.timed(
            "has_permission.time", tags={"call": "has_global_permission"}
        ):
            result = self._has_permission(person_id, scope, [RefSpec("global")])
        self.collector.increment(
            "has_permission",
            tags={
                "call": "has_global_permission",
                "result": str(result),
                "scope": scope,
            },
        )
        self.registrar.emit(
            "has_global_permission_completed", person_id, scope, result=result
        )
        return result

    @overload  # noqa: F811
    def has_permission(
        self, person_id: UUIDType, scope: str, org_ref: UUIDType
    ) -> bool:
        ...

    @overload  # noqa: F811
    def has_permission(
        self, person_id: UUIDType, scope: str, org_ref: int, ref_type: RefType
    ) -> bool:
        ...

    def has_permission(  # noqa: F811
        self,
        person_id: UUIDType,
        scope: str,
        org_ref: Union[UUIDType, int],
        ref_type: Optional[RefType] = None,
    ) -> bool:
        """Test whether the scope is granted to the person on the
        provided org or location references.

        This should not be used to test for explicit global permissions, prefer
        has_global_permission instead.
        """
        with self.collector.timed(
            "has_permission.time", tags={"call": "has_permission"}
        ):
            result = self._has_permission(
                person_id, scope, [RefSpec(org_ref, ref_type)]
            )
        self.collector.increment(
            "has_permission",
            tags={"call": "has_permission", "result": str(result), "scope": scope},
        )
        self.registrar.emit(
            "has_permission_completed",
            person_id,
            scope,
            org_ref,
            ref_type=ref_type,
            result=result,
        )
        return result

    @overload  # noqa: F811
    def has_all_permissions(
        self, person_id: UUIDType, scope: str, *, org_refs: List[UUIDType]
    ) -> bool:
        ...

    @overload  # noqa: F811
    def has_all_permissions(
        self, person_id: UUIDType, scope: str, *, org_refs: List[int], ref_type: RefType
    ) -> bool:
        ...

    def has_all_permissions(  # noqa: F811
        self,
        person_id: UUIDType,
        scope: str,
        *,
        org_refs: Union[List[UUIDType], List[int]],
        ref_type: Optional[RefType] = None,
    ) -> bool:
        """Test whether the scope is granted to the person on ALL of the
        provided org or location references.

        This should not be used to test for explicit global permissions, prefer
        has_global_permission instead.
        """
        with self.collector.timed(
            "has_permission.time", tags={"type": "has_all_permissions"}
        ):
            specs = [RefSpec(ref, ref_type) for ref in org_refs]
            result = self._has_permission(person_id, scope, specs)
        self.collector.increment(
            "has_permission",
            tags={"call": "has_all_permissions", "result": str(result), "scope": scope},
        )
        self.registrar.emit(
            "has_all_permissions_completed",
            person_id,
            scope,
            org_refs=org_refs,
            ref_type=ref_type,
            result=result,
        )
        return result
