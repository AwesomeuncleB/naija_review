"""
evaluate_task_a.py
==================
Runs the Task A system against the test set and computes:
  - RMSE         (rating accuracy)
  - ROUGE-1/2/L  (word overlap between generated and real review)
  - BERTScore F1 (semantic similarity)

How it works:
  1. Loads test_set.json (created by split_test_set.py)
  2. Calls /task-a/batch endpoint with all (user_id, business_id) pairs
  3. Compares predicted ratings + text against ground truth
  4. Prints a full results table and saves results to ./data/eval_task_a.json

Usage:
  python scripts/evaluate_task_a.py \\
      --test  ./data/test_set.json \\
      --api-url http://localhost:8000 \\
      --api-key sk-ant-... \\
      --limit 200 \\
      --batch-size 10

Note: BERTScore downloads a ~400MB model on first run (distilbert-base-uncased).
      Pass --skip-bert to skip it if you have no internet or want faster results.
"""

import json
import math
import argparse
import time
import sys
from pathlib import Path

import requests
import numpy as np
from rouge_score import rouge_scorer

parser = argparse.ArgumentParser()
parser.add_argument("--test",       default="./data/test_set.json")
parser.add_argument("--api-url",    default="http://localhost:8000")
parser.add_argument("--api-key",    default="", help="Anthropic API key")
parser.add_argument("--limit",      type=int, default=200, help="Max pairs to evaluate")
parser.add_argument("--batch-size", type=int, default=10,  help="Pairs per API call")
parser.add_argument("--out",        default="./data/eval_task_a.json")
parser.add_argument("--skip-bert",  action="store_true", help="Skip BERTScore (faster)")
parser.add_argument("--city",       default="Lagos")
args = parser.parse_args()

# ── Load test set ─────────────────────────────────────────────────────────────
test_path = Path(args.test)
if not test_path.exists():
    print(f"ERROR: {test_path} not found. Run split_test_set.py first.")
    sys.exit(1)

with open(test_path) as f:
    test_set = json.load(f)

if args.limit:
    test_set = test_set[:args.limit]

print(f"\n📊  Task A Evaluation")
print(f"   Test pairs  : {len(test_set)}")
print(f"   API URL     : {args.api_url}")
print(f"   Batch size  : {args.batch_size}")
print(f"   BERTScore   : {'disabled' if args.skip_bert else 'enabled'}\n")

# ── Check backend is up ───────────────────────────────────────────────────────
try:
    r = requests.get(f"{args.api_url}/health", timeout=5)
    print(f"   Backend     : ✓ connected ({r.json().get('db_stats', {}).get('reviews', '?')} reviews in DB)")
except Exception:
    print(f"   Backend     : ✗ not reachable at {args.api_url}")
    print("   Start it with: uvicorn backend.main:app --reload")
    sys.exit(1)

# ── Run predictions in batches ────────────────────────────────────────────────
print(f"\n→ Generating predictions...\n")

predictions = []
total       = len(test_set)
pairs       = [{"user_id": t["user_id"], "business_id": t["business_id"]} for t in test_set]

for i in range(0, total, args.batch_size):
    batch = pairs[i : i + args.batch_size]
    pct   = int(100 * i / total)
    bar   = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"\r  [{bar}] {pct}%  ({i}/{total})", end="", flush=True)

    try:
        resp = requests.post(
            f"{args.api_url}/task-a/batch",
            json={"pairs": batch, "city": args.city, "api_key": args.api_key},
            timeout=120,
        )
        data = resp.json()
        predictions.extend(data.get("results", []))
    except Exception as e:
        print(f"\n  ⚠ Batch {i}-{i+args.batch_size} failed: {e}")
        # Add placeholder errors so indices stay aligned
        for _ in batch:
            predictions.append({"error": str(e), "rating": None, "review": ""})

    time.sleep(0.5)  # be gentle on the API

print(f"\r  [{'█'*20}] 100%  ({total}/{total})")
print(f"  ✓ {len(predictions)} predictions received\n")

# ── Align predictions with ground truth ──────────────────────────────────────
# predictions may be in different order — align by user_id + business_id
pred_map = {}
for p in predictions:
    key = (p.get("user_id"), p.get("business_id"))
    pred_map[key] = p

aligned = []
for t in test_set:
    key  = (t["user_id"], t["business_id"])
    pred = pred_map.get(key, {})
    aligned.append({
        "user_id":     t["user_id"],
        "business_id": t["business_id"],
        "true_stars":  t["true_stars"],
        "true_text":   t["true_text"],
        "pred_stars":  pred.get("rating"),
        "pred_text":   pred.get("review", ""),
        "error":       pred.get("error"),
    })

