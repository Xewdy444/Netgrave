"""A module for interacting with the ZoomEye API."""

import base64
import logging
import math
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

import aiohttp

from .search_engine import SearchEngine

logger = logging.getLogger(__name__)


@dataclass
class ZoomEyeCredentials:
    """A class for representing ZoomEye credentials."""

    api_key: str

    def __str__(self) -> str:
        return self.api_key


class ZoomEyeError(Exception):
    """An exception raised when an error occurs with the ZoomEye API."""


class ZoomEye(SearchEngine):
    """
    A class for interacting with the ZoomEye API.

    Parameters
    ----------
    credentials : ZoomEyeCredentials
        The credentials to use for the API.
    """

    PAGE_SIZE: ClassVar[int] = 1000

    def __init__(self, credentials: ZoomEyeCredentials) -> None:
        self._credentials = credentials

        self._session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 "
                "Safari/537.36",
                "API-KEY": str(credentials),
            }
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(credentials={self._credentials!r})"

    async def search(
        self, query: str, *, page: int = 1, page_size: int = PAGE_SIZE
    ) -> Optional[Dict[str, Any]]:
        """
        Search the ZoomEye API for the given query.

        Parameters
        ----------
        query : str
            The query to search for.
        page : int, optional
            The page to search on, by default 1.
        page_size : int, optional
            The number of results per page, by default PAGE_SIZE.

        Returns
        -------
        Optional[Dict[str, Any]]
            The response from ZoomEye. Returns None if the account
            has run out of resource credits.
        """
        async with self._session.post(
            "https://api.zoomeye.ai/v2/search",
            json={
                "qbase64": base64.b64encode(query.encode()).decode(),
                "page": page,
                "pagesize": page_size,
            },
        ) as response:
            if response.status == 402:
                logger.warning("ZoomEye resource credits are insufficient.")
                return None

            response_json = await response.json()

            if response_json.get("code") != 60000:
                raise ZoomEyeError(
                    response_json.get("message") or f"HTTP {response.status}"
                )

        return response_json

    async def get_hosts(self, query: str, *, count: int = 100) -> List[Tuple[str, int]]:
        """
        Get hosts from ZoomEye that match the given query.

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
        hosts: Set[Tuple[str, int]] = set()
        page_size = max(min(count, self.PAGE_SIZE), 1)

        for page in range(1, math.ceil(count / page_size) + 1):
            result = await self.search(query, page=page, page_size=page_size)

            if result is None or not result["data"]:
                break

            for host in result["data"]:
                hosts.add((host["ip"], host["port"]))

                if len(hosts) == count:
                    return list(hosts)

        return list(hosts)
