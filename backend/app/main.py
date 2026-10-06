from fastapi import FastAPI

from app.routers import health, inquiries

app = FastAPI(title="AI Support Desk API")

app.include_router(health.router)
app.include_router(inquiries.router)
