from html import escape

from app.domain import Message, Publication, PublishingError
from app.platforms.base import https_base, post, publication, require_config


class WordPress:
    name = "WordPress"

    def __init__(self, client, base_url, username, app_password):
        self.client = client
        self.base_url = base_url
        self.username = username
        self.app_password = app_password

    async def publish(self, message: Message) -> Publication:
        require_config(
            WORDPRESS_URL=self.base_url, WORDPRESS_USERNAME=self.username,
            WORDPRESS_APP_PASSWORD=self.app_password,
        )
        url = escape(message.url)
        content = (
            f"{escape(message.text[:message.start])}<a href=\"{url}\">{url}</a>"
            f"{escape(message.text[message.end:])}"
        )
        data = await post(
            self.client, f"{https_base(self.base_url)}/wp-json/wp/v2/posts",
            auth=(self.username, self.app_password),
            json={"title": "Announcement", "content": f"<p>{content}</p>", "status": "publish"},
        )
        if data["status"] != "publish":
            raise PublishingError("WordPress did not publish the post.")
        return publication(data["link"], not data.get("password"), data["date_gmt"])
