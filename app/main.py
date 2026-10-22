from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import initialize_database
from app.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="TaskFlow", lifespan=lifespan)
app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
