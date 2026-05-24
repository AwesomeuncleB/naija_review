"""
nigerian_context.py
===================
The cultural intelligence layer — what makes NaijaReview different from every other team.

This module handles:
1. City-level profiles (Lagos ≠ Abuja ≠ Port Harcourt)
2. Category-level Nigerian consumer concerns
3. Pidgin phrase banks calibrated by intensity
4. Persona context builder (injected into every LLM call)
5. System prompts for Task A and Task B

KEY FIX (v2): Nigerian cultural flavor text (NEPA refs, buka comparisons, local
place names) is now GATED behind is_nigerian_business. The Yelp dataset is US-based,
so injecting "generator backup" or "mama put comparison" into reviews of American
businesses confuses the model and hurts ROUGE scores.

What always applies (data-driven, not location-dependent):
  - Behavioral fingerprint (word count, rating stats, tone, patterns)
  - User's price sensitivity and service expectations (as personality traits)
  - Pidgin code-switching calibration
  - Few-shot examples from real history

What only applies when the business is actually in Nigeria:
  - City cultural references (Danfo, NEPA, Wuse, etc.)
  - Category naija_refs (generator backup, buka comparison, tokunbo, etc.)
  - "Location context: {city}, Nigeria" framing
"""

from typing import Optional
import json


# ── Nigerian city detection ───────────────────────────────────────────────────

NIGERIAN_CITIES = {
    "Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan",
    "Enugu", "Kaduna", "Benin City", "Calabar", "Owerri",
    "Abeokuta", "Ilorin", "Jos", "Warri", "Uyo",
}

def is_nigerian_city(city: Optional[str]) -> bool:
    """Return True if the city is a known Nigerian city."""
    if not city:
        return False
    return city.strip() in NIGERIAN_CITIES


# ── City profiles ─────────────────────────────────────────────────────────────

CITY_PROFILES = {
    "Lagos": {
        "descriptor": "Nigeria's commercial capital — fast-paced, hustle-driven, cosmopolitan",
        "price_sensitivity": "High — knows market rates and will call out overpricing",
        "service_expectation": "Efficiency over formality. Speed matters. Long queues are unacceptable.",
        "cultural_refs": ["Danfo", "Third Mainland", "VI", "Lekki", "Surulere", "NEPA"],
        "speech_markers": ["abeg", "omo", "sharp sharp", "wetin", "e don do"],
        "food_refs": ["buka", "mama put", "suya joint", "Chinese for mainland price"],
        "rating_bias": -0.2,  # Lagos reviewers slightly harsher
    },
    "Abuja": {
        "descriptor": "Nigeria's capital — formal, diplomatic, government-heavy",
        "price_sensitivity": "Moderate — Abuja prices are high, residents accept it but still notice value",
        "service_expectation": "Professional service expected. Less tolerance for informality.",
        "cultural_refs": ["Wuse", "Garki", "Maitama", "Area 1", "Gwarinpa"],
        "speech_markers": ["honestly", "sincerely", "I must say", "frankly speaking"],
        "food_refs": ["proper restaurant", "continental", "grills"],
        "rating_bias": 0.1,
    },
    "Port Harcourt": {
        "descriptor": "Oil city — wealthy pockets, industrial edge, Rivers State pride",
        "price_sensitivity": "Moderate-low — oil money means less price sensitivity in some circles",
        "service_expectation": "Quality over speed. PH people take pride in good living.",
        "cultural_refs": ["GRA", "Trans Amadi", "Mile 1", "Rumuola"],
        "speech_markers": ["my brother", "I tell you", "nah wah", "straight up"],
        "food_refs": ["banga soup", "fresh fish", "pepper soup joint"],
        "rating_bias": 0.0,
    },
    "Kano": {
        "descriptor": "Northern commercial hub — traditional, trade-oriented, value-focused",
        "price_sensitivity": "Very high — Kano traders know value better than anyone",
        "service_expectation": "Reliability and honesty over speed. Trust matters.",
        "cultural_refs": ["Sabon Gari", "Fagge", "Kurmi Market"],
        "speech_markers": ["wallahi", "in sha Allah", "barka", "kai"],
        "food_refs": ["suya", "tuwo", "kilishi", "fura da nono"],
        "rating_bias": 0.1,
    },
    "Ibadan": {
        "descriptor": "Ancient Yoruba city — historic, academic, understated",
        "price_sensitivity": "High — Ibadan is famously cost-conscious",
        "service_expectation": "Unpretentious. Substance over style.",
        "cultural_refs": ["UI", "Dugbe", "Bodija", "Ring Road"],
        "speech_markers": ["jo", "abi", "ehn", "se"],
        "food_refs": ["amala joint", "pounded yam", "local buka"],
        "rating_bias": -0.1,
    },
    "Enugu": {
        "descriptor": "Coal City — Igbo cultural heartland, community-oriented",
        "price_sensitivity": "High — value-conscious, community word-of-mouth matters",
        "service_expectation": "Warmth and respect. Personal connection valued.",
        "cultural_refs": ["GRA Enugu", "Independence Layout", "Ogbete Market"],
        "speech_markers": ["biko", "kedu", "nna", "chai"],
        "food_refs": ["ofe akwu", "ugba", "abacha", "nkwobi"],
        "rating_bias": 0.0,
    },
}

