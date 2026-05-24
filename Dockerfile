# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + serve frontend static files ─────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./static

# Data directory (bind-mounted at runtime)
RUN mkdir -p /app/data

# Serve static frontend from FastAPI
RUN pip install --no-cache-dir aiofiles==23.2.1

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
