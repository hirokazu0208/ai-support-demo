from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="AI Support Desk API")

app.include_router(health.router)
