"""Application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.router import router
from app.core.config import settings
from app.core.observability import RequestDiagnostics


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(RequestDiagnostics)
    trusted_proxies = [
        item.strip() for item in settings.trusted_proxy_ips.split(",") if item.strip()
    ]
    if trusted_proxies:
        app.add_middleware(
            ProxyHeadersMiddleware, trusted_hosts=trusted_proxies
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
