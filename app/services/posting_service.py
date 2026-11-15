import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Sequence

from app.domain import Message, Publication, Publisher, PublishingError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Attempt:
    platform: str
    publication: Optional[Publication] = None
    error: Optional[str] = None


class PostingService:
    def __init__(self, publishers: Sequence[Publisher], deadline: float = 15):
        self.publishers = tuple(publishers)
        self.deadline = deadline

    async def publish(self, message: Message) -> list[Attempt]:
        return await asyncio.gather(
            *(self._attempt(publisher, message) for publisher in self.publishers)
        )

    async def _attempt(self, publisher: Publisher, message: Message) -> Attempt:
        try:
            published = await asyncio.wait_for(publisher.publish(message), self.deadline)
        except PublishingError as exc:
            return Attempt(publisher.name, error=str(exc))
        except asyncio.TimeoutError:
            return Attempt(publisher.name, error="Platform timed out. Publication could not be confirmed.")
        except Exception as exc:
            # Raw exception text can contain provider data or credentials.
            logger.warning("Publishing to %s failed (%s)", publisher.name, type(exc).__name__)
            return Attempt(publisher.name, error="Platform request failed or returned invalid data.")
        return Attempt(publisher.name, publication=published)
