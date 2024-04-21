"""The base class for interacting with an IoT search engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


class SearchEngine(ABC):
    """The base class for interacting with an IoT search engine."""

    _session: aiohttp.ClientSession

    async def __aenter__(self) -> SearchEngine:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        await self._session.close()

    @abstractmethod
    async def search(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search the API for the given query.

        Parameters
        ----------
        query : str
            The query to search for.

        Returns
        -------
        Optional[Dict[str, Any]]
            The results of the search.
        """

    @abstractmethod
    async def get_hosts(self, query: str, *, count: int = 500) -> List[Tuple[str, int]]:
        """
        Get hosts that match the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        count : int, optional
            The number of hosts to retrieve, by default 500.

        Returns
        -------
        List[Tuple[str, int]]
            The hosts that match the query.
        """
