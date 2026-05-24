"""
diagnose.py — run this from your niaja_review/ project root.
It checks every possible failure point in 10 seconds.

Usage:
    python diagnose.py
"""
import os, sys, json
from pathlib import Path

print("\n🔍  NaijaReview Diagnostic\n" + "="*40)

# 1. API Key
key = os.getenv("ANTHROPIC_API_KEY", "")
if not key:
    # Try loading .env manually
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY"):
                key = line.split("=", 1)[-1].strip().strip('"').strip("'")
                break

if key:
    print(f"✅  ANTHROPIC_API_KEY found: {key[:20]}...")
else:
    print("❌  ANTHROPIC_API_KEY not set — this is why nothing works!")
    print("    Fix: add ANTHROPIC_API_KEY=sk-ant-... to your .env file")

# 2. Database
db_paths = [
    Path("data/naijareview.db"),
    Path("./data/naijareview.db"),
    Path("backend/../data/naijareview.db"),
]
db_found = None
for p in db_paths:
    if p.exists():
        db_found = p
        break

if db_found:
    import sqlite3
    conn = sqlite3.connect(db_found)
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    businesses = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    conn.close()
    print(f"✅  Database found: {db_found}")
    print(f"    Users: {users:,} | Reviews: {reviews:,} | Businesses: {businesses:,}")
    if users < 100:
        print(f"⚠️   Only {users} users — preprocessing may not have finished")
else:
    print("❌  Database not found at data/naijareview.db")
    print("    Fix: run python scripts/preprocess_yelp.py")

# 3. Backend imports
print("\n--- Checking backend imports ---")
sys.path.insert(0, ".")
try:
    from backend.nigerian_context import build_persona_context, is_nigerian_city, build_system_prompt_task_b
    print("✅  nigerian_context.py imports OK")
    # Check the function signature has business_city param
    import inspect
    sig = inspect.signature(build_persona_context)
    if "business_city" in sig.parameters:
        print("✅  build_persona_context has business_city param (v2 fix applied)")
    else:
        print("❌  build_persona_context is MISSING business_city param — old version!")
        print("    Fix: replace backend/nigerian_context.py with the fixed version")
except ImportError as e:
    print(f"❌  Import error: {e}")
    print("    Run this script from the niaja_review/ root directory")

try:
    from backend.task_a import generate_review_stream, predict_rating
    print("✅  task_a.py imports OK")
except ImportError as e:
    print(f"❌  task_a.py import error: {e}")

try:
    from backend.task_b import get_recommendations_stream
    print("✅  task_b.py imports OK")
except ImportError as e:
    print(f"❌  task_b.py import error: {e}")

try:
    from backend.database import db_stats
    stats = db_stats()
    print(f"✅  database.py imports OK — DB exists: {stats['db_exists']}")
except Exception as e:
    print(f"❌  database.py error: {e}")

# 4. Backend running?
print("\n--- Checking if backend is running ---")
try:
    import urllib.request
    with urllib.request.urlopen("http://localhost:8000/health", timeout=3) as r:
        data = json.loads(r.read())
        print(f"✅  Backend running at :8000")
        print(f"    DB stats: {data.get('db_stats', {})}")
except Exception:
    print("❌  Backend NOT running at localhost:8000")
    print("    Fix: uvicorn backend.main:app --reload --port 8000")

# 5. Frontend pointing to right URL?
print("\n--- Checking frontend files ---")
for fname in ["frontend/src/TaskA.jsx", "frontend/src/TaskB.jsx"]:
    p = Path(fname)
    if p.exists():
        content = p.read_text()
        if "api_key: apiKey" in content or "apiKey" in content:
            print(f"❌  {fname} still has old apiKey code — replace with fixed version")
        else:
            print(f"✅  {fname} looks clean (no apiKey in request body)")
    else:
        print(f"⚠️   {fname} not found (may be in different location)")

print("\n" + "="*40)
print("Done. Fix any ❌ items above and restart the backend.\n")
