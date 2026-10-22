from fastapi import FastAPI

app = FastAPI(title="TaskFlow")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
