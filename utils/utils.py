"""Utility functions and classes."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Coroutine, Iterable, List, Optional, Set, Tuple, TypeVar

from pydantic import BaseModel, FilePath, PositiveInt

from .search_engines import CensysCredentials, ShodanCredentials, ZoomEyeCredentials

T = TypeVar("T")

logger = logging.getLogger(__name__)


class Args(BaseModel):
    """A class for representing the arguments passed to the program."""

    hosts: List[str]
    file: Optional[FilePath]
    censys: Optional[CensysCredentials]
    shodan: Optional[ShodanCredentials]
    zoomeye: Optional[ZoomEyeCredentials]
    output: Path
    number: PositiveInt
    timeout: PositiveInt
    concurrent: PositiveInt

    @classmethod
    def from_namespace(cls, namespace: argparse.Namespace) -> Args:
        """
        Create an instance of Args from an argparse namespace.

        Parameters
        ----------
        namespace : argparse.Namespace
            The namespace to create the Args instance from.

        Returns
        -------
        Args
            The Args instance.
        """
        new_args = {
            "hosts": namespace.hosts,
            "file": namespace.file,
            "censys": None,
            "shodan": None,
            "zoomeye": None,
            "output": namespace.output,
            "number": namespace.number,
            "timeout": namespace.timeout,
            "concurrent": namespace.concurrent,
        }

        if namespace.censys:
            censys_api_id = os.getenv("CENSYS_API_ID")
            censys_api_secret = os.getenv("CENSYS_API_SECRET")

            if censys_api_id is None or censys_api_secret is None:
                raise ValueError(
                    "You must set the CENSYS_API_ID and CENSYS_API_SECRET "
                    "environment variables."
                )

            new_args["censys"] = CensysCredentials(censys_api_id, censys_api_secret)

        if namespace.shodan:
            shodan_api_key = os.getenv("SHODAN_API_KEY")

            if shodan_api_key is None:
                raise ValueError(
                    "You must set the SHODAN_API_KEY environment variable."
                )

            new_args["shodan"] = ShodanCredentials(shodan_api_key)

        if namespace.zoomeye:
            zoomeye_api_key = os.getenv("ZOOMEYE_API_KEY")

            if zoomeye_api_key is None:
                raise ValueError(
                    "You must set the ZOOMEYE_API_KEY environment variable."
                )

            new_args["zoomeye"] = ZoomEyeCredentials(zoomeye_api_key)

        return cls(**new_args)


class CoroutineExecutor:
    """
    A class for executing coroutines with a maximum number of concurrent tasks.

    Parameters
    ----------
    max_tasks : int
        The maximum number of concurrent tasks.
    """

    def __init__(self, max_tasks: int) -> None:
        self._max_tasks = max_tasks
        self._semaphore = asyncio.Semaphore(max_tasks)
        self._tasks: Set[asyncio.Task[Any]] = set()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_tasks={self._max_tasks!r})"

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self) -> Iterable[asyncio.Task[Any]]:
        yield from self._tasks

    async def __aenter__(self) -> CoroutineExecutor:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()

    async def _execute(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Execute a coroutine with a semaphore.

        Parameters
        ----------
        coro : Coroutine[Any, Any, T]
            The coroutine to execute.

        Returns
        -------
        T
            The result of the coroutine.
        """
        async with self._semaphore:
            return await coro

    def close(self) -> None:
        """Cancel all pending tasks."""
        for task in self._tasks:
            task.cancel()

        self._tasks.clear()

    def submit(self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        """
        Submit a coroutine to be executed.

        Parameters
        ----------
        coro : Coroutine[Any, Any, T]
            The coroutine to execute.

        Returns
        -------
        asyncio.Task[T]
            The task that will execute the coroutine.
        """
        task = asyncio.create_task(self._execute(coro))
        self._tasks.add(task)
        return task

    async def gather(self) -> List[Any]:
        """
        Gather the results of all pending tasks.

        Returns
        -------
        List[Any]
            The results of all pending tasks.
        """
        return await asyncio.gather(*self._tasks)


def format_hosts(hosts: List[str]) -> List[Tuple[str, int]]:
    """
    Format a list of hosts into a list of tuples containing the host and port.

    Parameters
    ----------
    hosts : List[str]
        The hosts to format.

    Returns
    -------
    List[Tuple[str, int]]
        The formatted hosts.
    """
    formatted_hosts: Set[Tuple[str, int]] = set()

    for host in hosts:
        try:
            host, port = host.split(":")
            formatted_hosts.add((host, int(port)))
        except ValueError:
            logger.warning("Invalid host: %s", host)

    return list(formatted_hosts)
