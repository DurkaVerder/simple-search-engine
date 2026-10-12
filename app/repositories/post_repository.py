from collections.abc import Sequence
from uuid import UUID

import asyncpg


class PostRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_schema(self) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id UUID PRIMARY KEY,
                    rubrics TEXT[] NOT NULL DEFAULT '{}',
                    text TEXT NOT NULL,
                    created_date TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS posts_created_date_idx
                    ON posts (created_date DESC);
                """
            )

    async def upsert_many(self, posts: Sequence[dict]) -> None:
        async with self.pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO posts (id, rubrics, text, created_date)
                VALUES ($1, $2::text[], $3, $4)
                ON CONFLICT (id) DO UPDATE SET
                    rubrics = EXCLUDED.rubrics,
                    text = EXCLUDED.text,
                    created_date = EXCLUDED.created_date
                """,
                [
                    (post["id"], post["rubrics"], post["text"], post["created_date"])
                    for post in posts
                ],
            )

    async def get_by_ids(self, post_ids: Sequence[UUID]) -> list[asyncpg.Record]:
        if not post_ids:
            return []
        return await self.pool.fetch(
            """
            SELECT id, rubrics, text, created_date
            FROM posts
            WHERE id = ANY($1::uuid[])
            ORDER BY created_date DESC
            LIMIT 20
            """,
            post_ids,
        )

    async def delete(self, post_id: UUID) -> bool:
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM posts WHERE id = $1",
                post_id,
            )
        return result == "DELETE 1"
