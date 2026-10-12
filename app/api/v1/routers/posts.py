from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.services.post_service import PostService

router = APIRouter(prefix="/posts", tags=["posts"])


def get_service(request: Request) -> PostService:
    return request.app.state.post_service


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    service: PostService = Depends(get_service),
) -> None:
    if not await service.delete_post(post_id):
        raise HTTPException(status_code=404, detail="Post not found")
