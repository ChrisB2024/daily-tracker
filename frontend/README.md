# Daily Tracker Frontend

React + Vite frontend for the Daily Tracker app.

## Setup

Install dependencies:
```bash
npm install
```

## Running the Frontend

Start the dev server:
```bash
npm run dev
```

This opens the app at `http://localhost:5173/`

The frontend automatically proxies API requests to `http://localhost:8001/` (backend).

## Build

Build for production:
```bash
npm run build
```

## Prerequisites

Make sure the backend is running on port 8001:
```bash
cd ../backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8001
```

Otherwise API calls will fail with "Failed to fetch" errors.
