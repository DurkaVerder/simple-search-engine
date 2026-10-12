import asyncpg
from elasticsearch import AsyncElasticsearch

from app.repositories.post_repository import PostRepository
from app.search.search_repository import SearchRepository
from app.settings import ELASTICSEARCH_INDEX


async def initialize_storage(
    pool: asyncpg.Pool, elastic: AsyncElasticsearch
) -> None:
    await PostRepository(pool).create_schema()
    await SearchRepository(elastic, ELASTICSEARCH_INDEX).create_index()
