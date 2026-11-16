# Brand Performance Manager — React Front End

A React + Vite + TypeScript single-page app that replaces the former Streamlit UI. It
talks to the FastAPI backend (`../app/server.py`) over a small JSON API and renders KPI
tiles, Plotly charts, and the two-phase Human-in-the-Loop AI Advisor.

## Develop

```bash
npm install
# Run the backend in another terminal:  (from ../app)  uvicorn server:app --port 8000
npm run dev          # Vite dev server on :5173, proxies /api → :8000
```

## Build (required before deploy)

Databricks Apps cannot run `npm` at deploy time, so the compiled assets are committed
under `../app/static` and served by FastAPI.

```bash
npm run build        # → ../app/static (index.html + assets/)
```

Commit the regenerated `app/static` whenever the UI changes, then deploy the bundle:

```bash
cd ..  &&  databricks bundle deploy --target dev
```

## Structure

```
frontend/
├── index.html
├── vite.config.ts          outDir → ../app/static ; dev proxy /api → :8000
├── src/
│   ├── main.tsx
│   ├── App.tsx             shell + sidebar nav + shared enriched-context state
│   ├── styles.css          NovaLife navy/orange design system
│   ├── lib/api.ts          typed client for the FastAPI backend
│   └── components/
│       ├── Dashboard.tsx       KPI tiles + share-trend + insurgent charts
│       ├── Advisor.tsx         AI chat + two-phase HITL routing gate
│       ├── Insurgent.tsx       insurgent brand table + threat chart
│       ├── Distribution.tsx    ACV distribution table + chart
│       ├── Chart.tsx           Plotly wrappers
│       └── common.tsx          context pills, notices, loading
```
