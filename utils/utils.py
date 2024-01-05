from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any, Coroutine, List, Optional, Set, Tuple

from pydantic import BaseModel, FilePath, PositiveInt, model_validator

logger = logging.getLogger(__name__)


class Args(BaseModel):
    """A class for representing the arguments passed to the program."""

    hosts: List[str]
    file: Optional[FilePath]
    key: Optional[str]
    output: Path
    pages: PositiveInt
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
        return cls(
            hosts=args.hosts,
            file=args.file,
            key=args.key,
            output=args.output,
            pages=args.pages,
            timeout=args.timeout,
            concurrent=args.concurrent,
        )

    @model_validator(mode="after")
    def validate_args(self) -> Args:
        """
        Ensure that a host, file, or ZoomEye API key was specified.

        Returns
        -------
        Args
            The Args instance.
        """
        if not self.hosts and all(value is None for value in (self.file, self.key)):
            raise ValueError("You must specify a host, file, or ZoomEye API key.")

        return self


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
        await self.close()

    async def close(self) -> None:
        """Cancel all pending tasks."""
        for task in self._tasks:
            task.cancel()

        self._tasks.clear()

    async def submit(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """
        Submit a coroutine to be executed

        Parameters
        ----------
        coro : Coroutine[Any, Any, Any]
            The coroutine to execute.

        Returns
        -------
        Any
            The return value of the coroutine.
        """
        async with self._semaphore:
            task = asyncio.create_task(coro)
            task.add_done_callback(self._tasks.remove)
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
