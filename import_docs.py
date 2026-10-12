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
from elasticsearch import AsyncElasticsearch, helpers

load_dotenv()

POSTGRES_DSN = os.environ["POSTGRES_DSN"]
ELASTICSEARCH_URL = os.environ["ELASTICSEARCH_URL"]
ELASTICSEARCH_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "posts")
CHUNK_SIZE = int(os.environ.get("IMPORT_CHUNK_SIZE", "500"))

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id UUID PRIMARY KEY,
    rubrics TEXT[] NOT NULL DEFAULT '{}',
    text TEXT NOT NULL,
    created_date TIMESTAMPTZ NOT NULL
);
"""

INDEX_MAPPING = {
    "properties": {
        "id": {"type": "keyword"},
        "text": {"type": "text"},
    }
}


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
        await elastic.indices.create(index=ELASTICSEARCH_INDEX, mappings=INDEX_MAPPING, ignore=400)

        async with pool.acquire() as connection:
            await connection.execute(CREATE_TABLE)
            async for batch in chunks(read_posts(csv_path)):
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
                        for post in batch
                    ],
                )
                await helpers.async_bulk(
                    elastic,
                    (
                        {
                            "_op_type": "index",
                            "_index": ELASTICSEARCH_INDEX,
                            "_id": str(post["id"]),
                            "_source": {
                                "id": str(post["id"]),
                                "text": post["text"],
                            },
                        }
                        for post in batch
                    ),
                )
                imported += len(batch)

        await elastic.indices.refresh(index=ELASTICSEARCH_INDEX)
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
