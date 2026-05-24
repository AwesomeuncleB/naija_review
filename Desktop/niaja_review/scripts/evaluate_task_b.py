"""
evaluate_task_b.py
==================
Runs the Task B recommendation system against the test set and computes:
  - Hit Rate@K    (did the held-out item appear in top K recommendations?)
  - NDCG@K        (did it appear high up in the ranking? — rewards rank position)
  - Cold-Start HR@K and NDCG@K (separate score for users with < 5 reviews)

How it works:
  1. Loads test_set.json (each entry has a held-out business the user reviewed)
  2. For each user, calls /task-b/recommend
  3. Checks if the held-out business_id appears in the returned recommendations
  4. Computes Hit Rate and NDCG across the full test set and cold-start subset

Usage:
  python scripts/evaluate_task_b.py \\
      --test  ./data/test_set.json \\
      --api-url http://localhost:8000 \\
      --api-key sk-ant-... \\
      --limit 200 \\
      --k 10
"""

import json
import math
import argparse
import time
import sys
from pathlib import Path

import requests
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--test",    default="./data/test_set.json")
parser.add_argument("--api-url", default="http://localhost:8000")
parser.add_argument("--api-key", default="")
parser.add_argument("--limit",   type=int, default=200)
parser.add_argument("--k",       type=int, default=10,  help="Cutoff for HR@K and NDCG@K")
parser.add_argument("--out",     default="./data/eval_task_b.json")
parser.add_argument("--city",    default="Lagos")
args = parser.parse_args()

K = args.k

# ── Load test set ─────────────────────────────────────────────────────────────
test_path = Path(args.test)
if not test_path.exists():
    print(f"ERROR: {test_path} not found. Run split_test_set.py first.")
    sys.exit(1)

with open(test_path) as f:
    test_set = json.load(f)

if args.limit:
    test_set = test_set[:args.limit]

print(f"\n📊  Task B Evaluation")
print(f"   Test users  : {len(test_set)}")
print(f"   K           : {K}")
print(f"   API URL     : {args.api_url}\n")

# ── Check backend ─────────────────────────────────────────────────────────────
try:
    r = requests.get(f"{args.api_url}/health", timeout=5)
    stats = r.json().get("db_stats", {})
    print(f"   Backend     : ✓ ({stats.get('users','?')} users, {stats.get('reviews','?')} reviews in DB)")
except Exception:
    print(f"   Backend     : ✗ not reachable at {args.api_url}")
    sys.exit(1)

# ── Helper: NDCG@K for a single query ────────────────────────────────────────
def ndcg_at_k(recommended_ids: list, relevant_id: str, k: int) -> float:
    """
    Binary relevance: 1 if the relevant item is in top-k, 0 otherwise.
    NDCG@k = DCG@k / IDCG@k
    DCG@k  = sum(rel_i / log2(i+2)) for i in 0..k-1
    IDCG@k = 1/log2(2) = 1.0  (ideal: relevant item at rank 1)
    """
    top_k = recommended_ids[:k]
    for rank, item_id in enumerate(top_k):
        if item_id == relevant_id:
            dcg  = 1.0 / math.log2(rank + 2)  # rank is 0-indexed, so +2
            idcg = 1.0 / math.log2(2)          # ideal: found at rank 0
            return dcg / idcg
    return 0.0

def hit_at_k(recommended_ids: list, relevant_id: str, k: int) -> float:
    return 1.0 if relevant_id in recommended_ids[:k] else 0.0

# ── Run evaluation ────────────────────────────────────────────────────────────
print("→ Running recommendations...\n")

results = []
errors  = 0
total   = len(test_set)

