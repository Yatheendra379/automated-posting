import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_service

TIMESTAMP = "2026-11-15T10:30:00Z"


@pytest.mark.parametrize("body", [
    {"message": "a" * 200 + " https://example.com"},
    {"message": "No link here"},
    {"message": "Two links https://example.com http://example.org"},
    {"message": "Invalid https://"},
    {"message": "Invalid https://-example.com"},
    {"message": "Invalid https://example.com:99999"},
    {"message": "Invalid https://user:secret@example.com"},
    {"message": "Invalid https://example.com/%xx"},
    {"message": "Unsupported ftp://example.com"},
    {"message": "Check https://example.com", "platform": "Mastodon"},
    {"message": 100},
    {},
])
def test_validation_before_posting(body):
    def unexpected_service_call():
        pytest.fail("Invalid input must never publish")

    # Dependencies are resolved before model validation. Return a service
    # whose publish method fails the test if validation lets the request through.
    class Service:
        async def publish(self, message):
            unexpected_service_call()

    app.dependency_overrides[get_service] = Service
    try:
        assert TestClient(app).post("/posting", json=body).status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("gist_status", [201, 429])
def test_vendor_requests_and_results(gist_status):
    message = "✨ <Update> (https://example.com/news?a=1&b=2)."
    requests = {}

    def vendor(request):
        payload = json.loads(request.content)
        requests[request.url.path] = (request, payload)
        path = request.url.path
        if path == "/api/v1/statuses":
            assert payload == {"status": message, "visibility": "public"}
            return httpx.Response(200, json={
                "url": "https://mastodon.example/@demo/1",
                "visibility": "public", "created_at": TIMESTAMP,
            })
        if path.endswith("createSession"):
            assert payload == {"identifier": "demo.bsky.social", "password": "test-app-password"}
            return httpx.Response(200, json={"accessJwt": "test-jwt", "did": "did:plc:demo"})
        if path.endswith("createRecord"):
            assert request.headers["authorization"] == "Bearer test-jwt"
            assert payload["repo"] == "did:plc:demo"
            assert payload["collection"] == "app.bsky.feed.post"
            record = payload["record"]
            assert record["text"] == message
            facet = record["facets"][0]
            start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
            assert message.encode()[start:end].decode() == facet["features"][0]["uri"]
            assert facet["features"][0]["uri"] == "https://example.com/news?a=1&b=2"
            return httpx.Response(200, json={"uri": "at://did:plc:demo/app.bsky.feed.post/xyz"})
        if path == "/api/notes/create":
            assert payload == {"text": message, "visibility": "public", "localOnly": False}
            return httpx.Response(200, json={"createdNote": {
                "id": "123", "visibility": "public", "createdAt": TIMESTAMP,
            }})
        if path == "/gists":
            assert payload == {"public": True, "files": {"message.txt": {"content": message}}}
            if gist_status == 429:
                return httpx.Response(429, json={"error": "private diagnostic"})
            return httpx.Response(201, json={
                "html_url": "https://gist.github.com/demo/1", "public": True,
                "created_at": TIMESTAMP,
            })
        if path == "/wp-json/wp/v2/posts":
            assert request.headers["authorization"].startswith("Basic ")
            assert payload["status"] == "publish"
            assert "&lt;Update&gt;" in payload["content"]
            assert 'href="https://example.com/news?a=1&amp;b=2"' in payload["content"]
            return httpx.Response(201, json={
                "link": "https://wordpress.example/announcement", "status": "publish",
                "date_gmt": "2026-11-15T10:30:00",
            })
        pytest.fail(f"Unexpected outbound path {path}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(vendor))
    settings = Settings(
        _env_file=None,
        mastodon_url="https://mastodon.example", mastodon_token="test-token",
        bluesky_identifier="demo.bsky.social", bluesky_app_password="test-app-password",
        misskey_url="https://misskey.example", misskey_token="test-token",
        github_gist_token="test-token", wordpress_url="https://wordpress.example",
        wordpress_username="demo", wordpress_app_password="test-app-password",
    )

    async def get_mock_service():
        async with client:
            yield settings.posting_service(client)

    app.dependency_overrides[get_service] = get_mock_service
    try:
        response = TestClient(app).post("/posting", json={"message": message})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is True
    results = {item["platform"]: item for item in response.json()["results"]}
    assert len(requests) == 6
    assert len(results) == 5
    assert results["Bluesky"]["posted_url"] == "https://bsky.app/profile/did:plc:demo/post/xyz"
    assert results["Misskey"]["posted_url"] == "https://misskey.example/notes/123"
    assert results["WordPress"]["date"] == "2026-11-15"
    assert results["Mastodon"]["time"] == "10:30:00"

    if gist_status == 429:
        assert results["GitHub Gist"] == {
            "platform": "GitHub Gist", "status": "failed", "posted_url": None,
            "public_access": False, "date": None, "time": None,
            "error": "Rate limit exceeded (HTTP 429).",
        }
    assert sum(item["public_access"] for item in results.values()) == (5 if gist_status == 201 else 4)


def test_all_unconfigured():
    settings = Settings(
        _env_file=None,
        mastodon_token="", bluesky_app_password="", misskey_token="",
        github_gist_token="", wordpress_app_password="",
    )
    app.dependency_overrides[get_service] = lambda: settings.posting_service(None)
    try:
        message = "a" * 180 + " https://example.com"
        assert len(message) == 200
        response = TestClient(app).post("/posting", json={"message": message})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is False
    results = response.json()["results"]
    assert len(results) == 5
    assert all(item["status"] == "failed" and "Missing configuration" in item["error"] for item in results)


def test_timeout_does_not_interrupt_other_platforms():
    import asyncio
    from datetime import datetime, timezone

    from app.domain import Publication, parse_message
    from app.services.posting_service import PostingService

    class SlowPublisher:
        name = "Slow"

        async def publish(self, message):
            await asyncio.sleep(1)

    class WorkingPublisher:
        name = "Working"

        async def publish(self, message):
            return Publication("https://example.com/post", True, datetime.now(timezone.utc))

    service = PostingService([SlowPublisher(), WorkingPublisher()], deadline=0.02)
    slow, working = asyncio.run(service.publish(parse_message("See https://example.com")))
    assert "timed out" in slow.error
    assert working.publication.url == "https://example.com/post"
