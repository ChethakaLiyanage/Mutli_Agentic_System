"""FastAPI entry point for the Claim Intake Agent service."""

from fastapi import FastAPI

from backend.app.api.intake import router as intake_router


app = FastAPI(
    title="Claim Intake Agent API",
    version="1.0.0",
)
app.include_router(intake_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Return a lightweight service availability response."""

    return {
        "status": "ok",
        "service": "claim-intake-agent",
    }