DEFAULT_CITY = {
    "descriptor": "Nigerian urban dweller",
    "price_sensitivity": "High — value for money is paramount",
    "service_expectation": "Efficient, respectful service",
    "cultural_refs": ["NEPA", "generator", "Lagos traffic"],
    "speech_markers": ["abeg", "omo", "sharp sharp"],
    "food_refs": ["local buka", "suya", "jollof"],
    "rating_bias": 0.0,
}


def get_city_profile(city: str) -> dict:
    return CITY_PROFILES.get(city, DEFAULT_CITY)


# ── Category contexts ─────────────────────────────────────────────────────────

CATEGORY_CONTEXTS = {
    "Restaurants": {
        "key_concerns": ["portion size", "value for money", "wait time", "freshness", "cleanliness"],
        "naija_refs": ["buka standard", "mama put comparison", "jollof rice benchmark", "generator backup"],
        "rating_bias": 0.0,
    },
    "Hotels": {
        "key_concerns": ["power supply", "water supply", "security", "WiFi", "breakfast included"],
        "naija_refs": ["NEPA situation", "generator noise", "security men", "hot water"],
        "rating_bias": 0.2,
    },
    "Electronics": {
        "key_concerns": ["authenticity", "warranty", "price comparison", "after-sales service"],
        "naija_refs": ["Slot comparison", "Jumia price check", "tokunbo vs brand new", "power surge protection"],
        "rating_bias": -0.1,
    },
    "Beauty": {
        "key_concerns": ["product authenticity", "skin tone compatibility", "longevity", "price"],
        "naija_refs": ["suitable for dark skin", "Lagos heat test", "sweat-proof"],
        "rating_bias": 0.1,
    },
    "Shopping": {
        "key_concerns": ["price negotiation", "product authenticity", "variety", "location convenience"],
        "naija_refs": ["market comparison", "Oshodi price", "fake vs original"],
        "rating_bias": -0.1,
    },
}

DEFAULT_CATEGORY = {
    "key_concerns": ["value for money", "quality", "service", "reliability"],
    "naija_refs": [],
    "rating_bias": 0.0,
}


def get_category_context(categories: str) -> dict:
    if not categories:
        return DEFAULT_CATEGORY
    cats_lower = categories.lower()
    for key in CATEGORY_CONTEXTS:
        if key.lower() in cats_lower:
            return CATEGORY_CONTEXTS[key]
    if any(w in cats_lower for w in ["food", "restaurant", "cafe", "bar", "pizza", "sushi", "chicken"]):
        return CATEGORY_CONTEXTS["Restaurants"]
    if any(w in cats_lower for w in ["hotel", "motel", "inn", "lodg"]):
        return CATEGORY_CONTEXTS["Hotels"]
    return DEFAULT_CATEGORY


# ── Pidgin phrase banks ───────────────────────────────────────────────────────

