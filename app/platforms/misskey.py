from urllib.parse import quote

from app.domain import Message, Publication
from app.platforms.base import bearer, https_base, post, publication, require_config


class Misskey:
    name = "Misskey"

    def __init__(self, client, base_url, token):
        self.client = client
        self.base_url = base_url
        self.token = token

    async def publish(self, message: Message) -> Publication:
        require_config(MISSKEY_URL=self.base_url, MISSKEY_TOKEN=self.token)
        base_url = https_base(self.base_url)
        data = await post(
            self.client,
            f"{base_url}/api/notes/create",
            headers=bearer(self.token),
            json={"text": message.text, "visibility": "public", "localOnly": False},
        )
        note = data["createdNote"]
        return publication(
            f"{base_url}/notes/{quote(note['id'], safe='')}",
            note["visibility"] == "public",
            note["createdAt"],
        )
