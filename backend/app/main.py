"""FastAPI entry point for the motor-insurance multi-agent backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.api.intake import router as intake_router
from backend.app.api.orchestrator import router as orchestrator_router


app = FastAPI(
    title="Claim Intake Agent API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(intake_router)
app.include_router(auth_router)
app.include_router(orchestrator_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return a lightweight service availability response."""

    return {
        "status": "ok",
        "service": "claim-intake-agent",
    }
