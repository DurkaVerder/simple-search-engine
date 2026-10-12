from fastapi import FastAPI
from app.api.v1.routers.posts import router as posts_router

app = FastAPI()

app.include_router(posts_router)



