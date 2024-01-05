"""A module for dataclasses used by the NetwaveDevice class."""
from dataclasses import dataclass
from typing import Optional, Tuple


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

    string: str
    encoding: str
    span: Tuple[int, int]
    is_interesting: bool

    def __str__(self) -> str:
        return self.string

    def __hash__(self) -> int:
        return hash(self.string)

    def __eq__(self, __value: object, /) -> bool:
        if isinstance(__value, ExtractedString):
            return self.string == __value.string

        if isinstance(__value, str):
            return self.string == __value

        return NotImplemented
