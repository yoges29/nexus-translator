# Development Guide

## Prerequisites

- Node.js 20+
- Python 3.12+
- PostgreSQL 16+ (or Docker Compose)
- LibreTranslate API key (recommended for local translation tests)

## Initial setup

```bash
cp .env.example .env
# Edit .env — set TRANSLATION_API_KEY at minimum
```

## Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run from `backend/` so `PYTHONPATH` resolves to `app`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Tests

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run test
```

## Docker Compose

From repository root:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## Adding languages

Edit `shared/languages.json` only. Both backend validation and frontend selectors consume this file.

## Translation provider

Set in `.env`:

```env
TRANSLATION_PROVIDER=libretranslate
TRANSLATION_API_KEY=your_key
TRANSLATION_API_URL=https://libretranslate.com
```

Obtain a key from your LibreTranslate host (the public instance requires a key).

Alternative:

```env
TRANSLATION_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Install `google-cloud-translate` when using Google.
