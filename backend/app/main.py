from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import Base, engine
from app.routers import auth, conversation, topics, progress


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(topics.router)
    app.include_router(progress.router)
    app.include_router(conversation.router)

    @app.on_event("startup")
    async def on_startup() -> None:
        # Import models so SQLAlchemy registers them before create_all
        import app.models.user  # noqa: F401
        import app.models.conversation  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
