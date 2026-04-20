"""FastAPI application factory for the Mini App backend.

Creates a FastAPI app that serves both the REST API and the static
webapp files. The orchestrator is injected as a dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.api.routes import router, set_orchestrator, set_session_factory

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from server.orchestrator.game_loop import GameOrchestrator

# Path to the webapp/ directory (project root / webapp)
_WEBAPP_DIR = Path(__file__).resolve().parent.parent.parent / "webapp"


def create_api_app(
    orchestrator: GameOrchestrator,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        orchestrator: The game orchestrator holding all game state.
        session_factory: Optional SQLAlchemy session factory. When provided,
            it is stored on the orchestrator for database-backed persistence.

    Returns:
        A fully configured FastAPI app ready to run.
    """
    if session_factory is not None:
        orchestrator.session_factory = session_factory
        set_session_factory(session_factory)
    app = FastAPI(
        title="RPG Mini App API",
        description="REST API for the Telegram Mini App game client.",
        version="0.1.0",
    )

    # CORS — allow Telegram WebApp origin (any origin for local dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Inject orchestrator into route handlers
    set_orchestrator(orchestrator)

    # Mount API routes
    app.include_router(router)

    # Mount static files for the webapp
    if _WEBAPP_DIR.is_dir():
        app.mount(
            "/app", StaticFiles(directory=str(_WEBAPP_DIR), html=True), name="app"
        )

    return app
