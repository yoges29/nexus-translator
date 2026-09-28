import logging
import socket
from contextlib import asynccontextmanager

# Prefer IPv4 resolution to prevent dual-stack IPv6 connection aborts on Windows
_original_getaddrinfo = socket.getaddrinfo


def _ipv4_preferred_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        res = _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        if res:
            return res
    except Exception:
        pass
    return _original_getaddrinfo(host, port, family, type, proto, flags)


socket.getaddrinfo = _ipv4_preferred_getaddrinfo

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError, ProviderError
from app.core.logging import configure_logging
from app.database.session import init_db

logger = logging.getLogger("nexus.translator")
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    init_db()
    logger.info("NEXUS Translator backend started")
    yield


app = FastAPI(
    title="NEXUS Translator API",
    description="Multilingual AI translation platform — Stage 3 (Multimodal: Images, Documents & Conversations)",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

settings = get_settings()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

cors_kwargs: dict[str, object] = {
    "allow_origins": settings.cors_origin_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_origin_regex and settings.cors_origin_regex.strip():
    cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex.strip()

app.add_middleware(CORSMiddleware, **cors_kwargs)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_payload_size_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request payload exceeds size limit."})
    return await call_next(request)



@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(ProviderError)
async def provider_error_handler(_: Request, exc: ProviderError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    import uvicorn

    server_port = int(os.environ.get("PORT", os.environ.get("BACKEND_PORT", settings.backend_port)))
    server_host = os.environ.get("BACKEND_HOST", settings.backend_host)
    uvicorn.run("app.main:app", host=server_host, port=server_port)

