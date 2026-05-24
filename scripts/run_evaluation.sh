#!/usr/bin/env bash
# ── NaijaReview Full Evaluation Pipeline ──────────────────────────────────────
# Run from naijareview/ project root with venv active.
# Usage:
#   bash scripts/run_evaluation.sh sk-ant-YOUR-KEY          # fast (no BERTScore)
#   bash scripts/run_evaluation.sh sk-ant-YOUR-KEY --bert   # full (downloads 400MB model)
# ─────────────────────────────────────────────────────────────────────────────

API_KEY=${1:-""}
BERT_FLAG="--skip-bert"
if [ "${2}" = "--bert" ]; then BERT_FLAG=""; fi

if [ -z "$API_KEY" ]; then
  echo "Usage: bash scripts/run_evaluation.sh sk-ant-YOUR-KEY [--bert]"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  NaijaReview — Evaluation Pipeline       ║"
echo "╚══════════════════════════════════════════╝"

# ── Step 1: Install eval deps ─────────────────────────────────────────────────
echo ""
echo "→ [1/4] Installing evaluation deps..."
pip install rouge-score numpy requests --quiet
if [ -z "$BERT_FLAG" ]; then
  pip install bert-score torch transformers --quiet
fi
echo "  ✓ Done"

# ── Step 2: Build test split ──────────────────────────────────────────────────
echo ""
echo "→ [2/4] Building test split from Yelp DB..."
python scripts/split_test_set.py \
  --db    ./data/naijareview.db \
  --out   ./data \
  --limit 500 \
  --min-reviews 10

# ── Step 3: Task A evaluation ─────────────────────────────────────────────────
echo ""
echo "→ [3/4] Task A — RMSE + ROUGE${BERT_FLAG:+ (BERTScore skipped)}..."
echo "  Evaluating 50 pairs (~15 mins). Raise --limit for more thorough eval."
python scripts/evaluate_task_a.py \
  --test       ./data/test_set.json \
  --api-url    http://localhost:8000 \
  --api-key    "$API_KEY" \
  --limit      50 \
  --batch-size 5 \
  --out        ./data/eval_task_a.json \
  $BERT_FLAG

# ── Step 4: Task B evaluation ─────────────────────────────────────────────────
echo ""
echo "→ [4/4] Task B — NDCG@10 + Hit Rate..."
python scripts/evaluate_task_b.py \
  --test    ./data/test_set.json \
  --api-url http://localhost:8000 \
  --api-key "$API_KEY" \
  --limit   100 \
  --out     ./data/eval_task_b.json

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Done! Results in:                       ║"
echo "║  data/eval_task_a.json  (RMSE/ROUGE)     ║"
echo "║  data/eval_task_b.json  (NDCG/HitRate)   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Put those numbers in your Solution Paper!"
