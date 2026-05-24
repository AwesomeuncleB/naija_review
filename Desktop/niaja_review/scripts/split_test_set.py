"""
split_test_set.py
=================
Creates a reproducible train/test split from the Yelp SQLite database.

Strategy: Leave-One-Out (LOO)
  - For each user with >= 10 reviews, hold out their MOST RECENT review
    as the ground truth test item.
  - The remaining reviews stay in the "training" set (used for persona building).

This is the standard evaluation protocol for recommendation and review
generation systems — it simulates predicting something the user will
write/rate in the future, given their past.

Output files (saved to ./data/):
  test_set.json     — list of {user_id, business_id, true_stars, true_text, ...}
  train_ids.json    — set of review_ids excluded from persona building

Usage:
  python scripts/split_test_set.py --db ./data/naijareview.db --limit 1000
"""

import sqlite3
import json
import argparse
import random
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--db",    default="./data/naijareview.db")
parser.add_argument("--out",   default="./data")
parser.add_argument("--limit", type=int, default=1000,  help="Max test users (keeps runtime manageable)")
parser.add_argument("--min-reviews", type=int, default=10)
parser.add_argument("--seed",  type=int, default=42)
args = parser.parse_args()

random.seed(args.seed)
DB   = Path(args.db)
OUT  = Path(args.out)
OUT.mkdir(exist_ok=True)

if not DB.exists():
    print(f"ERROR: DB not found at {DB}")
    print("Run scripts/preprocess_yelp.py first.")
    raise SystemExit(1)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

print("\n🔪  Building test split...")

# ── 1. Find qualifying users ──────────────────────────────────────────────────
cur.execute("""
    SELECT user_id, review_count
    FROM users
    WHERE review_count >= ?
    ORDER BY review_count DESC
""", (args.min_reviews,))

all_users = [dict(r) for r in cur.fetchall()]
print(f"   Qualifying users (>= {args.min_reviews} reviews): {len(all_users):,}")

# Sample down to limit
if len(all_users) > args.limit:
    all_users = random.sample(all_users, args.limit)
    print(f"   Sampled down to: {args.limit:,} users")

# ── 2. For each user, grab their most recent review as the test item ──────────
test_set     = []
held_out_ids = set()
skipped      = 0

for i, user in enumerate(all_users):
    uid = user["user_id"]

    # Most recent review = test item
    cur.execute("""
        SELECT r.review_id, r.user_id, r.business_id, r.stars, r.text, r.date,
               b.name as business_name, b.categories, b.city, b.stars as biz_stars
        FROM reviews r
        LEFT JOIN businesses b ON r.business_id = b.business_id
        WHERE r.user_id = ?
        ORDER BY r.date DESC
        LIMIT 1
    """, (uid,))
    row = cur.fetchone()
    if not row:
        skipped += 1
        continue

    r = dict(row)

    # Verify user has enough remaining reviews for persona building
    cur.execute("SELECT COUNT(*) FROM reviews WHERE user_id=? AND review_id != ?", (uid, r["review_id"]))
    remaining = cur.fetchone()[0]
    if remaining < 5:
        skipped += 1
        continue

    test_set.append({
        "user_id":       r["user_id"],
        "business_id":   r["business_id"],
        "business_name": r["business_name"] or "Unknown",
        "categories":    r["categories"] or "General",
        "city":          r["city"] or "Lagos",
        "biz_stars":     r["biz_stars"] or 3.5,
        "true_stars":    r["stars"],
        "true_text":     r["text"],
        "date":          r["date"],
        "held_review_id": r["review_id"],
        "is_cold_start": False,
    })
    held_out_ids.add(r["review_id"])

    if (i + 1) % 100 == 0:
        print(f"   Processed {i+1}/{len(all_users)} users...", end="\r")

# ── 2b. Add cold-start users (1-4 reviews) — worth 25 pts ────────────────────
print(f"\n   Adding cold-start users (1-4 reviews)...")

cur.execute("""
    SELECT user_id, review_count
    FROM users
    WHERE review_count BETWEEN 1 AND 4
    ORDER BY RANDOM()
    LIMIT ?
""", (min(200, args.limit // 5),))

cold_users = [dict(r) for r in cur.fetchall()]
cold_added = 0
for user in cold_users:
    uid = user["user_id"]
    cur.execute("""
        SELECT r.review_id, r.user_id, r.business_id, r.stars, r.text, r.date,
               b.name as business_name, b.categories, b.city, b.stars as biz_stars
        FROM reviews r
        LEFT JOIN businesses b ON r.business_id = b.business_id
        WHERE r.user_id = ?
        ORDER BY r.date DESC
        LIMIT 1
    """, (uid,))
    row = cur.fetchone()
    if not row:
        continue
    r = dict(row)
    if not r.get("text") or len(r["text"]) < 20:
        continue
    test_set.append({
        "user_id":        r["user_id"],
        "business_id":    r["business_id"],
        "business_name":  r["business_name"] or "Unknown",
        "categories":     r["categories"] or "General",
        "city":           r["city"] or "Lagos",
        "biz_stars":      r["biz_stars"] or 3.5,
        "true_stars":     r["stars"],
        "true_text":      r["text"],
        "date":           r["date"],
        "held_review_id": r["review_id"],
        "is_cold_start":  True,
    })
    cold_added += 1

print(f"   ✓ {cold_added} cold-start users added")

# ── 3. Save ───────────────────────────────────────────────────────────────────
test_path  = OUT / "test_set.json"
train_path = OUT / "held_out_review_ids.json"

with open(test_path, "w") as f:
    json.dump(test_set, f, indent=2)

with open(train_path, "w") as f:
    json.dump(list(held_out_ids), f)

conn.close()

# ── 4. Summary ────────────────────────────────────────────────────────────────
stars_dist = {}
for item in test_set:
    s = item["true_stars"]
    stars_dist[s] = stars_dist.get(s, 0) + 1

avg_len = sum(len(t["true_text"].split()) for t in test_set) / max(len(test_set), 1)

print(f"""
╔══════════════════════════════════════════╗
║         Test Split — Complete            ║
╠══════════════════════════════════════════╣
║  Test pairs created : {len(test_set):>18,}  ║
║  Users skipped      : {skipped:>18,}  ║
║  Avg review length  : {avg_len:>15.1f} words  ║
╠══════════════════════════════════════════╣
║  Star distribution:                      ║""")
for s in sorted(stars_dist):
    bar = "█" * int(stars_dist[s] / max(stars_dist.values()) * 20)
    print(f"║  {s}★  {bar:<20} {stars_dist[s]:>5}  ║")
print(f"""╠══════════════════════════════════════════╣
║  Saved: {str(test_path):<33}  ║
╚══════════════════════════════════════════╝
""")
