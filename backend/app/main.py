from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .routers import auth, orgs, projects, plans, video, analytics, health
from .db import Base, engine

Base.metadata.create_all(bind=engine)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(orgs.router, prefix="/orgs", tags=["organizations"])
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(plans.router, prefix="/plans", tags=["plans"])
app.include_router(video.router, prefix="/video", tags=["video"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
