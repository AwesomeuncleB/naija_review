"""
task_a.py — Groq (llama-3.3-70b-versatile) with fallback key
"""
import json
import httpx
import os
from typing import Optional, AsyncIterator
from .database import get_user, get_user_reviews, get_business
from .nigerian_context import (
    build_persona_context,
    build_system_prompt_task_a,
    get_category_context,
    get_city_profile,
    is_nigerian_city,
)

GROQ_KEY_1     = os.getenv("GROQ_KEY_1", "") or os.getenv("GROQ_API_KEY", "")
GROQ_KEY_2     = os.getenv("GROQ_KEY_2", "")
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
MODEL          = "llama-3.3-70b-versatile"
YELP_GLOBAL_AVG = 3.75


def _groq_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "content-type": "application/json"}


def _groq_body(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> dict:
    return {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    }


async def _groq_post(client: httpx.AsyncClient, system_prompt: str, user_prompt: str) -> str:
    for key in filter(None, [GROQ_KEY_1, GROQ_KEY_2]):
        try:
            resp = await client.post(
                GROQ_URL,
                headers=_groq_headers(key),
                json=_groq_body(system_prompt, user_prompt),
            )
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
        except Exception:
            continue
    raise Exception("Both Groq keys failed")


def predict_rating(user_data: dict, business: dict, city: str = "Lagos") -> int:
    fp         = user_data.get("style_fingerprint", {})
    user_avg   = fp.get("avg_rating") or user_data.get("avg_stars") or YELP_GLOBAL_AVG
    biz_avg    = business.get("stars") or YELP_GLOBAL_AVG
    rating_std = fp.get("rating_std", 1.0)

    blended = (0.60 * user_avg) + (0.30 * biz_avg) + (0.10 * YELP_GLOBAL_AVG)
    if rating_std > 1.5:
        blended = (0.75 * user_avg) + (0.15 * biz_avg) + (0.10 * YELP_GLOBAL_AVG)

    city_profile = get_city_profile(city)
    blended += city_profile.get("rating_bias", 0.0)

    cats = (business.get("categories") or "").lower()
    if any(w in cats for w in ["hotel", "motel", "inn", "resort"]):
        blended += 0.15
    elif any(w in cats for w in ["fast food", "mcdonald", "burger king"]):
        blended -= 0.10

    return max(1, min(5, round(blended)))


def build_user_prompt_task_a(
    user_data: dict,
    user_reviews: list[dict],
    business: dict,
    city: str,
    naija_traits: list[str],
    pidgin_level: str = "medium",
    predicted_rating: Optional[int] = None,
) -> str:
    business_city = business.get("city", "")
    nigerian      = is_nigerian_city(business_city)

    persona_context = build_persona_context(
        user_data, user_reviews, city, naija_traits,
        business_city=business_city,
    )
    category_ctx  = get_category_context(business.get("categories", ""))
    rating_anchor = f"\nPREDICTED RATING (use exactly): {predicted_rating}/5\n" if predicted_rating else ""

    if nigerian and category_ctx.get("naija_refs"):
        category_section = (
            "CONSUMER CONCERNS:\n"
            f"Key concerns    : {', '.join(category_ctx.get('key_concerns', []))}\n"
            f"Local references: {', '.join(category_ctx.get('naija_refs', []))}"
        )
    else:
        category_section = f"CONSUMER CONCERNS:\nKey concerns: {', '.join(category_ctx.get('key_concerns', []))}"

    return (
        f"{persona_context}\n{rating_anchor}\n"
        f"BUSINESS TO REVIEW:\n"
        f"Name           : {business.get('name', 'Unknown')}\n"
        f"Category       : {business.get('categories', 'General')}\n"
        f"Location       : {business_city or city}\n"
        f"Platform rating: {business.get('stars', 'N/A')}/5 ({business.get('review_count', 'N/A')} reviews)\n"
        f"Attributes     : {json.dumps(business.get('attributes', {}), indent=2)[:300]}\n\n"
        f"{category_section}\n\n"
        f"INSTRUCTIONS:\n"
        f"- Pidgin intensity: {pidgin_level}\n"
        f"- Rating MUST be {predicted_rating if predicted_rating else 'aligned with user history'}\n"
        f"- Mirror this user's exact voice from their history\n"
        f"- Output valid JSON only — no markdown, no preamble"
    )


async def generate_review_stream(
    user_id: Optional[str],
    business_id: Optional[str],
    manual_persona: Optional[dict] = None,
    manual_business: Optional[dict] = None,
    city: str = "Lagos",
    naija_traits: Optional[list] = None,
    pidgin_level: str = "medium",
    api_key: Optional[str] = None,
) -> AsyncIterator[str]:

    if user_id:
        user_data = get_user(user_id)
        if not user_data:
            yield f'data: {{"error": "User {user_id} not found"}}\n\n'
            return
        user_reviews = get_user_reviews(user_id, limit=12)
    else:
        user_data    = manual_persona or {"user_id": "manual", "avg_stars": 3.5,
                                          "review_count": 20, "style_fingerprint": {}}
        user_reviews = []

    if business_id:
        business = get_business(business_id)
        if not business:
            yield f'data: {{"error": "Business {business_id} not found"}}\n\n'
            return
    else:
        business = manual_business or {"name": "Unknown", "categories": "General"}

    predicted_rating = predict_rating(user_data, business, city)
    system_prompt    = build_system_prompt_task_a()
    user_prompt      = build_user_prompt_task_a(
        user_data, user_reviews, business, city,
        naija_traits or [], pidgin_level, predicted_rating
    )

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            text = await _groq_post(client, system_prompt, user_prompt)
            payload = json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": text}
            })
            yield f"data: {payload}\n\n"
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'


async def generate_review_batch(
    pairs: list[dict],
    city: str = "Lagos",
    api_key: Optional[str] = None,
) -> list[dict]:
    results = []
    async with httpx.AsyncClient(timeout=90) as client:
        for pair in pairs:
            uid = pair.get("user_id")
            bid = pair.get("business_id")
            try:
                user_data    = get_user(uid) or {}
                user_reviews = get_user_reviews(uid, limit=12) if uid else []
                business     = get_business(bid) or {"name": bid, "categories": "General"}

                predicted_rating = predict_rating(user_data, business, city)
                system_prompt    = build_system_prompt_task_a()
                user_prompt      = build_user_prompt_task_a(
                    user_data, user_reviews, business, city, [], "medium", predicted_rating
                )

                text  = await _groq_post(client, system_prompt, user_prompt)
                clean = text.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(clean)
                except Exception:
                    last = clean.rfind("}")
                    parsed = json.loads(clean[:last + 1]) if last > 0 else {"error": "parse_failed", "raw": text[:200]}

            except Exception as e:
                parsed = {"error": str(e)}

            parsed["rating"]       = predicted_rating if "predicted_rating" in dir() else None
            parsed["predicted_by"] = "bayesian_blend"
            results.append({"user_id": uid, "business_id": bid,
                             "business_name": (get_business(bid) or {}).get("name") if bid else None,
                             **parsed})
    return results
