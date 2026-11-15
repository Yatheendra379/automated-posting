import re
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv6Address
from typing import Protocol
from urllib.parse import urlsplit

# A CTA must use an explicit scheme. Count all explicit URI candidates.
LINK = re.compile(r"""[a-z][a-z0-9+.-]*://[^\s<>"\x00-\x1f]*""", re.IGNORECASE)
DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")


@dataclass(frozen=True)
class Message:
    text: str
    url: str
    start: int
    end: int


def parse_message(text: str) -> Message:
    matches = list(LINK.finditer(text))
    if len(matches) != 1:
        raise ValueError("Include exactly one CTA URL with an explicit HTTP(S) scheme.")

    match = matches[0]
    url = match.group().rstrip(".,!?;:'")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while url.endswith(closing) and url.count(closing) > url.count(opening):
            url = url[:-1]
    try:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        port = parts.port
        if ":" in hostname:

            IPv6Address(hostname)
        else:
            ascii_host = hostname.rstrip(".").encode("idna").decode("ascii")
            if len(ascii_host) > 253 or not all(
                DOMAIN_LABEL.fullmatch(label) for label in ascii_host.split(".")
            ):
                raise ValueError
        if (
            parts.scheme not in {"http", "https"}
            or parts.username is not None
            or port == 0
            or parts.netloc.endswith(":")
            or "\\" in url
            or BAD_ESCAPE.search(url)
        ):
            raise ValueError
    except ValueError:
        raise ValueError("The CTA must be a valid HTTP(S) URL without credentials.") from None

    return Message(text, url, match.start(), match.start() + len(url))


@dataclass(frozen=True)
class Publication:
    url: str
    public: bool
    posted_at: datetime


class PublishingError(Exception):
    """A safe error message that may be returned to a caller."""


class Publisher(Protocol):
    name: str

    async def publish(self, message: Message) -> Publication:
        ...
