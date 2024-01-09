"""Utility functions and classes."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Coroutine, List, Optional, Set, Tuple, TypeVar

from pydantic import BaseModel, FilePath, PositiveInt

from .censys import CensysCredentials
from .zoomeye import ZoomEyeCredentials

T = TypeVar("T")

logger = logging.getLogger(__name__)


class Args(BaseModel):
    """A class for representing the arguments passed to the program."""

    hosts: List[str]
    file: Optional[FilePath]
    censys: Optional[CensysCredentials]
    zoomeye: Optional[ZoomEyeCredentials]
    output: Path
    number: PositiveInt
    timeout: PositiveInt
    concurrent: PositiveInt

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Args:
        """
        Create an Args instance from the given arguments.

        Parameters
        ----------
        args : argparse.Namespace
            The arguments to create an Args instance from.

        Returns
        -------
        Args
            The Args instance.
        """
        new_args = {
            "hosts": args.hosts,
            "file": args.file,
            "censys": None,
            "zoomeye": None,
            "output": args.output,
            "number": args.number,
            "timeout": args.timeout,
            "concurrent": args.concurrent,
        }

        if args.censys:
            censys_api_id = os.getenv("CENSYS_API_ID")
            CENSYS_API_SECRET = os.getenv("CENSYS_API_SECRET")

            if censys_api_id is None or CENSYS_API_SECRET is None:
                raise ValueError(
                    "You must set the CENSYS_API_ID and CENSYS_API_SECRET "
                    "environment variables."
                )

            new_args["censys"] = CensysCredentials(censys_api_id, CENSYS_API_SECRET)

        if args.zoomeye:
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
        self._tasks: Set[asyncio.Task] = set()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_tasks={self._max_tasks!r})"

    def __len__(self) -> int:
        return len(self._tasks)

    async def __aenter__(self) -> CoroutineExecutor:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Cancel all pending tasks."""
        for task in self._tasks:
            task.cancel()

        self._tasks.clear()

    async def submit(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Submit a coroutine to be executed.

        Parameters
        ----------
        coro : Coroutine[Any, Any, T]
            The coroutine to execute.

        Returns
        -------
        T
            The return value of the coroutine.
        """
        async with self._semaphore:
            task = asyncio.create_task(coro)
            task.add_done_callback(self._tasks.discard)
            self._tasks.add(task)
            return await task


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
    formatted_hosts = []

    for host in hosts:
        try:
            host, port = host.split(":")
            formatted_hosts.append((host, int(port)))
        except ValueError:
            logger.warning("Invalid host: %s", host)

    return formatted_hosts
