"""A module for interacting with the ZoomEye API."""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp


@dataclass
class ZoomEyeCredentials:
    """A class for representing ZoomEye credentials."""

    api_key: str


class ZoomEyeError(Exception):
    """An exception raised when an error occurs with the ZoomEye API."""


class ZoomEye:
    """
    A class for interacting with the ZoomEye API.

    Parameters
    ----------
    credentials : ZoomEyeCredentials
        The credentials to use for the API.
    """

    def __init__(self, credentials: ZoomEyeCredentials) -> None:
        self._credentials = credentials

        self._session = aiohttp.ClientSession()
        self._session.headers["API-KEY"] = credentials.api_key

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def __aenter__(self) -> ZoomEye:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        await self._session.close()

    async def search(self, query: str, *, page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Search ZoomEye for the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        page : int, optional
            The page to search on, by default 1.

        Returns
        -------
        Optional[Dict[str, Any]]
            The response from ZoomEye. Returns None if the page was not found.
        """
        async with self._session.get(
            "https://api.zoomeye.org/host/search",
            params={"query": query, "page": page},
        ) as response:
            if response.status == 403:
                return None

            response_json = await response.json()

        if "error" in response_json:
            raise ZoomEyeError(response_json["error"])

        return response_json

    async def get_hosts(self, query: str, *, count: int = 500) -> List[Tuple[str, int]]:
        """
        Get hosts from ZoomEye.

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
        tasks = [
            asyncio.create_task(self.search(query, page=page))
            for page in range(1, math.ceil(count / 20) + 1)
        ]

        results = await asyncio.gather(*tasks)
        hosts: Set[Tuple[str, int]] = set()

        for result in results:
            if result is None:
                continue

            for host in result["matches"]:
                hosts.add((host["ip"], host["portinfo"]["port"]))

                if len(hosts) == count:
                    return list(hosts)

        return list(hosts)
