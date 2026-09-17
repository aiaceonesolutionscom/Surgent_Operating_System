import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.server.middleware import setup_middleware, ALLOWED_ORIGINS
from src.server.exceptions import AppException
from src.router.agents import register_routes
from src.services.channels.green_api_poller import GreenAPIPoller
from src.services.recovery.post_op_followup_poller import PostOpFollowUpPoller
from src.services.leads.lead_nurturing_poller import LeadNurturingPoller

settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("aesthetixai")

poller = GreenAPIPoller()
post_op_poller = PostOpFollowUpPoller()
lead_nurturing_poller = LeadNurturingPoller()


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        # Medical SaaS: deliberately do NOT capture user PII (request headers,
        # IPs, form bodies). send_default_pii=False keeps patient data out of
        # Sentry even though the default snippet suggests otherwise.
        send_default_pii=False,
        traces_sample_rate=0.1,
    )
    logger.info("Sentry initialized (environment=%s)", settings.app_env)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_sentry()
    poller.start()
    logger.info("Green API poller started on app startup")
    post_op_poller.start()
    logger.info("Post-op follow-up poller started on app startup")
    lead_nurturing_poller.start()
    logger.info("Lead nurturing poller started on app startup")
    try:
        yield
    finally:
        poller.stop()
        logger.info("Green API poller stopped")
        post_op_poller.stop()
        logger.info("Post-op follow-up poller stopped")
        lead_nurturing_poller.stop()
        logger.info("Lead nurturing poller stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

setup_middleware(app)
register_routes(app)


def _with_cors(request, response: JSONResponse) -> JSONResponse:
    # Confirmed (via a minimal FastAPI+CORSMiddleware+exception_handler repro
    # with no other custom code involved) that Starlette's CORSMiddleware
    # never adds Access-Control-Allow-Origin to a response built by a
    # registered `@app.exception_handler` — this is a general framework
    # limitation, not something specific to this app's middleware or DB
    # setup. Without this, the browser reports "blocked by CORS policy"
    # instead of surfacing whatever the real error was underneath.
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return _with_cors(request, JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    ))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return _with_cors(request, JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    ))


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
