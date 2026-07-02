from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import goals, rep_types, reps, summary, debrief, history
from app.scheduler import init_scheduler, scheduler

app = FastAPI(title="Daily Tracker", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(goals.router)
app.include_router(rep_types.router)
app.include_router(reps.router)
app.include_router(summary.router)
app.include_router(debrief.router)
app.include_router(history.router)


@app.on_event("startup")
async def startup():
    init_scheduler()


@app.on_event("shutdown")
async def shutdown():
    if scheduler.running:
        scheduler.shutdown()


@app.get("/healthz")
async def healthz():
    """Liveness probe. Useful for confirming the server is up before debugging deeper issues."""
    return {"status": "ok"}
