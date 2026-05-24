"""
main.py
=======
NaijaReview Intelligence — FastAPI Backend
Serves Task A (User Modeling) and Task B (Recommendation) endpoints.
"""

import json
from dotenv import load_dotenv
load_dotenv()
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .database import db_stats, search_users, search_businesses, get_user, get_user_reviews
from .task_a import generate_review_stream, generate_review_batch
from .task_b import get_recommendations_stream

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NaijaReview Intelligence API",
    description="DSN x BCT Hackathon — LLM Agent for Nigerian user modeling and recommendation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class TaskARequest(BaseModel):
    # Option 1: Use DB user + business
    user_id: Optional[str] = None
    business_id: Optional[str] = None
    # Option 2: Manual persona (frontend custom mode)
    manual_persona: Optional[dict] = None
    manual_business: Optional[dict] = None
    # Context
    city: str = "Lagos"
    naija_traits: list[str] = []
    pidgin_level: str = "medium"  # none | low | medium | high
    api_key: Optional[str] = None


class TaskABatchRequest(BaseModel):
    pairs: list[dict]  # [{"user_id": ..., "business_id": ...}]
    city: str = "Lagos"
    api_key: Optional[str] = None


class TaskBRequest(BaseModel):
    user_id: Optional[str] = None
    manual_persona: Optional[dict] = None
    city: str = "Lagos"
    naija_traits: list[str] = []
    category_hint: Optional[str] = None
    conversation_history: Optional[list[dict]] = None
    inject_business_id: Optional[str] = None  # evaluation: force true item into candidates
    api_key: Optional[str] = None


# ── Health & data endpoints ───────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "NaijaReview Intelligence",
        "tasks": ["Task A: User Modeling", "Task B: Recommendation"],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    stats = db_stats()
    return {
        "status": "ok",
        "db_connected": stats["db_exists"],
        "db_stats": stats,
    }


@app.get("/users")
def list_users(min_reviews: int = 20, limit: int = 50):
    """Browse users in the database — used by frontend user picker."""
    try:
        users = search_users(min_reviews=min_reviews, limit=limit)
        return {"users": users, "count": len(users)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
def get_user_profile(user_id: str):
    """Get a single user's profile + recent reviews."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reviews = get_user_reviews(user_id, limit=5)
    return {"user": user, "recent_reviews": reviews}


@app.get("/businesses")
def list_businesses(
    category: Optional[str] = None,
    city: Optional[str] = None,
    min_stars: float = 0.0,
    limit: int = 20,
    search: Optional[str] = None,
):
    """Search businesses — used by Task A business picker."""
    try:
        businesses = search_businesses(category=category, city=city, min_stars=min_stars, limit=limit, search=search)
        return {"businesses": businesses, "count": len(businesses)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Task A endpoints ──────────────────────────────────────────────────────────

@app.post("/task-a/generate")
async def task_a_generate(req: TaskARequest):
    """
    Task A: Generate a simulated review for a user-business pair.
    Returns a streaming SSE response.
    """
    async def event_stream():
        async for chunk in generate_review_stream(
            user_id=req.user_id,
            business_id=req.business_id,
            manual_persona=req.manual_persona,
            manual_business=req.manual_business,
            city=req.city,
            naija_traits=req.naija_traits,
            pidgin_level=req.pidgin_level,
            api_key=req.api_key or os.getenv("GROQ_API_KEY"),
        ):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/task-a/batch")
async def task_a_batch(req: TaskABatchRequest):
    """
    Task A: Batch evaluation endpoint.
    Judges submit a list of (user_id, business_id) pairs,
    receive predicted ratings + reviews for RMSE/ROUGE evaluation.
    """
    if len(req.pairs) > 100:
        raise HTTPException(status_code=400, detail="Max 100 pairs per batch request")

    results = await generate_review_batch(
        pairs=req.pairs,
        city="Lagos",
        api_key=req.api_key or os.getenv("GROQ_API_KEY"),
    )
    return {"results": results, "count": len(results)}


# ── Task B endpoints ──────────────────────────────────────────────────────────

@app.post("/task-b/recommend")
async def task_b_recommend(req: TaskBRequest):
    """
    Task B: Get personalised recommendations for a user.
    Streaming SSE — yields JSON as the agent reasons.
    Handles warm users, cold-start, and multi-turn conversation.
    """
    async def event_stream():
        async for chunk in get_recommendations_stream(
            user_id=req.user_id,
            manual_persona=req.manual_persona,
            city=req.city,
            naija_traits=req.naija_traits,
            category_hint=req.category_hint,
            conversation_history=req.conversation_history,
            inject_business_id=req.inject_business_id,
            api_key=req.api_key or os.getenv("GROQ_API_KEY"),
        ):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Dev / demo endpoints ──────────────────────────────────────────────────────

@app.get("/demo/persona")
def demo_persona():
    """Returns a sample persona for frontend development when DB is empty."""
    return {
        "user_id": "demo_user_001",
        "avg_stars": 3.2,
        "review_count": 34,
        "style_fingerprint": {
            "avg_words_per_review": 52,
            "avg_rating": 3.2,
            "rating_std": 1.1,
            "dominant_topic": "food",
            "tone": "balanced",
            "review_count": 34,
        },
        "sample_reviews": [
            {"stars": 2, "text": "E no reach the hype at all. Waited 45 minutes for my order and the rice was cold. Never again.", "business_name": "Chicken Republic"},
            {"stars": 4, "text": "Honestly this place surprised me. The suya was fresh and the service was faster than I expected. Would come back.", "business_name": "Mallam Musa Suya Spot"},
            {"stars": 3, "text": "Average experience. The food was okay but nothing special. Overpriced for what you get.", "business_name": "Yellow Chilli"},
        ],
    }


# ── Static file serving (for Docker deployment) ───────────────────────────────
# Mounts built React app — only active if ./static exists (i.e. inside Docker)
_static = Path(__file__).parent.parent / "static"
if _static.exists():
    from fastapi.staticfiles import StaticFiles
    _assets = _static / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/app")
    @app.get("/app/{path:path}")
    def serve_spa(path: str = ""):
        return FileResponse(str(_static / "index.html"))
