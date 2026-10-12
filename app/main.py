from contextlib import asynccontextmanager

import asyncpg
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI

from app.api.v1.routers.posts import router as posts_router
from app.api.v1.routers.search import router as search_router
from app.db import initialize_storage
from app.repositories.post_repository import PostRepository
from app.search.search_repository import SearchRepository
from app.services.post_service import PostService
from app.settings import ELASTICSEARCH_INDEX, ELASTICSEARCH_URL, POSTGRES_DSN


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=10)
    elastic = AsyncElasticsearch(ELASTICSEARCH_URL)
    await elastic.ping()
    await initialize_storage(db, elastic)
    app.state.db = db
    app.state.elastic = elastic
    app.state.post_service = PostService(
        PostRepository(db),
        SearchRepository(elastic, ELASTICSEARCH_INDEX),
    )
    try:
        yield
    finally:
        await elastic.close()
        await db.close()


app = FastAPI(title="Simple Search Engine", version="1.0.0", lifespan=lifespan)
app.include_router(posts_router)
app.include_router(search_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
