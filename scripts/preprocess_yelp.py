"""
preprocess_yelp.py
==================
Run ONCE after downloading the Yelp dataset.
Builds a SQLite database optimised for fast persona lookups.

Usage:
    python scripts/preprocess_yelp.py --data-dir ./data --db-path ./data/naijareview.db

Time: ~10-15 minutes on a normal laptop
Output: naijareview.db (~800MB)
"""

import json
import sqlite3
import argparse
import os
import sys
import time
from pathlib import Path
from collections import defaultdict
import re

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", default="./data", help="Folder with Yelp JSON files")
parser.add_argument("--db-path", default="./data/naijareview.db", help="Output SQLite path")
parser.add_argument("--max-reviews", type=int, default=None, help="Cap for dev (e.g. 500000)")
parser.add_argument("--min-reviews-per-user", type=int, default=10, help="Min reviews to include a user")
args = parser.parse_args()

DATA_DIR = Path(args.data_dir)
DB_PATH  = Path(args.db_path)

# ── Helpers ───────────────────────────────────────────────────────────────────
def progress(msg, n=None, total=None):
    if n and total:
        pct = int(100 * n / total)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct}%  {msg}  ({n:,}/{total:,})", end="", flush=True)
    else:
        print(f"\n→ {msg}", flush=True)

def count_lines(path):
    """Fast line count via wc -l or Python fallback."""
    try:
        import subprocess
        r = subprocess.run(["wc", "-l", str(path)], capture_output=True, text=True)
        return int(r.stdout.strip().split()[0])
    except Exception:
        count = 0
        with open(path, "rb") as f:
            for _ in f:
                count += 1
        return count

def extract_style_fingerprint(reviews: list[dict]) -> dict:
    """
    Derive a writing-style fingerprint from a user's review history.
    Used for behavioural fidelity scoring.
    """
    if not reviews:
        return {}

    texts = [r["text"] for r in reviews]
    ratings = [r["stars"] for r in reviews]

    avg_words = sum(len(t.split()) for t in texts) / len(texts)
    avg_rating = sum(ratings) / len(ratings)
    rating_std = (sum((r - avg_rating)**2 for r in ratings) / len(ratings)) ** 0.5

    # Common keywords (cheap heuristic for topic preference)
    all_words = " ".join(texts).lower()
    topic_keywords = {
        "food": ["food", "taste", "delicious", "bland", "flavour", "flavor", "spicy", "menu"],
        "service": ["service", "staff", "waiter", "rude", "friendly", "slow", "quick"],
        "price": ["price", "expensive", "cheap", "value", "worth", "overpriced", "affordable"],
        "ambiance": ["ambiance", "atmosphere", "vibe", "noisy", "cozy", "dirty", "clean"],
    }
    topic_scores = {}
    for topic, words in topic_keywords.items():
        topic_scores[topic] = sum(all_words.count(w) for w in words)

    dominant_topic = max(topic_scores, key=topic_scores.get)

    # Sentiment words
    positive_words = ["great", "amazing", "love", "excellent", "wonderful", "best", "fantastic"]
    negative_words = ["terrible", "horrible", "awful", "worst", "bad", "disappointing", "never"]
    pos_count = sum(all_words.count(w) for w in positive_words)
    neg_count = sum(all_words.count(w) for w in negative_words)
    tone = "positive" if pos_count > neg_count else "negative" if neg_count > pos_count else "balanced"

    return {
        "avg_words_per_review": round(avg_words, 1),
        "avg_rating": round(avg_rating, 2),
        "rating_std": round(rating_std, 2),
        "dominant_topic": dominant_topic,
        "tone": tone,
        "review_count": len(reviews),
    }

