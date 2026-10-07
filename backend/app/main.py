from fastapi import FastAPI

from app.routers import agent, faqs, health, inquiries

app = FastAPI(title="AI Support Desk API")

app.include_router(health.router)
app.include_router(inquiries.router)
app.include_router(faqs.router)
app.include_router(agent.router)
