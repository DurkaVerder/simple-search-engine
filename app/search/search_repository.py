import asyncio
from collections.abc import Iterable
from uuid import UUID

from elastic_transport import ConnectionError as ElasticConnectionError
from elastic_transport import ConnectionTimeout
from elasticsearch import AsyncElasticsearch, helpers


class SearchRepository:

    def __init__(self, client: AsyncElasticsearch, index: str) -> None:
        self.client = client
        self.index = index

    async def create_index(self) -> None:
        await self.client.indices.create(
            index=self.index,
            mappings={
                "properties": {
                    "id": {"type": "keyword"},
                    "text": {"type": "text"},
                }
            },
            ignore=400,
        )

    async def find_ids(self, query: str, limit: int = 20) -> list[UUID]:
        result = await self.client.search(
            index=self.index,
            size=limit,
            query={"match": {"text": {"query": query}}},
            _source=["id"],
        )
        return [UUID(hit["_source"]["id"]) for hit in result["hits"]["hits"]]

    async def index_many(self, posts: Iterable[dict]) -> None:
        await helpers.async_bulk(
            self.client,
            (
                {
                    "_op_type": "index",
                    "_index": self.index,
                    "_id": str(post["id"]),
                    "_source": {
                        "id": str(post["id"]),
                        "text": post["text"],
                    },
                }
                for post in posts
            ),
        )

    async def delete(self, post_id: UUID) -> None:
        for attempt in range(4):
            try:
                await self.client.delete(
                    index=self.index,
                    id=str(post_id),
                    ignore=[404],
                )
                return
            except (ElasticConnectionError, ConnectionTimeout):
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)

    async def refresh(self) -> None:
        await self.client.indices.refresh(index=self.index)
