from uuid import UUID

from app.repositories.post_repository import PostRepository
from app.search.search_repository import SearchRepository
from app.schemas.search import Post


class PostService:
    def __init__(
        self,
        posts: PostRepository,
        search: SearchRepository,
    ) -> None:
        self.posts = posts
        self.search = search

    async def search_posts(self, query: str) -> list[Post]:
        ids = await self.search.find_ids(query)
        rows = await self.posts.get_by_ids(ids)
        return [Post.model_validate(dict(row)) for row in rows]

    async def delete_post(self, post_id: UUID) -> bool:
        deleted = await self.posts.delete(post_id)
        if not deleted:
            return False
        await self.search.delete(post_id)
        return True
