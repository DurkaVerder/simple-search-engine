from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["search"])




@router.get("/")
async def search(q: str):
    return {"message": f"Search for query: {q}"}