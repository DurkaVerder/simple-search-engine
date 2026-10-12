from pydantic import BaseModel

class Post(BaseModel):
    id: str
    rubrics: list[str]
    text: str
    created_date: str

class SearchResponse(BaseModel):
    posts: list[Post]

