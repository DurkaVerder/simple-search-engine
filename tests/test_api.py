from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

from elastic_transport import ConnectionError as ElasticConnectionError
import pytest

from app.repositories.post_repository import PostRepository
from app.search.search_repository import SearchRepository
from app.services.post_service import PostService


@pytest.mark.asyncio
async def test_search_returns_documents_sorted_by_database() -> None:
    post_id = uuid4()
    db = AsyncMock()
    db.fetch.return_value = [
        {
            "id": post_id,
            "rubrics": ["news"],
            "text": "A document",
            "created_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
    ]
    elastic = AsyncMock()
    elastic.search.return_value = {
        "hits": {"hits": [{"_source": {"id": str(post_id)}}]}
    }
    service = PostService(PostRepository(db), SearchRepository(elastic, "posts"))

    result = await service.search_posts("document")

    assert result[0].id == post_id
    elastic.search.assert_awaited_once()
    db.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_removes_post_from_database_and_index() -> None:
    post_id = uuid4()
    db = MagicMock()
    db.acquire.return_value.__aenter__ = AsyncMock()
    db.acquire.return_value.__aenter__.return_value.execute = AsyncMock(
        return_value="DELETE 1"
    )
    elastic = AsyncMock()
    service = PostService(PostRepository(db), SearchRepository(elastic, "posts"))

    await service.delete_post(post_id)

    elastic.delete.assert_awaited_once_with(
        index="posts",
        id=str(post_id),
        ignore=[404],
    )


@pytest.mark.asyncio
async def test_delete_retries_elasticsearch_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post_id = uuid4()
    elastic = AsyncMock()
    elastic.delete.side_effect = [
        ElasticConnectionError("temporary failure"),
        ElasticConnectionError("temporary failure"),
        ElasticConnectionError("temporary failure"),
        None,
    ]
    sleep = AsyncMock()
    monkeypatch.setattr("app.search.search_repository.asyncio.sleep", sleep)

    await SearchRepository(elastic, "posts").delete(post_id)

    assert elastic.delete.await_count == 4
    sleep.assert_has_awaits(
        [call(1), call(2), call(4)]
    )
