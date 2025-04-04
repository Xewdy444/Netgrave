"""A module for interacting with the Censys API."""

from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set, Tuple, TypedDict

import aiohttp

from .search_engine import SearchEngine


@dataclass
class CensysCredentials:
    """A class for representing Censys credentials."""

    api_id: str
    api_secret: str

    def __str__(self) -> str:
        return f"{self.api_id}:{self.api_secret}"


class CensysError(Exception):
    """An exception raised when an error occurs with the Censys API."""


class Service(TypedDict):
    """A dictionary of service information."""

    extended_service_name: str
    service_name: str
    transport_protocol: str
    port: int


class Censys(SearchEngine):
    """
    A class for interacting with the Censys API.

    Parameters
    ----------
    credentials : CensysCredentials
        The credentials to use for the API.
    """

    PAGE_SIZE: ClassVar[int] = 100

    def __init__(self, credentials: CensysCredentials) -> None:
        self._credentials = credentials

        self._session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(credentials.api_id, credentials.api_secret)
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def search(
        self, query: str, *, cursor: Optional[str] = None, per_page: int = PAGE_SIZE
    ) -> Optional[Dict[str, Any]]:
        """
        Search the Censys API for the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        cursor : Optional[str], optional
            The cursor token to use, by default None.
        per_page : int, optional
            The number of results per page, by default PAGE_SIZE.

        Returns
        -------
        Optional[Dict[str, Any]]
            The response from Censys. Returns None if the query is invalid.
        """
        params = {"q": query, "per_page": per_page}

        if cursor is not None:
            params["cursor"] = cursor

        async with self._session.get(
            "https://search.censys.io/api/v2/hosts/search", params=params
        ) as response:
            if response.status == 422:
                return None

            response_json = await response.json()

        if "error" in response_json:
            raise CensysError(response_json["error"])

        return response_json

    async def get_hosts(
        self,
        query: str,
        *,
        count: int = 100,
        service_filter: Optional[Callable[[Service], bool]] = None,
    ) -> List[Tuple[str, int]]:
        """
        Get hosts from Censys that match the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        count : int, optional
            The number of hosts to retrieve, by default 100.
        service_filter : Optional[Callable[[Service], bool]], optional
            A function to filter the services, by default None.
            The function should return True if the service should be included
            in the results.

        Returns
        -------
        List[Tuple[str, int]]
            The list of hosts.
        """
        hosts: Set[Tuple[str, int]] = set()
        cursor: Optional[str] = None

        while len(hosts) < count:
            per_page = (
                min(count - len(hosts), self.PAGE_SIZE)
                if service_filter is None
                else self.PAGE_SIZE
            )

            response = await self.search(query, cursor=cursor, per_page=per_page)

            if response is None:
                break

            for host in response["result"]["hits"]:
                for service in host["services"]:
                    if service_filter is not None and not service_filter(service):
                        continue

                    hosts.add((host["ip"], service["port"]))

                    if len(hosts) == count:
                        return list(hosts)

            cursor = response["result"]["links"]["next"]

            if not cursor:
                break

        return list(hosts)
