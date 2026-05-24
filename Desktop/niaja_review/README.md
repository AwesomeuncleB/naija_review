# 🇳🇬 NaijaReview Intelligence
### DSN x BCT LLM Agent Hackathon — Task A & B Submission

> *Design agents that understand how people behave, what they want, and what they'll choose next.*

---

## Overview

NaijaReview Intelligence is a dual-task LLM agent system for Nigerian-contextualised user modelling and personalised recommendation. It treats users as dynamic, culturally-embedded agents rather than static preference vectors — built on real Yelp behavioural data with a deep Nigerian cultural intelligence layer.

---

## Architecture

```
Yelp Dataset (7M reviews)
       ↓
 preprocess_yelp.py          ← One-time ETL into SQLite
       ↓
  naijareview.db             ← Users, reviews, businesses + style fingerprints
       ↓
  FastAPI Backend
  ├── /task-a/generate       ← Task A: streaming review generation
  ├── /task-a/batch          ← Task A: batch eval (RMSE/ROUGE)
  └── /task-b/recommend      ← Task B: agentic recommendation
       ↓
  React Frontend             ← Unified UI for both tasks
```

### Key Components

| File | Role |
|---|---|
| `scripts/preprocess_yelp.py` | ETL pipeline — builds SQLite DB from raw Yelp JSON |
| `backend/database.py` | All DB queries — persona fetch, collaborative filter |
| `backend/nigerian_context.py` | Cultural intelligence layer — city profiles, pidgin calibration |
| `backend/task_a.py` | Review generation — prompt engineering + streaming |
| `backend/task_b.py` | ReAct recommendation agent — candidate retrieval + ranking |
| `backend/main.py` | FastAPI app — all endpoints |
| `frontend/src/TaskA.jsx` | Task A UI |
| `frontend/src/TaskB.jsx` | Task B UI with multi-turn conversation |

---

## Setup

### 1. Download Yelp Dataset
Go to [yelp.com/dataset](https://www.yelp.com/dataset), download, and extract into `./data/`:
```
data/
  yelp_academic_dataset_review.json
  yelp_academic_dataset_user.json
  yelp_academic_dataset_business.json
```

### 2. Preprocess (run once, ~10 min)
```bash
pip install -r requirements.txt
python scripts/preprocess_yelp.py --data-dir ./data --db-path ./data/naijareview.db
```
For faster dev testing, cap at 500k reviews:
```bash
python scripts/preprocess_yelp.py --max-reviews 500000
```

### 3. Run Backend
```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn backend.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### 4. Run Frontend
```bash
cd frontend
npm install
npm run dev
# App at http://localhost:5173
```

### 5. Or: Docker (everything in one)
```bash
cp .env.example .env          # add your key
docker-compose up --build
# App + API at http://localhost:8000
```

---

## Task A — User Modeling

**Input:** User persona (from DB or manual) + product/business details  
**Output:** Predicted star rating + written review

### How It Works

1. **Persona Extraction** — Fetches user's last 10 reviews from Yelp DB, computes a style fingerprint (avg words, rating std, dominant topic, tone).

2. **Few-Shot Injection** — Pastes 3–5 of the user's actual past reviews into the Claude prompt as examples. This is the single biggest driver of behavioural fidelity.

3. **Nigerian Context Enrichment** — The `nigerian_context.py` module enriches the prompt with:
   - City-specific behavioural priors (Lagos = hustle + price-sensitivity; Abuja = formal; PH = premium)
   - Category-specific Nigerian consumer concerns
   - Calibrated Pidgin English intensity (none/low/medium/high)

4. **Structured Output** — Claude returns JSON with `rating`, `review`, `tone`, `pidgin_intensity`, `key_praises`, `key_complaints`, `behavioral_notes`.

### Evaluation Endpoints
```bash
# Single review (streaming)
POST /task-a/generate
{"user_id": "abc123", "business_id": "xyz456", "city": "Lagos"}

# Batch eval for RMSE/ROUGE
POST /task-a/batch
{"pairs": [{"user_id": "...", "business_id": "..."}, ...]}
```

---

## Task B — Recommendation Agent

**Input:** User persona + optional conversation history  
**Output:** Ranked recommendations with Nigerian-contextualised explanations

### ReAct Agent Loop

```
THINK  → Analyse user profile, rating patterns, dominant preferences
RETRIEVE → Collaborative filter (similar users' liked businesses)
         + Content filter (category/city search)
REASON → Score candidates: category fit, price alignment, quality signal
RECOMMEND → Return top 5 with persona-specific explanations
MULTI-TURN → Accept follow-up ("more like #2 but cheaper") and re-rank
```

### Cold-Start Handling (25 pts)
When a user has fewer than 3 reviews:
- Falls back to city-level demographic priors
- Asks 1–2 targeted clarifying questions
- Uses Nigerian-context defaults (what typical Lagos users in that age group prefer)

### Conversation
The frontend maintains full conversation history, passed to the agent each turn for progressive refinement.

---

## Nigerian Cultural Intelligence Layer

This is our key differentiator. The system goes beyond English-language user modelling to capture authentic Nigerian consumer behaviour:

| Signal | Implementation |
|---|---|
| **Pidgin English** | Calibrated intensity (none→high) injected via system prompt |
| **City archetypes** | Lagos (hustle/price), Abuja (formal/quality), PH (premium), Kano (value/respect) |
| **Category concerns** | Hotels → NEPA/generator; Electronics → original vs tokunbo; Food → portion/value |
| **Rating calibration** | Nigerian consumers tend to be harsher — model corrects for this |
| **Cultural references** | Jumia, NEPA, go-slow, buka, Danfo, etc. injected contextually |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | DB status + stats |
| `/users` | GET | Browse users (min_reviews filter) |
| `/users/{user_id}` | GET | User profile + recent reviews |
| `/businesses` | GET | Search businesses (category, city, stars) |
| `/task-a/generate` | POST | Generate review (streaming SSE) |
| `/task-a/batch` | POST | Batch evaluation (up to 100 pairs) |
| `/task-b/recommend` | POST | Get recommendations (streaming SSE) |
| `/demo/persona` | GET | Sample persona for dev without DB |

---

## Design Decisions & Tradeoffs

**Why SQLite over Postgres/vector DB?**  
For a hackathon submission, SQLite is zero-dependency, fully portable, and fast enough for the evaluation workload. A production system would use pgvector for the collaborative filtering similarity search.

**Why Claude Sonnet over fine-tuning?**  
Fine-tuning on Yelp reviews would improve ROUGE scores but requires significant compute and time. Few-shot prompting with real user history achieves comparable behavioural fidelity with far less infrastructure — and the Nigerian context layer is prompt-based by necessity (no Nigerian training data exists in standard datasets).

**Why streaming?**  
The demo experience matters for judges. Streaming shows the agent "thinking" in real time, which is both more compelling and better demonstrates the agentic workflow requirement.

**What I'd do with more time:**  
- Fine-tune a small model on Nigerian review data scraped from Jumia, Zomato Nigeria, Google Reviews Lagos
- Add pgvector for true semantic similarity in collaborative filtering
- Build a proper NDCG@10 offline evaluation harness
- Cross-domain: use Amazon + Goodreads datasets to recommend books/products not just restaurants
