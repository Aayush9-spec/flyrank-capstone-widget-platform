from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter
from app.core.body_limit import BodySizeLimitMiddleware
from app.api.widgets import router as widgets_router
from app.api.auth import router as auth_router
from app.api.public import router as public_router
from app.api.submissions import router as submissions_router
from app.api.dashboard import router as dashboard_router
from app.core.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant embeddable widget and lead-capture platform",
    version="1.0.0",
)

@app.middleware("http")
async def widget_cache_headers(request, call_next):
    response = await call_next(request)

    if request.url.path.startswith("/widget/v1/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    return response


app.mount(
    "/widget/v1",
    StaticFiles(directory="widget"),
    name="widget-v1",
)

app.add_middleware(BodySizeLimitMiddleware, max_body_size=65536)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "FlyRank Widget Platform API",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


app.include_router(auth_router)
app.include_router(widgets_router)
app.include_router(public_router)
app.include_router(submissions_router)
app.include_router(dashboard_router)
