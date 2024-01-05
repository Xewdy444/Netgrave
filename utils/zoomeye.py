"""A module for interacting with the ZoomEye API."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


class ZoomEye:
    """
    A class for interacting with the ZoomEye API.

    Parameters
    ----------
    api_key : str
        The ZoomEye API key to use.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

        self._session = aiohttp.ClientSession()
        self._session.headers["API-KEY"] = api_key

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(api_key={self._api_key!r})"

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
        page : int
            The page to search on, by default 1.

        Returns
        -------
        Optional[Dict[str, Any]]
            The response from ZoomEye. Returns None if the page was not found.
        """
        async with self._session.get(
            "https://api.zoomeye.org/host/search", params={"query": query, "page": page}
        ) as response:
            if response.status == 403:
                return None

            return await response.json()

    async def get_hosts(self, query: str, *, pages: int = 1) -> List[Tuple[str, int]]:
        """
        Get hosts from ZoomEye.

        Parameters
        ----------
        query : str
            The query to search for.
        pages : int
            The number of pages to search, by default 1.
        """
        tasks = [
            asyncio.create_task(self.search(query, page=page))
            for page in range(1, pages + 1)
        ]

        results = await asyncio.gather(*tasks)
        hosts = set()

        for result in results:
            if result is None:
                continue

            for host in result["matches"]:
                hosts.add((host["ip"], host["portinfo"]["port"]))

        return list(hosts)
