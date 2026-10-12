from fastapi import APIRouter, Depends, Query, Request

from app.schemas.search import Post
from app.services.post_service import PostService

router = APIRouter(prefix="/search", tags=["search"])


def get_service(request: Request) -> PostService:
    return request.app.state.post_service


@router.get("", response_model=list[Post])
async def search(
    q: str = Query(min_length=1, description="Text to search in documents"),
    service: PostService = Depends(get_service),
) -> list[Post]:
    return await service.search_posts(q)
