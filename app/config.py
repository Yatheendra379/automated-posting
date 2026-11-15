import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.platforms.bluesky import Bluesky
from app.platforms.github import GitHubGist
from app.platforms.mastodon import Mastodon
from app.platforms.misskey import Misskey
from app.platforms.wordpress import WordPress
from app.services.posting_service import PostingService


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    mastodon_url: str = ""
    mastodon_token: str = ""
    bluesky_pds_url: str = "https://bsky.social"
    bluesky_identifier: str = ""
    bluesky_app_password: str = ""
    misskey_url: str = ""
    misskey_token: str = ""
    github_gist_token: str = ""
    wordpress_url: str = ""
    wordpress_username: str = ""
    wordpress_app_password: str = ""

    def posting_service(self, client: httpx.AsyncClient) -> PostingService:
        return PostingService([
            Mastodon(client, self.mastodon_url, self.mastodon_token),
            Bluesky(client, self.bluesky_pds_url, self.bluesky_identifier, self.bluesky_app_password),
            Misskey(client, self.misskey_url, self.misskey_token),
            GitHubGist(client, self.github_gist_token),
            WordPress(client, self.wordpress_url, self.wordpress_username, self.wordpress_app_password),
        ])
