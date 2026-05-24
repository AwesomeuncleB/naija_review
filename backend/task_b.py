"""
task_b.py
=========
Task B: Recommendation Agent
ReAct-style agentic loop with cold-start handling,
collaborative filtering, and Nigerian context ranking.
"""

import json
import httpx
import os
from typing import Optional, AsyncIterator
from .database import (
    get_user, get_user_reviews, get_user_rated_businesses,
    get_similar_users, get_top_businesses_for_similar_users,
    search_businesses, get_business,
)
from .nigerian_context import (
    build_persona_context,
    build_system_prompt_task_b,
    get_city_profile,
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") or os.getenv("GROQ_KEY_1", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
MODEL        = "llama-3.3-70b-versatile"


# ── Candidate retrieval ───────────────────────────────────────────────────────

def get_candidates(
    user_id: Optional[str],
    user_data: dict,
    city: str,
    category_hint: Optional[str] = None,
    limit: int = 15,
) -> list[dict]:
    candidates = []
    seen_ids   = set()

    # Strategy 1: Collaborative filtering
    if user_id:
        already_reviewed = get_user_rated_businesses(user_id)
        similar_users    = get_similar_users(user_id, limit=8)
        similar_ids      = [u["user_id"] for u in similar_users]
        if similar_ids:
            collab = get_top_businesses_for_similar_users(similar_ids, already_reviewed, limit=10)
            for b in collab:
                if b["business_id"] not in seen_ids:
                    b["source"] = "collaborative"
                    candidates.append(b)
                    seen_ids.add(b["business_id"])

    # Strategy 2: Content-based
    fp    = user_data.get("style_fingerprint", {})
    topic = category_hint or fp.get("dominant_topic", "Restaurants")
    content = search_businesses(category=topic, min_stars=3.5, limit=15)
    if len(content) < 5:
        content = search_businesses(category="Restaurants", min_stars=4.0, limit=15)
    for b in content:
        if b["business_id"] not in seen_ids:
            b["source"] = "content"
            candidates.append(b)
            seen_ids.add(b["business_id"])

    # Strategy 3: Popular fill
    if user_id and len(candidates) < limit:
        popular = search_businesses(min_stars=3.5, limit=10)
        for b in popular:
            if b["business_id"] not in seen_ids:
                b["source"] = "popular"
                candidates.append(b)
                seen_ids.add(b["business_id"])

    return candidates[:limit]


def build_recommendation_prompt(
    user_data: dict,
    user_reviews: list[dict],
    candidates: list[dict],
    city: str,
    naija_traits: list[str],
    conversation_history: list[dict],
    cold_start: bool = False,
) -> str:
    persona_context = build_persona_context(
        user_data, user_reviews, city, naija_traits,
        business_city=None,
    )

    candidates_str = ""
    for i, c in enumerate(candidates, 1):
        candidates_str += f"""
[{i}] {c.get('name', 'Unknown')}
  Category      : {c.get('categories', 'N/A')[:80]}
  Location      : {c.get('city', 'Unknown')}
  Platform rating: {c.get('stars', 'N/A')}/5 ({c.get('review_count', 0)} reviews)
  Source        : {c.get('source', 'search')}
  Business ID   : {c.get('business_id', '')}
"""

    convo_str = ""
    if conversation_history:
        convo_str = "\nCONVERSATION HISTORY:\n"
        for msg in conversation_history[-6:]:
            convo_str += f"[{msg['role'].upper()}]: {msg['content']}\n"

    cold_note = ""
    if cold_start:
        cold_note = "\nCOLD START: User has little/no history. Ask 1-2 clarifying questions if needed.\n"

    return f"""{persona_context}
{cold_note}
CANDIDATE BUSINESSES TO RANK:
{candidates_str}
{convo_str}

TASK: Rank the top 5 candidates for this specific user. Explain each recommendation in terms of their behavioural history.
Output valid JSON only."""


# ── Main recommendation function ──────────────────────────────────────────────

async def get_recommendations_stream(
    user_id: Optional[str] = None,
    manual_persona: Optional[dict] = None,
    city: str = "Lagos",
    naija_traits: Optional[list] = None,
    category_hint: Optional[str] = None,
    conversation_history: Optional[list] = None,
    inject_business_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> AsyncIterator[str]:

    key = api_key or GROQ_API_KEY
    if not key:
        yield 'data: {"error": "No API key"}\n\n'
        return

    # Load user data
    cold_start = False
    if user_id:
        user_data    = get_user(user_id)
        user_reviews = get_user_reviews(user_id, limit=10)
        if not user_data or user_data.get("review_count", 0) < 3:
            cold_start = True
            user_data  = user_data or {"user_id": user_id, "avg_stars": 3.5,
                                        "review_count": 0, "style_fingerprint": {}}
    else:
        cold_start   = True
        user_data    = manual_persona or {"avg_stars": 3.5, "review_count": 0, "style_fingerprint": {}}
        user_reviews = []

    # Get candidates
    candidates = get_candidates(user_id, user_data, city, category_hint)

    # Oracle injection for evaluation
    if inject_business_id:
        injected_ids = {c["business_id"] for c in candidates}
        if inject_business_id not in injected_ids:
            true_biz = get_business(inject_business_id)
            if true_biz:
                true_biz["source"] = "oracle"
                candidates.append(true_biz)

    # Fallback mock candidates if DB empty
    if not candidates:
        candidates = _mock_candidates(city)

    # Build prompt and stream
    system_prompt = build_system_prompt_task_b()
    user_prompt   = build_recommendation_prompt(
        user_data, user_reviews, candidates, city,
        naija_traits or [], conversation_history or [], cold_start
    )

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 2000,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            },
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    text  = chunk["choices"][0]["delta"].get("content", "")
                    if text:
                        payload = json.dumps({
                            "type": "content_block_delta",
                            "delta": {"type": "text_delta", "text": text}
                        })
                        yield f"data: {payload}\n\n"
                except Exception:
                    pass


def _mock_candidates(city: str) -> list[dict]:
    return [
        {"business_id": "mock_001", "name": "Chicken Republic",      "categories": "Restaurants, Fast Food, Nigerian",    "city": city, "stars": 3.8, "review_count": 420, "source": "content"},
        {"business_id": "mock_002", "name": "Kilimanjaro Restaurant", "categories": "Restaurants, Nigerian, Continental",  "city": city, "stars": 4.2, "review_count": 310, "source": "content"},
        {"business_id": "mock_003", "name": "Yellow Chilli",          "categories": "Restaurants, Nigerian, Upscale",      "city": city, "stars": 4.5, "review_count": 280, "source": "collaborative"},
        {"business_id": "mock_004", "name": "The Place Restaurant",   "categories": "Restaurants, Nigerian, Casual",       "city": city, "stars": 4.0, "review_count": 560, "source": "collaborative"},
        {"business_id": "mock_005", "name": "Nando's Nigeria",        "categories": "Restaurants, Peri-Peri, Fast Casual", "city": city, "stars": 4.1, "review_count": 390, "source": "content"},
        {"business_id": "mock_006", "name": "Shoprite",               "categories": "Shopping, Supermarket, Retail",       "city": city, "stars": 3.6, "review_count": 800, "source": "content"},
        {"business_id": "mock_007", "name": "Lagos Oriental Hotel",   "categories": "Hotels, Hospitality, Luxury",         "city": city, "stars": 4.3, "review_count": 190, "source": "content"},
        {"business_id": "mock_008", "name": "Bature Brewery",         "categories": "Bars, Brewery, Drinks",               "city": city, "stars": 4.6, "review_count": 150, "source": "collaborative"},
    ]
