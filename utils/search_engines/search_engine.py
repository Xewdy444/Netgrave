"""The base class for interacting with an IoT search engine."""

import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class SearchEngine(ABC):
    """The base class for interacting with an IoT search engine."""

    _session: aiohttp.ClientSession

    async def __aenter__(self) -> Self:
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
    async def get_hosts(self, query: str, *, count: int) -> List[Tuple[str, int]]:
        """
        Get hosts that match the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        count : int
            The number of hosts to retrieve.

        Returns
        -------
        List[Tuple[str, int]]
            The hosts that match the query.
        """