valid = [a for a in aligned if a["pred_stars"] is not None and not a.get("error")]
print(f"  Valid predictions for scoring: {len(valid)}/{len(aligned)}")

if len(valid) == 0:
    print("\n  ERROR: No valid predictions. Check your API key and backend logs.")
    sys.exit(1)

# ── RMSE ──────────────────────────────────────────────────────────────────────
print("\n→ Computing RMSE...")

squared_errors = [(a["pred_stars"] - a["true_stars"]) ** 2 for a in valid]
rmse           = math.sqrt(np.mean(squared_errors))
mae            = np.mean([abs(a["pred_stars"] - a["true_stars"]) for a in valid])

# Per-star-bucket RMSE (shows where the model struggles)
buckets = {1: [], 2: [], 3: [], 4: [], 5: []}
for a in valid:
    buckets[a["true_stars"]].append((a["pred_stars"] - a["true_stars"]) ** 2)
bucket_rmse = {k: math.sqrt(np.mean(v)) if v else None for k, v in buckets.items()}

print(f"   RMSE : {rmse:.4f}")
print(f"   MAE  : {mae:.4f}")

# ── ROUGE ─────────────────────────────────────────────────────────────────────
print("\n→ Computing ROUGE scores...")

scorer  = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
r1, r2, rl = [], [], []

for a in valid:
    scores = scorer.score(a["true_text"], a["pred_text"])
    r1.append(scores["rouge1"].fmeasure)
    r2.append(scores["rouge2"].fmeasure)
    rl.append(scores["rougeL"].fmeasure)

rouge1 = np.mean(r1)
rouge2 = np.mean(r2)
rougeL = np.mean(rl)

print(f"   ROUGE-1 : {rouge1:.4f}")
print(f"   ROUGE-2 : {rouge2:.4f}")
print(f"   ROUGE-L : {rougeL:.4f}")

# ── BERTScore ─────────────────────────────────────────────────────────────────
bert_f1_mean = None
if not args.skip_bert:
    print("\n→ Computing BERTScore (this takes 1-3 minutes)...")
    try:
        from bert_score import score as bert_score_fn
        refs  = [a["true_text"]  for a in valid]
        hyps  = [a["pred_text"]  for a in valid]
        P, R, F1 = bert_score_fn(hyps, refs, lang="en", verbose=False,
                                  model_type="distilbert-base-uncased")
        bert_f1_mean = float(F1.mean())
        print(f"   BERTScore F1 : {bert_f1_mean:.4f}")
    except Exception as e:
        print(f"   BERTScore failed: {e}")
else:
    print("\n→ BERTScore: skipped")

# ── Results table ─────────────────────────────────────────────────────────────
print(f"""
╔══════════════════════════════════════════════╗
║         Task A Evaluation Results            ║
╠══════════════════════════════════════════════╣
║  Pairs evaluated   : {len(valid):>22}  ║
╠══════════════════════════════════════════════╣
║  RATING ACCURACY                             ║
║  RMSE              : {rmse:>22.4f}  ║
║  MAE               : {mae:>22.4f}  ║
╠══════════════════════════════════════════════╣
║  REVIEW TEXT QUALITY                         ║
║  ROUGE-1 F1        : {rouge1:>22.4f}  ║
║  ROUGE-2 F1        : {rouge2:>22.4f}  ║
║  ROUGE-L F1        : {rougeL:>22.4f}  ║""")

if bert_f1_mean is not None:
    print(f"║  BERTScore F1      : {bert_f1_mean:>22.4f}  ║")
else:
    print(f"║  BERTScore F1      : {'(skipped)':>22}  ║")

print(f"""╠══════════════════════════════════════════════╣
║  RMSE BY TRUE STAR RATING                    ║""")
for s, v in bucket_rmse.items():
    if v is not None:
        count = len(buckets[s])
        print(f"║  {s}★ (n={count:>4})         : {v:>22.4f}  ║")
print("╚══════════════════════════════════════════════╝")

# ── Save full results ─────────────────────────────────────────────────────────
output = {
    "summary": {
        "n_evaluated": len(valid),
        "rmse":        round(rmse, 4),
        "mae":         round(mae, 4),
        "rouge1":      round(rouge1, 4),
        "rouge2":      round(rouge2, 4),
        "rougeL":      round(rougeL, 4),
        "bertscore_f1": round(bert_f1_mean, 4) if bert_f1_mean else None,
        "rmse_by_star": {str(k): round(v, 4) if v else None for k, v in bucket_rmse.items()},
    },
    "per_pair": aligned,
}

out_path = Path(args.out)
out_path.parent.mkdir(exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"\n  Full results saved to: {out_path}\n")