PIDGIN_PHRASES = {
    "low": {
        "agreement": ["honestly", "I must say", "to be fair"],
        "disappointment": ["it wasn't great", "I expected better", "a bit disappointing"],
        "approval": ["quite good", "really nice", "pretty solid"],
        "value": ["reasonable price", "good value", "worth it"],
    },
    "medium": {
        "agreement": ["abeg", "omo", "e be like say"],
        "disappointment": ["e no reach the hype", "them no try", "big disappointment"],
        "approval": ["e dey sweet", "sharp sharp", "the thing correct"],
        "value": ["value for money sha", "e worth am", "price reasonable"],
    },
    "high": {
        "agreement": ["abeg I swear", "omo mehn", "chai"],
        "disappointment": ["e no do am at all", "total waste of time", "dem dey craze?"],
        "approval": ["e dey mad o", "this one na correct thing", "I hail am die"],
        "value": ["e cheap die", "value wey e give", "make you no miss am"],
    },
}


# ── Opinion pattern extractor ─────────────────────────────────────────────────

def _extract_opinion_patterns(reviews: list[dict]) -> dict:
    """
    Extract recurring themes from a user's review history.
    These become the behavioural signature injected into the prompt.
    """
    praise_words = ["great", "amazing", "good", "excellent", "love", "perfect",
                    "fresh", "quick", "friendly", "helpful", "clean", "value"]
    complaint_words = ["slow", "cold", "expensive", "rude", "dirty", "wait",
                       "overpriced", "small", "portion", "disappointing", "bad",
                       "wrong", "noisy", "loud", "parking"]

    praise_counts = {}
    complaint_counts = {}
    low_ratings = []
    high_ratings = []

    for r in reviews:
        text = r.get("text", "").lower()
        stars = r.get("stars", 3)

        if stars <= 2:
            low_ratings.append(r)
        if stars >= 4:
            high_ratings.append(r)

        for w in praise_words:
            if w in text:
                praise_counts[w] = praise_counts.get(w, 0) + 1
        for w in complaint_words:
            if w in text:
                complaint_counts[w] = complaint_counts.get(w, 0) + 1

    top_praises    = sorted(praise_counts,    key=praise_counts.get,    reverse=True)[:3]
    top_complaints = sorted(complaint_counts, key=complaint_counts.get, reverse=True)[:3]

    return {
        "recurring_praises":    top_praises,
        "recurring_complaints": top_complaints,
        "harsh_review_count":   len(low_ratings),
        "positive_review_count": len(high_ratings),
    }


# ── Persona context builder ───────────────────────────────────────────────────

