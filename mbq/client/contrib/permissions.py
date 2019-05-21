import logging
import urllib
from copy import copy
from typing import Dict, List, Optional, Union, cast, overload
from uuid import UUID

import requests
from typing_extensions import Literal, Protocol

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
                f"/api/v1/people/{person_id}/permissions", params={"org_ref": org_ref}
            )
        except requests.exceptions.HTTPError as e:
            response = getattr(e, "response", None)
            if response and response.status_code // 100 == 4:
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
                f"/api/v1/people/{person_id}/permissions",
                params={"location_id": location_id, "location_type": location_type},
            )
        except requests.exceptions.HTTPError as e:
            response = getattr(e, "response", None)
            if response and response.status_code // 100 == 4:
                raise ClientError("Invalid request") from e
            raise ServerError("Server error") from e
        except Exception as e:
            raise ServerError("Server error") from e


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

    def __init__(
        self,
        os_core_client: OSCoreClient,
        cache_name="default",
        cache_period_seconds=120,
    ):
        self.os_core_client = os_core_client

        if cache_name is not None:
            from django.core.cache import caches  # type: ignore

            self.cache = caches[cache_name] if cache_name else None
            self.cache_period_seconds = cache_period_seconds
        else:
            self.cache = None
            self.cache_period_seconds = None

    def _cache_key(
        self, person_id: str, ref: Union[str, int], ref_type: Optional[RefType] = None
    ) -> str:
        """ref can be either an org_ref or a legacy int ref here"""
        if ref_type:
            return f"{self._cache_prefix}:{person_id}:{ref}:{ref_type}"
        return f"{self._cache_prefix}:{person_id}:{ref}"

    def _global_cache_key(self, person_id: str) -> str:
        return f"{self._cache_prefix}:{person_id}:global"

    def _cache_read(
        self, person_id: str, org_ref: str, ref_type: Optional[RefType] = None
    ) -> Optional[CachedPermissionsDoc]:
        if not self.cache:
            return None

        keys = [self._global_cache_key(person_id)]
        if org_ref != "global":
            keys.append(self._cache_key(person_id, org_ref, ref_type))

        try:
            fetched = self.cache.get_many(keys)
        except Exception as e:
            raise ServerError("Error reading from cache") from e

        if len(fetched.keys()) != len(keys):
            logger.debug(f"Not all keys found in cache, got: {fetched}")
            return None

        logger.debug(f"Successful cache read: {fetched}")

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
                self._cache_key(person_id, org_ref, ref_type)
            ] = joined_scopes

        return cache_doc

    def _cache_write(self, doc: CachedPermissionsDoc) -> None:
        if self.cache:
            logger.debug(f"Writing to cache: {doc}")
            try:
                self.cache.set_many(doc, timeout=self.cache_period_seconds)
            except Exception as e:
                raise ServerError("Error writing to cache") from e

    def _has_permission(
        self,
        person_id: UUIDType,
        scope: str,
        org_ref: Union[UUIDType, Literal["global"], int],
        ref_type: Optional[RefType] = None,
    ) -> bool:
        person_id = str(person_id)
        org_ref = str(org_ref)

        cached_doc = self._cache_read(person_id, org_ref, ref_type)
        if not cached_doc:
            if ref_type is not None:
                fetched_doc = self.os_core_client.fetch_permissions_for_location(
                    person_id, int(org_ref), ref_type
                )
            else:
                fetched_doc = self.os_core_client.fetch_permissions(person_id, org_ref)
            cached_doc = self._cache_transform(person_id, fetched_doc)
            self._cache_write(cached_doc)

        if cached_doc:
            for scopes in cached_doc.values():
                if f"{scope}|" in scopes:
                    return True

        return False

    def has_global_permission(self, person_id: UUIDType, scope: str) -> bool:
        return self._has_permission(person_id, scope, "global")

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
        return self._has_permission(person_id, scope, org_ref, ref_type)
