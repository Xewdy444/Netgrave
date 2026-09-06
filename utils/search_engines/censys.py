"""A module for interacting with the Censys Platform API."""

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

import aiohttp

from .search_engine import SearchEngine


@dataclass
class CensysCredentials:
    """A class for representing Censys credentials."""

    personal_access_token: str
    organization_id: Optional[str] = None

    def __str__(self) -> str:
        return self.personal_access_token


class CensysError(Exception):
    """An exception raised when an error occurs with the Censys API."""


class Censys(SearchEngine):
    """
    A class for interacting with the Censys Platform API.

    Parameters
    ----------
    credentials : CensysCredentials
        The credentials to use for the API.
    """

    PAGE_SIZE: ClassVar[int] = 100

    def __init__(self, credentials: CensysCredentials) -> None:
        self._credentials = credentials

        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {credentials.personal_access_token}"}
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def search(
        self,
        query: str,
        *,
        page_token: Optional[str] = None,
        page_size: int = PAGE_SIZE,
    ) -> Optional[Dict[str, Any]]:
        """
        Search the Censys Platform API for the given query.

        Parameters
        ----------
        query : str
            The Censys Query Language query to search for.
        page_token : Optional[str], optional
            The token of the page to retrieve, by default None.
        page_size : int, optional
            The number of results per page, by default PAGE_SIZE.
            The API caps this at 100.

        Returns
        -------
        Optional[Dict[str, Any]]
            The result object from Censys. Returns None if the query is invalid.
        """
        body: Dict[str, Any] = {"query": query, "page_size": page_size}
        params: Dict[str, str] = {}

        if page_token is not None:
            body["page_token"] = page_token

        if self._credentials.organization_id is not None:
            params["organization_id"] = self._credentials.organization_id

        async with self._session.post(
            "https://api.platform.censys.io/v3/global/search/query",
            json=body,
            params=params,
        ) as response:
            if response.status == 422:
                return None

            response_json = await response.json()

            if response.status != 200:
                raise CensysError(
                    response_json.get("detail")
                    or response_json.get("error")
                    or f"HTTP {response.status}"
                )

        return response_json.get("result")

    async def get_hosts(self, query: str, *, count: int = 100) -> List[Tuple[str, int]]:
        """
        Get hosts from Censys that match the given query.

        Parameters
        ----------
        query : str
            The Censys Query Language query to search for.
        count : int, optional
            The number of hosts to retrieve, by default 100.

        Returns
        -------
        List[Tuple[str, int]]
            The list of hosts.
        """
        hosts: Set[Tuple[str, int]] = set()
        page_token: Optional[str] = None

        while len(hosts) < count:
            result = await self.search(
                query,
                page_token=page_token,
                page_size=min(count - len(hosts), self.PAGE_SIZE),
            )

            if result is None:
                break

            for hit in result.get("hits") or []:
                host = hit.get("host_v1")

                if host is None:
                    continue

                ip_address = host["resource"].get("ip")

                if ip_address is None:
                    continue

                for service in host.get("matched_services") or []:
                    hosts.add((ip_address, service["port"]))

                    if len(hosts) == count:
                        return list(hosts)

            page_token = result.get("next_page_token")

            if not page_token:
                break

        return list(hosts)