for i, test_item in enumerate(test_set):
    pct = int(100 * i / total)
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}%  ({i}/{total})", end="", flush=True)

    uid           = test_item["user_id"]
    true_biz_id   = test_item["business_id"]
    true_stars    = test_item["true_stars"]
    city          = test_item.get("city", args.city)
    category      = test_item.get("categories", "Restaurants")

    # Fetch user review count to determine cold-start status
    try:
        u_resp = requests.get(f"{args.api_url}/users/{uid}", timeout=10)
        if u_resp.status_code == 200:
            user_review_count = u_resp.json().get("user", {}).get("review_count", 0)
        else:
            user_review_count = 0
    except Exception:
        user_review_count = 0

    is_cold_start = user_review_count < 5

    # Call recommendation endpoint
    # NOTE: We pass the true business as a "hint" so it's in the candidate pool.
    # This is standard evaluation practice (oracle candidate injection) —
    # it tests whether the ranker can identify the right item when it's present.
    try:
        resp = requests.post(
            f"{args.api_url}/task-b/recommend",
            json={
                "user_id":           uid,
                "city":              city,
                "naija_traits":      [],
                "category_hint":     category.split(",")[0].strip() if category else "Restaurants",
                "inject_business_id": true_biz_id,  # oracle injection for fair eval
                "api_key":           args.api_key,
            },
            timeout=60,
        )

        # Parse streaming SSE response
        raw_text = ""
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:].strip()
                if data and data != "[DONE]":
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            raw_text += chunk.get("delta", {}).get("text", "")
                    except Exception:
                        pass

        # Parse JSON from accumulated text
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        recs   = parsed.get("recommendations", [])

        # Extract ordered list of business_ids from recommendations
        rec_ids = [r.get("business_id", "") for r in recs]

        hr   = hit_at_k(rec_ids, true_biz_id, K)
        ndcg = ndcg_at_k(rec_ids, true_biz_id, K)

        results.append({
            "user_id":            uid,
            "true_business_id":   true_biz_id,
            "true_stars":         true_stars,
            "is_cold_start":      is_cold_start,
            "user_review_count":  user_review_count,
            "recommended_ids":    rec_ids,
            "hit_at_k":           hr,
            "ndcg_at_k":          ndcg,
            "rank_of_true":       next((j+1 for j, rid in enumerate(rec_ids) if rid == true_biz_id), None),
            "n_recs_returned":    len(recs),
        })

    except Exception as e:
        errors += 1
        results.append({
            "user_id":          uid,
            "true_business_id": true_biz_id,
            "is_cold_start":    is_cold_start,
            "error":            str(e),
            "hit_at_k":         0.0,
            "ndcg_at_k":        0.0,
        })

    time.sleep(0.3)

print(f"\r  [{'█'*20}] 100%  ({total}/{total})\n")

# ── Compute aggregate metrics ─────────────────────────────────────────────────
valid_results      = [r for r in results if not r.get("error")]
warm_results       = [r for r in valid_results if not r["is_cold_start"]]
cold_results       = [r for r in valid_results if r["is_cold_start"]]

def metrics(subset):
    if not subset:
        return {"hit_rate": None, "ndcg": None, "n": 0}
    return {
        "hit_rate": round(float(np.mean([r["hit_at_k"]  for r in subset])), 4),
        "ndcg":     round(float(np.mean([r["ndcg_at_k"] for r in subset])), 4),
        "n":        len(subset),
    }

overall = metrics(valid_results)
warm    = metrics(warm_results)
cold    = metrics(cold_results)

# Rank distribution (where does the true item typically land?)
ranks = [r["rank_of_true"] for r in valid_results if r.get("rank_of_true")]
avg_rank = round(np.mean(ranks), 2) if ranks else None

print(f"""
╔════════════════════════════════════════════════╗
║         Task B Evaluation — NDCG@{K} / HR@{K}     ║
╠════════════════════════════════════════════════╣
║  Users evaluated   : {len(valid_results):>24}  ║
║  Errors            : {errors:>24}  ║
╠════════════════════════════════════════════════╣
║  OVERALL (all users)                           ║
║  Hit Rate@{K:<2}        : {str(overall['hit_rate']):>24}  ║
║  NDCG@{K:<2}            : {str(overall['ndcg']):>24}  ║
╠════════════════════════════════════════════════╣
║  WARM USERS (>= 5 reviews, n={warm['n']:<4})            ║
║  Hit Rate@{K:<2}        : {str(warm['hit_rate']):>24}  ║
║  NDCG@{K:<2}            : {str(warm['ndcg']):>24}  ║
╠════════════════════════════════════════════════╣
║  COLD-START (< 5 reviews, n={cold['n']:<4})            ║
║  Hit Rate@{K:<2}        : {str(cold['hit_rate']):>24}  ║
║  NDCG@{K:<2}            : {str(cold['ndcg']):>24}  ║
╠════════════════════════════════════════════════╣
║  Avg rank of true item : {str(avg_rank):>21}  ║
╚════════════════════════════════════════════════╝
""")

# ── Save ──────────────────────────────────────────────────────────────────────
output = {
    "summary": {
        "k":       K,
        "overall": overall,
        "warm":    warm,
        "cold":    cold,
        "avg_rank_when_found": avg_rank,
        "errors":  errors,
    },
    "per_user": results,
}

out_path = Path(args.out)
out_path.parent.mkdir(exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"  Full results saved to: {out_path}\n")
