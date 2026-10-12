from fastapi import APIRouter

router = APIRouter(prefix="/posts", tags=["posts"])




@router.delete("/{post_id}")
async def delete_posts(post_id: str):
    return {"message": f"Delete post with ID {post_id}"}