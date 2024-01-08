"""A module for interacting with the Censys API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


@dataclass
class CensysCredentials:
    """A class for representing Censys credentials."""

    api_id: str
    secret: str


class Censys:
    """
    A class for interacting with the Censys API.

    Parameters
    ----------
    credentials : CensysCredentials
        The credentials to use for the API.
    """

    def __init__(self, credentials: CensysCredentials) -> None:
        self._credentials = credentials

        self._session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(credentials.api_id, credentials.secret)
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def __aenter__(self) -> Censys:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        await self._session.close()

    async def search(
        self, query: str, *, cursor: Optional[str] = None, per_page: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        Search Censys for the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        cursor : Optional[str], optional
            The cursor token to use, by default None.
        per_page : int, optional
            The number of results per page, by default 100.

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

            return await response.json()

    async def get_hosts(self, query: str, *, count: int = 500) -> List[Tuple[str, int]]:
        """
        Get hosts from Censys.

        Parameters
        ----------
        query : str
            The query to search for.
        count : int, optional
            The number of hosts to retrieve, by default 500.

        Returns
        -------
        List[Tuple[str, int]]
            The list of hosts.
        """
        if count < 1:
            raise ValueError("Count must be at least 1.")

        hosts = set()
        cursor = None

        while len(hosts) < count:
            per_page = min(count - len(hosts), 100)
            response = await self.search(query, cursor=cursor, per_page=per_page)

            if response is None:
                break

            for host in response["result"]["hits"]:
                for service in host["services"]:
                    hosts.add((host["ip"], service["port"]))

                    if len(hosts) == count:
                        return list(hosts)

            cursor = response["result"]["links"]["next"]

            if not cursor:
                break

        return list(hosts)
