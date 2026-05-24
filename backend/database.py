"""
database.py
===========
All SQLite queries for NaijaReview.
Provides fast persona lookups, review history fetching,
and item retrieval for both Task A and Task B.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from functools import lru_cache

DB_PATH = Path("./data/demo.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn

_conn: Optional[sqlite3.Connection] = None

def db():
    global _conn
    if _conn is None:
        _conn = get_conn()
    return _conn


# ── User queries ──────────────────────────────────────────────────────────────

def get_user(user_id: str) -> Optional[dict]:
    cur = db().execute(
        "SELECT * FROM users WHERE user_id=?", (user_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["style_fingerprint"] = json.loads(d.get("style_fingerprint") or "{}")
    return d


def get_user_reviews(user_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch a user's most recent reviews with business names attached.
    Used to build few-shot examples for Task A.
    """
    cur = db().execute("""
        SELECT r.review_id, r.stars, r.text, r.date,
               b.name as business_name, b.categories, b.city
        FROM reviews r
        LEFT JOIN businesses b ON r.business_id = b.business_id
        WHERE r.user_id = ?
        ORDER BY r.date DESC
        LIMIT ?
    """, (user_id, limit))
    return [dict(row) for row in cur.fetchall()]


def get_user_rated_businesses(user_id: str) -> set:
    """Return set of business_ids this user has already reviewed."""
    cur = db().execute(
        "SELECT business_id FROM reviews WHERE user_id=?", (user_id,)
    )
    return {row[0] for row in cur.fetchall()}


def search_users(min_reviews: int = 10, limit: int = 50) -> list[dict]:
    """Browse users — useful for the frontend user picker."""
    cur = db().execute("""
        SELECT user_id, review_count, avg_stars, style_fingerprint
        FROM users
        WHERE review_count >= ?
        ORDER BY review_count DESC
        LIMIT ?
    """, (min_reviews, limit))
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["style_fingerprint"] = json.loads(r.get("style_fingerprint") or "{}")
    return rows


# ── Business queries ──────────────────────────────────────────────────────────

def get_business(business_id: str) -> Optional[dict]:
    cur = db().execute(
        "SELECT * FROM businesses WHERE business_id=?", (business_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["attributes"] = json.loads(d.get("attributes") or "{}")
    return d


def search_businesses(
    category: Optional[str] = None,
    city: Optional[str] = None,
    min_stars: float = 0.0,
    limit: int = 20,
    search: Optional[str] = None,
) -> list[dict]:
    """
    Find businesses matching filters.
    Used by Task B to build candidate recommendation sets.
    """
    query = "SELECT * FROM businesses WHERE stars >= ?"
    params: list = [min_stars]

    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    if category:
        query += " AND categories LIKE ?"
        params.append(f"%{category}%")
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")

    query += " ORDER BY review_count DESC LIMIT ?"
    params.append(limit)

    cur = db().execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["attributes"] = json.loads(r.get("attributes") or "{}")
    return rows


def get_similar_users(user_id: str, limit: int = 10) -> list[dict]:
    """
    Find users with similar rating behaviour — used for collaborative filtering
    in Task B cold-start scenarios.
    """
    user = get_user(user_id)
    if not user:
        return []

    avg = user.get("avg_stars", 3.0)
    fp  = user.get("style_fingerprint", {})
    topic = fp.get("dominant_topic", "food")

    cur = db().execute("""
        SELECT u.user_id, u.avg_stars, u.review_count, u.style_fingerprint
        FROM users u
        WHERE u.user_id != ?
          AND ABS(u.avg_stars - ?) < 0.5
          AND u.review_count >= 10
          AND u.style_fingerprint LIKE ?
        ORDER BY ABS(u.avg_stars - ?) ASC
        LIMIT ?
    """, (user_id, avg, f'%"{topic}"%', avg, limit))

    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["style_fingerprint"] = json.loads(r.get("style_fingerprint") or "{}")
    return rows


def get_top_businesses_for_similar_users(similar_user_ids: list[str], exclude_ids: set, limit: int = 20) -> list[dict]:
    """
    Collaborative filtering step: find businesses that similar users loved,
    that the target user hasn't tried yet.
    """
    if not similar_user_ids:
        return []

    placeholders = ",".join("?" * len(similar_user_ids))
    exclude_list = list(exclude_ids) if exclude_ids else ["__none__"]
    ex_placeholders = ",".join("?" * len(exclude_list))

    cur = db().execute(f"""
        SELECT b.business_id, b.name, b.categories, b.city, b.stars, b.review_count,
               AVG(r.stars) as collab_score,
               COUNT(r.review_id) as endorsement_count
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        WHERE r.user_id IN ({placeholders})
          AND r.stars >= 4
          AND r.business_id NOT IN ({ex_placeholders})
        GROUP BY b.business_id
        ORDER BY endorsement_count DESC, collab_score DESC
        LIMIT ?
    """, (*similar_user_ids, *exclude_list, limit))

    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        r["attributes"] = {}
    return rows


# ── Stats / health ────────────────────────────────────────────────────────────

def db_stats() -> dict:
    cur = db()
    def count(table):
        return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {
        "businesses": count("businesses"),
        "users": count("users"),
        "reviews": count("reviews"),
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
    }