# ── Build DB ──────────────────────────────────────────────────────────────────
def build_database():
    progress("Creating SQLite database...")
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=-64000;

        CREATE TABLE IF NOT EXISTS businesses (
            business_id   TEXT PRIMARY KEY,
            name          TEXT,
            city          TEXT,
            state         TEXT,
            categories    TEXT,
            stars         REAL,
            review_count  INTEGER,
            attributes    TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id           TEXT PRIMARY KEY,
            review_count      INTEGER,
            avg_stars         REAL,
            useful_votes      INTEGER,
            funny_votes       INTEGER,
            cool_votes        INTEGER,
            style_fingerprint TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            review_id    TEXT PRIMARY KEY,
            user_id      TEXT,
            business_id  TEXT,
            stars        INTEGER,
            text         TEXT,
            date         TEXT,
            useful       INTEGER DEFAULT 0,
            funny        INTEGER DEFAULT 0,
            cool         INTEGER DEFAULT 0,
            FOREIGN KEY (user_id)      REFERENCES users(user_id),
            FOREIGN KEY (business_id)  REFERENCES businesses(business_id)
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_user     ON reviews(user_id);
        CREATE INDEX IF NOT EXISTS idx_reviews_business ON reviews(business_id);
        CREATE INDEX IF NOT EXISTS idx_reviews_stars    ON reviews(stars);
        CREATE INDEX IF NOT EXISTS idx_business_city    ON businesses(city);
        CREATE INDEX IF NOT EXISTS idx_business_cat     ON businesses(categories);
    """)
    conn.commit()
    return conn, cur

def load_businesses(cur, conn):
    path = DATA_DIR / "yelp_academic_dataset_business.json"
    if not path.exists():
        print(f"\n⚠ Business file not found at {path}. Skipping.")
        return set()

    progress("Loading businesses...")
    total = count_lines(path)
    business_ids = set()
    batch = []

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                b = json.loads(line)
                batch.append((
                    b["business_id"],
                    b.get("name", ""),
                    b.get("city", ""),
                    b.get("state", ""),
                    b.get("categories", ""),
                    b.get("stars", 0),
                    b.get("review_count", 0),
                    json.dumps(b.get("attributes") or {}),
                ))
                business_ids.add(b["business_id"])
                if len(batch) >= 5000:
                    cur.executemany("INSERT OR IGNORE INTO businesses VALUES (?,?,?,?,?,?,?,?)", batch)
                    conn.commit()
                    batch = []
                progress("businesses", i, total)
            except (json.JSONDecodeError, KeyError):
                continue

    if batch:
        cur.executemany("INSERT OR IGNORE INTO businesses VALUES (?,?,?,?,?,?,?,?)", batch)
        conn.commit()

    print(f"\n  ✓ {len(business_ids):,} businesses loaded")
    return business_ids

def load_users(cur, conn):
    path = DATA_DIR / "yelp_academic_dataset_user.json"
    if not path.exists():
        print(f"\n⚠ User file not found at {path}. Skipping.")
        return set()

    progress("Loading users (filtering by min reviews)...")
    total = count_lines(path)
    valid_users = set()
    batch = []

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                u = json.loads(line)
                if u.get("review_count", 0) < args.min_reviews_per_user:
                    continue
                batch.append((
                    u["user_id"],
                    u.get("review_count", 0),
                    u.get("average_stars", 0),
                    u.get("useful", 0),
                    u.get("funny", 0),
                    u.get("cool", 0),
                    "{}",  # fingerprint filled in later
                ))
                valid_users.add(u["user_id"])
                if len(batch) >= 5000:
                    cur.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)", batch)
                    conn.commit()
                    batch = []
                progress("users", i, total)
            except (json.JSONDecodeError, KeyError):
                continue

    if batch:
        cur.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)", batch)
        conn.commit()

    print(f"\n  ✓ {len(valid_users):,} qualifying users loaded")
    return valid_users

def load_reviews(cur, conn, valid_users, business_ids):
    path = DATA_DIR / "yelp_academic_dataset_review.json"
    if not path.exists():
        print(f"\n⚠ Review file not found at {path}. Skipping.")
        return

    progress("Loading reviews...")
    total = count_lines(path)
    if args.max_reviews:
        total = min(total, args.max_reviews)

    batch = []
    loaded = 0
    skipped = 0

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if args.max_reviews and i > args.max_reviews:
                break
            try:
                r = json.loads(line)
                uid = r.get("user_id")
                bid = r.get("business_id")
                # Only load reviews for users and businesses we care about
                if uid not in valid_users:
                    skipped += 1
                    continue
                batch.append((
                    r["review_id"],
                    uid,
                    bid,
                    r.get("stars", 3),
                    r.get("text", ""),
                    r.get("date", ""),
                    r.get("useful", 0),
                    r.get("funny", 0),
                    r.get("cool", 0),
                ))
                loaded += 1
                if len(batch) >= 10000:
                    cur.executemany("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", batch)
                    conn.commit()
                    batch = []
                progress("reviews", i, total)
            except (json.JSONDecodeError, KeyError):
                continue

    if batch:
        cur.executemany("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", batch)
        conn.commit()

    print(f"\n  ✓ {loaded:,} reviews loaded ({skipped:,} skipped — users filtered out)")

def compute_style_fingerprints(cur, conn):
    """
    For each user, fetch their reviews and compute a style fingerprint.
    This is used at inference time to calibrate the LLM prompt.
    """
    progress("Computing style fingerprints (this takes a few minutes)...")

    cur.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cur.fetchall()]
    total = len(user_ids)

    for i, uid in enumerate(user_ids, 1):
        cur.execute(
            "SELECT stars, text FROM reviews WHERE user_id=? ORDER BY date DESC LIMIT 20",
            (uid,)
        )
        rows = cur.fetchall()
        reviews = [{"stars": r[0], "text": r[1]} for r in rows]
        fp = extract_style_fingerprint(reviews)
        cur.execute(
            "UPDATE users SET style_fingerprint=? WHERE user_id=?",
            (json.dumps(fp), uid)
        )
        if i % 10000 == 0:
            conn.commit()
            progress("fingerprints", i, total)

    conn.commit()
    print(f"\n  ✓ Style fingerprints computed for {total:,} users")

def print_summary(cur):
    cur.execute("SELECT COUNT(*) FROM businesses")
    b = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM reviews")
    r = cur.fetchone()[0]

    print(f"""
╔══════════════════════════════════════╗
║     NaijaReview DB — Build Complete  ║
╠══════════════════════════════════════╣
║  Businesses : {b:>20,}  ║
║  Users      : {u:>20,}  ║
║  Reviews    : {r:>20,}  ║
║  DB Path    : {str(DB_PATH):<20}  ║
╚══════════════════════════════════════╝
""")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start = time.time()
    print("\n🇳🇬  NaijaReview — Yelp Preprocessor\n")

    if not DATA_DIR.exists():
        print(f"ERROR: data directory not found at {DATA_DIR}")
        sys.exit(1)

    conn, cur = build_database()
    business_ids = load_businesses(cur, conn)
    valid_users  = load_users(cur, conn)
    load_reviews(cur, conn, valid_users, business_ids)
    compute_style_fingerprints(cur, conn)
    print_summary(cur)

    conn.close()
    elapsed = time.time() - start
    print(f"⏱  Total time: {elapsed/60:.1f} minutes\n")