def build_persona_context(
    user_data: dict,
    user_reviews: list[dict],
    city: Optional[str] = None,
    naija_traits: Optional[list] = None,
    business_city: Optional[str] = None,   # NEW: the actual city of the business being reviewed
) -> str:
    """
    Build the context block injected into every LLM prompt.

    Nigerian cultural flavor (city refs, local comparisons) is only injected
    when the business being reviewed is actually in Nigeria. This prevents the
    model from writing about "NEPA backup" for a Philadelphia restaurant.

    The behavioral fingerprint (word count, tone, rating stats, patterns,
    few-shot examples) always applies regardless of business location.
    """
    fp         = user_data.get("style_fingerprint", {})
    avg_rating = fp.get("avg_rating", user_data.get("avg_stars", 3.0))
    rating_std = fp.get("rating_std", 1.0)
    avg_words  = fp.get("avg_words_per_review", 60)
    tone       = fp.get("tone", "balanced")
    topic      = fp.get("dominant_topic", "food")
    city       = city or "Lagos"

    city_profile      = get_city_profile(city)
    nigerian_business = is_nigerian_city(business_city)

    # ── Writing style ─────────────────────────────────────────────────────────
    if avg_words < 25:
        writing_style    = "VERY SHORT reviews (under 25 words). One or two sentences max."
        word_instruction = "Write NO MORE than 30 words. Be extremely brief and punchy."
    elif avg_words < 60:
        writing_style    = "Short, punchy reviews (25-60 words). Gets to the point fast."
        word_instruction = f"Write approximately {int(avg_words)} words. Short and direct."
    elif avg_words < 120:
        writing_style    = "Medium-length reviews (60-120 words). Covers key points without rambling."
        word_instruction = f"Write approximately {int(avg_words)} words."
    elif avg_words < 200:
        writing_style    = "Detailed reviews (120-200 words). Methodical, covers multiple aspects."
        word_instruction = f"Write approximately {int(avg_words)} words. Cover multiple aspects."
    else:
        writing_style    = "Long, thorough reviews (200+ words). Comprehensive, storytelling style."
        word_instruction = f"Write approximately {int(avg_words)} words. Be thorough and detailed."

    # ── Opinion patterns from history ─────────────────────────────────────────
    patterns    = _extract_opinion_patterns(user_reviews) if user_reviews else {}
    pattern_str = ""
    if patterns.get("recurring_complaints"):
        pattern_str += f"\n- This user REPEATEDLY complains about: {', '.join(patterns['recurring_complaints'])}"
        pattern_str += "\n  → These concerns MUST appear in the generated review if relevant to this business."
    if patterns.get("recurring_praises"):
        pattern_str += f"\n- This user consistently praises: {', '.join(patterns['recurring_praises'])}"
    if patterns.get("harsh_review_count", 0) > 2:
        pattern_str += f"\n- Has written {patterns['harsh_review_count']} harsh (1-2 star) reviews — not afraid to be negative"

    # ── Few-shot examples ─────────────────────────────────────────────────────
    few_shot = ""
    if user_reviews:
        few_shot = "\n\nACTUAL PAST REVIEWS BY THIS USER — mirror this exact voice:\n"
        sorted_reviews = sorted(user_reviews, key=lambda x: x.get("stars", 3))
        sample = []
        if sorted_reviews:
            sample.append(sorted_reviews[0])   # lowest rated
        if len(sorted_reviews) > 1:
            sample.append(sorted_reviews[-1])  # highest rated
        middle = sorted_reviews[1:-1][:3]
        sample.extend(middle)

        for r in sample[:5]:
            biz   = r.get("business_name", "a business")
            stars = r.get("stars", "?")
            text  = r.get("text", "")[:400]
            if len(r.get("text", "")) > 400:
                text += "..."
            few_shot += f'\n[{stars}★ — {biz}]\n"{text}"\n'

    traits_str = ", ".join(naija_traits) if naija_traits else "typical Nigerian consumer"

    # ── Location block — gated ────────────────────────────────────────────────
    # Only say "City, Nigeria" and inject city cultural refs when the business
    # is actually in Nigeria. For US Yelp businesses, describe the user's
    # Nigerian background as a consumer profile, not a physical location claim.
    if nigerian_business:
        location_block = f"""Location context    : {city}, Nigeria
City character      : {city_profile['descriptor']}
Price sensitivity   : {city_profile['price_sensitivity']}
Service expectations: {city_profile['service_expectation']}"""
    else:
        location_block = f"""User background     : Nigerian consumer ({city} profile)
Price sensitivity   : {city_profile['price_sensitivity']}
Service expectations: {city_profile['service_expectation']}
(Note: business is not in Nigeria — apply consumer mindset, not local cultural refs)"""

    return f"""NIGERIAN USER PROFILE:
━━━━━━━━━━━━━━━━━━━━━━
{location_block}
Nigerian identity   : {traits_str}

BEHAVIOURAL FINGERPRINT (from {user_data.get('review_count', 0)} real reviews):
━━━━━━━━━━━━━━━━━━━━━━
Historical avg rating : {avg_rating:.1f}/5 (std: {rating_std:.1f})
Writing style         : {writing_style}
{word_instruction}
Primary topic focus   : {topic}
Overall tone          : {tone}
{pattern_str}
{few_shot}"""


# ── System prompts ────────────────────────────────────────────────────────────

