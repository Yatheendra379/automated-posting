from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request

from app.config import Settings
from app.schemas import PlatformResult, PostingRequest, PostingResponse
from app.services.posting_service import PostingService


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=10.0) as client:
        app.state.posting_service = Settings().posting_service(client)
        yield


app = FastAPI(title="Automated Multi-Platform Posting", lifespan=lifespan)


def get_service(request: Request) -> PostingService:
    return request.app.state.posting_service


@app.post("/posting", response_model=PostingResponse)
async def posting(body: PostingRequest, service: PostingService = Depends(get_service)):
    attempts = await service.publish(body.to_message())
    results = []
    for attempt in attempts:
        published = attempt.publication
        if published is None:
            results.append(PlatformResult(platform=attempt.platform, status="failed", error=attempt.error))
        else:
            results.append(PlatformResult(
                platform=attempt.platform,
                status="success",
                posted_url=published.url,
                public_access=published.public,
                date=published.posted_at.date(),
                time=published.posted_at.time().replace(microsecond=0),
            ))
    return PostingResponse(
        success=any(result.status == "success" for result in results), results=results
    )
