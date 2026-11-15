from app.domain import Message, Publication
from app.platforms.base import bearer, https_base, post, publication, require_config


class Mastodon:
    name = "Mastodon"

    def __init__(self, client, base_url, token):
        self.client = client
        self.base_url = base_url
        self.token = token

    async def publish(self, message: Message) -> Publication:
        require_config(MASTODON_URL=self.base_url, MASTODON_TOKEN=self.token)
        data = await post(
            self.client,
            f"{https_base(self.base_url)}/api/v1/statuses",
            headers=bearer(self.token),
            json={"status": message.text, "visibility": "public"},
        )
        return publication(data["url"], data["visibility"] == "public", data["created_at"])
