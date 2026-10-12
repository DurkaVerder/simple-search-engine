from __future__ import annotations

import argparse
import ast
import asyncio
import csv
import hashlib
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

from app.repositories.post_repository import PostRepository
from app.search.search_repository import SearchRepository
from app.settings import ELASTICSEARCH_INDEX, ELASTICSEARCH_URL, POSTGRES_DSN

load_dotenv()

CHUNK_SIZE = int(os.environ.get("IMPORT_CHUNK_SIZE", "500"))


def parse_rubrics(value: str) -> list[str]:
    if not value.strip():
        return []
    result = ast.literal_eval(value)
    if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
        raise ValueError("rubrics must be a list of strings")
    return result


def make_id(row_number: int, text: str, created_date: str, rubrics: str) -> uuid.UUID:
    source = f"{row_number}\0{text}\0{created_date}\0{rubrics}".encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    return uuid.uuid5(uuid.NAMESPACE_URL, digest)


def read_posts(csv_path: Path) -> Iterator[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        expected = {"text", "created_date", "rubrics"}
        if not reader.fieldnames or not expected.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain columns: {', '.join(sorted(expected))}")

        for row_number, row in enumerate(reader, start=2):
            text = (row["text"] or "").strip()
            created_date_value = (row["created_date"] or "").strip()
            rubrics_value = row["rubrics"] or ""
            if not text:
                raise ValueError(f"row {row_number}: text is empty")
            try:
                created_date = datetime.fromisoformat(created_date_value)
                rubrics = parse_rubrics(rubrics_value)
            except (TypeError, ValueError, SyntaxError) as error:
                raise ValueError(f"row {row_number}: invalid date or rubrics: {error}") from error

            post_id = make_id(row_number, text, created_date_value, rubrics_value)
            yield {
                "id": post_id,
                "rubrics": rubrics,
                "text": text,
                "created_date": created_date,
            }


async def wait_for_elasticsearch(client: AsyncElasticsearch) -> None:
    for attempt in range(1, 61):
        try:
            if await client.ping():
                return
        except Exception as error:
            if attempt == 60:
                raise RuntimeError("Elasticsearch did not become ready") from error
        await asyncio.sleep(2)
    raise RuntimeError("Elasticsearch did not become ready")


async def chunks(items: Iterator[dict[str, Any]]) -> AsyncIterator[list[dict[str, Any]]]:
    chunk: list[dict[str, Any]] = []
    for item in items:
        chunk.append(item)
        if len(chunk) == CHUNK_SIZE:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def import_posts(csv_path: Path) -> int:
    pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=10)
    elastic = AsyncElasticsearch(ELASTICSEARCH_URL)
    imported = 0
    try:
        await wait_for_elasticsearch(elastic)
        posts_repository = PostRepository(pool)
        search_repository = SearchRepository(elastic, ELASTICSEARCH_INDEX)
        await posts_repository.create_schema()
        await search_repository.create_index()

        async for batch in chunks(read_posts(csv_path)):
            await posts_repository.upsert_many(batch)
            await search_repository.index_many(batch)
            imported += len(batch)

        await search_repository.refresh()
        return imported
    finally:
        await elastic.close()
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path, default=Path("posts.csv"))
    args = parser.parse_args()
    count = asyncio.run(import_posts(args.csv_path))
    print(f"Imported {count} posts into PostgreSQL and '{ELASTICSEARCH_INDEX}'")


if __name__ == "__main__":
    main()
