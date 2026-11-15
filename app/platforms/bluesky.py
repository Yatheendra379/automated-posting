from datetime import datetime, timezone
from urllib.parse import quote

from app.domain import Message, Publication, PublishingError
from app.platforms.base import bearer, https_base, post, publication, require_config


class Bluesky:
    name = "Bluesky"

    def __init__(self, client, pds_url, identifier, app_password):
        self.client = client
        self.pds_url = pds_url
        self.identifier = identifier
        self.app_password = app_password

    async def publish(self, message: Message) -> Publication:
        require_config(
            BLUESKY_IDENTIFIER=self.identifier, BLUESKY_APP_PASSWORD=self.app_password
        )
        xrpc = f"{https_base(self.pds_url)}/xrpc"
        session = await post(
            self.client, f"{xrpc}/com.atproto.server.createSession",
            json={"identifier": self.identifier, "password": self.app_password},
        )
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        collection = "app.bsky.feed.post"
        record = await post(
            self.client, f"{xrpc}/com.atproto.repo.createRecord",
            headers=bearer(session["accessJwt"]),
            json={
                "repo": session["did"],
                "collection": collection,
                "record": {
                    "$type": collection,
                    "text": message.text,
                    "createdAt": created_at,
                    "facets": [{
                        "index": {
                            "byteStart": len(message.text[:message.start].encode("utf-8")),
                            "byteEnd": len(message.text[:message.end].encode("utf-8")),
                        },
                        "features": [{
                            "$type": "app.bsky.richtext.facet#link",
                            "uri": message.url,
                        }],
                    }],
                },
            },
        )
        prefix = f"at://{session['did']}/{collection}/"
        uri = record["uri"]
        if not uri.startswith(prefix) or not uri[len(prefix):]:
            raise PublishingError("Bluesky returned an unexpected record URI.")
        did = quote(session["did"], safe=":")
        key = quote(uri[len(prefix):], safe="")
        return publication(f"https://bsky.app/profile/{did}/post/{key}", True, created_at)
