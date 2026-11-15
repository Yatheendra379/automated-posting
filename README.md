# Automated Multi-Platform Posting

A FastAPI service that takes a short announcement and publishes it concurrently to Mastodon, Bluesky, Misskey, GitHub Gist, and WordPress.

## Run locally

From the repository root with Python 3.9 or later:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Open [Swagger UI](http://localhost:4000/docs). The endpoint publishes using the accounts configured on the server. For local-only use, bind to `127.0.0.1`.

## Platform configuration

Fill in `.env` or export the same variables before starting Uvicorn. Configured instance URLs must use HTTPS.

| Platform | Configuration and permissions | Official API reference |
| --- | --- | --- |
| Mastodon | Set `MASTODON_URL` to the account's instance and `MASTODON_TOKEN` to a user access token with `write:statuses`. | [Create status](https://docs.joinmastodon.org/methods/statuses/#create) |
| Bluesky | Set `BLUESKY_IDENTIFIER` to the handle or DID and `BLUESKY_APP_PASSWORD` to an app password created in account settings. For a custom PDS, set `BLUESKY_PDS_URL`. | [Creating a post](https://docs.bsky.app/docs/tutorials/creating-a-post) |
| Misskey | Set `MISSKEY_URL` to the account's instance and `MISSKEY_TOKEN` to a token generated in Settings → API with `write:notes`. | [Authentication](https://misskey-hub.net/en/docs/for-developers/api/token/) · [Create note endpoint](https://github.com/misskey-dev/misskey/blob/develop/packages/backend/src/server/api/endpoints/notes/create.ts) |
| GitHub Gist | Set `GITHUB_GIST_TOKEN` to a token with Gists write permission or a classic token with the `gist` scope. | [Create a gist](https://docs.github.com/en/rest/gists/gists#create-a-gist) |
| WordPress | Set `WORDPRESS_URL` to a WordPress site's base URL and configure `WORDPRESS_USERNAME` and `WORDPRESS_APP_PASSWORD` for a user with permission to publish posts. | [Create a post](https://developer.wordpress.org/rest-api/reference/posts/#create-a-post) · [Application Passwords](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/#basic-authentication-with-application-passwords) |

Empty settings produce a per-platform configuration error. The service attempts all five destinations for every valid request.

## API

```sh
curl -sS http://localhost:4000/posting \
  -H 'Content-Type: application/json' \
  -d '{"message":"See our latest update at https://example.com/news"}'
```

The message must be at most 200 characters and include exactly one CTA with a fully qualified `http://` or `https://` URL. URL validation is syntactic. An invalid request returns HTTP 422 before any outbound calls.

A valid request returns HTTP 200 with one result per platform. The top-level `success` is true if at least one platform confirmed publication. Date and time are UTC. `public_access` reflects the provider's publication visibility or record type. Instance access controls, moderation, and indexing delays can affect what anonymous visitors see.

Example results excerpt from a mixed outcome (illustrative URLs):

```json
{
  "success": true,
  "results": [
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.example/@demo/1",
      "public_access": true,
      "date": "2026-11-15",
      "time": "10:30:00",
      "error": null
    },
    {
      "platform": "GitHub Gist",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Rate limit exceeded (HTTP 429)."
    }
  ]
}
```

## Architecture

- `app/main.py` and `app/schemas.py` define the HTTP boundary and JSON contract.
- `app/domain.py` defines the parsed message, publication, and publisher interface.
- `app/services/posting_service.py` runs publishers concurrently through the domain interface and applies a deadline per platform.
- `app/platforms/` holds the provider-specific API adapters. `app/config.py` reads environment settings and wires the adapters into the service.

The service makes one publication attempt per destination for each request. A timeout can occur after a provider accepts a post, so verify the account before manually retrying.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The integration tests use HTTPX's mock transport to check the five providers' outbound requests, partial failure, and response mapping. See [verification log](verification.log) for test output and a local Uvicorn smoke test. Live posting requires credentials for the selected accounts.
