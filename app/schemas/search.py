from datetime import datetime
from uuid import UUID


from pydantic import BaseModel, Field


class Post(BaseModel):
    id: UUID
    rubrics: list[str] = Field(default_factory=list)
    text: str
    created_date: datetime
