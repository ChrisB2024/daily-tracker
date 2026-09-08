import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.routers import goals, rep_types, reps, summary, debrief, history
from app.scheduler import init_scheduler, scheduler

# Nothing configured logging, so app loggers emitted nothing under uvicorn's
# default handlers — converting the scheduler's print() calls to logging would
# otherwise have made the resolved job fire times invisible, which is the one
# signal that catches a timezone regression.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="Daily Tracker", version="0.1.0")

# Open origins, no credentials. allow_origins=["*"] with allow_credentials=True
# is a combination browsers reject outright, so the credentials flag never did
# anything; the config now states what actually happens. The API is deliberately
# unauthenticated (architecture.md, security invariant 2), so there is no cookie
# or auth header to protect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
