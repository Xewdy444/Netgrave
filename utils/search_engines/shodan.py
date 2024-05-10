"""A module for interacting with the Shodan API."""

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp

from .search_engine import SearchEngine

PAGE_SIZE = 100


@dataclass
class ShodanCredentials:
    """A class for representing Shodan credentials."""

    api_key: str


class ShodanError(Exception):
    """An exception raised when an error occurs with the Shodan API."""


class Shodan(SearchEngine):
    """
    A class for interacting with the Shodan API.

    Parameters
    ----------
    credentials : ShodanCredentials
        The credentials to use for the API.
    """

    def __init__(self, credentials: ShodanCredentials) -> None:
        self._credentials = credentials
        self._session = aiohttp.ClientSession()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def search(self, query: str, *, page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Search the Shodan API for the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        page : int, optional
            The page to search on, by default 1.

        Returns
        -------
        Optional[Dict[str, Any]]
            The response from Shodan. Returns None if the page was not found.
        """
        async with self._session.get(
            "https://api.shodan.io/shodan/host/search",
            params={"key": self._credentials.api_key, "query": query, "page": page},
        ) as response:
            if response.status == 400:
                return None

            response_json = await response.json()

        if "error" in response_json:
            raise ShodanError(response_json["error"])

        return response_json

    async def get_hosts(self, query: str, *, count: int = 100) -> List[Tuple[str, int]]:
        """
        Get hosts from Shodan that match the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        count : int, optional
            The number of hosts to retrieve, by default 100.

        Returns
        -------
        List[Tuple[str, int]]
            The list of hosts.
        """
        tasks = [
            asyncio.create_task(self.search(query, page=page))
            for page in range(1, math.ceil(count / PAGE_SIZE) + 1)
        ]

        results = await asyncio.gather(*tasks)
        hosts: Set[Tuple[str, int]] = set()

        for result in results:
            if result is None:
                continue

            for host in result["matches"]:
                hosts.add((host["ip_str"], host["port"]))

                if len(hosts) == count:
                    return list(hosts)

        return list(hosts)
