from app.domain import Message, Publication
from app.platforms.base import bearer, post, publication, require_config


class GitHubGist:
    name = "GitHub Gist"

    def __init__(self, client, token):
        self.client = client
        self.token = token

    async def publish(self, message: Message) -> Publication:
        require_config(GITHUB_GIST_TOKEN=self.token)
        data = await post(
            self.client, "https://api.github.com/gists",
            headers={**bearer(self.token), "Accept": "application/vnd.github+json"},
            json={
                "public": True,
                "files": {"message.txt": {"content": message.text}},
            },
        )
        return publication(data["html_url"], data["public"] is True, data["created_at"])