def build_system_prompt_task_a() -> str:
    return """You are Dexter AI — a behavioural user modeling system that generates authentic consumer reviews.

MISSION: Given a user's real review history and a business, generate the EXACT review this specific user would write. Not a generic review — THIS person's review, in their voice.

━━━ BEHAVIOURAL FIDELITY RULES ━━━
1. WORD COUNT IS MANDATORY: Match the user's historical average word count. If they write 40-word reviews, write 40 words. If they write 200-word reviews, write 200 words.
2. RATING IS PRE-COMPUTED: The predicted rating is provided. Use it exactly — do not change it.
3. RECURRING PATTERNS: If the user's history shows recurring complaints (service speed, pricing, portions), these must appear in the generated review where relevant.
4. VOICE MATCHING: Study the few-shot examples carefully. Copy sentence length, punctuation style, capitalization patterns, and vocabulary level exactly.

━━━ AUTHENTICITY RULES ━━━
5. LOCATION AWARENESS: The user profile says whether the business is in Nigeria or not. If it's NOT in Nigeria, write a realistic review of that specific American/international business — do NOT inject Nigerian local references (NEPA, buka, generator, etc.) that would be out of place.
6. IF the business IS in Nigeria, Nigerian context applies naturally: code-switching, local comparisons, infrastructure concerns are all fair game.
7. CODE-SWITCHING: If the user's Nigerian background warrants it and the review context allows it, light Pidgin code-switching is fine. Never force it.
8. VALUE CONSCIOUSNESS: Nigerian consumers almost always reference value for money — was it worth it? This applies anywhere in the world.
9. NO CARICATURES: Avoid stereotyped writing. Real reviews read like real people.

━━━ OUTPUT FORMAT ━━━
Output ONLY valid JSON, no markdown fences, no preamble:
{
  "rating": <integer 1-5 — must match the provided predicted rating>,
  "review": "<the review text>",
  "tone": "<blunt|warm|frustrated|enthusiastic|measured|sarcastic|disappointed>",
  "pidgin_intensity": "<none|low|medium|high>",
  "key_praises": ["<up to 3 specific things praised>"],
  "key_complaints": ["<up to 3 specific things complained about>"],
  "word_count": <integer>,
  "behavioral_notes": "<one sentence: what in this user's history explains this review>"
}"""


def build_system_prompt_task_b() -> str:
    return """You are NaijaReview Intelligence — a personalised recommendation agent with deep understanding of Nigerian consumer behaviour.

MISSION: Analyse a Nigerian user's behavioural profile and recommend businesses they will genuinely love — reasoning like someone who knows them personally.

━━━ REASONING PROCESS ━━━
1. READ the profile carefully. What is this person's actual priority — price? quality? speed? experience?
2. SCORE each candidate against their specific history. A user who hates slow service needs fast places. A user who rates 4+ everywhere is forgiving.
3. EXPLAIN in their voice — if they're blunt, be blunt. If they're verbose, give detail.
4. CONSUMER MINDSET — Nigerian consumers care about value, reliability, and whether something is worth the trip. Apply this lens regardless of where the businesses are located.
5. DO NOT flag location mismatches in your reasoning trace. The candidate list is what it is — rank the best options available, using the user's behaviour as your guide.

━━━ COLD START HANDLING ━━━
If the user has no history (cold start), ask 2-3 targeted questions that will unlock the most information:
- "Are you looking for everyday meals or a special occasion spot?"
- "Are you more about the experience or the food quality?"
- "What's your budget range — affordable, mid-range, or upscale?"
These questions should be returned in cold_start_questions.

━━━ OUTPUT FORMAT ━━━
Output ONLY valid JSON:
{
  "recommendations": [
    {
      "business_id": "<exact id from candidate list>",
      "name": "<business name>",
      "predicted_rating": <float — what this user would rate it>,
      "confidence": <float 0-1>,
      "reason": "<why THIS user specifically would like it — reference their actual behaviour>",
      "naija_note": "<value/reliability/worth-it assessment from a Nigerian consumer lens>",
      "rank": <integer starting at 1>
    }
  ],
  "reasoning_trace": "<show your thinking: what you noticed about the user, which candidates you eliminated and why>",
  "cold_start_questions": ["<only if cold start — 2-3 questions to ask>"]
}"""
