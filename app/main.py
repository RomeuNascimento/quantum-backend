import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quantum")
from app.database import get_settings
from app.auth.router import router as auth_router
from app.routers.ingredientes import router as ingredientes_router
from app.routers.embalagens import router as embalagens_router
from app.routers.receitas import router as receitas_router
from app.routers.produtos import router as produtos_router
from app.routers.precificacao import router as precificacao_router
from app.routers.custos_fixos import router as custos_fixos_router
from app.routers.colaboradores import router as colaboradores_router
from app.routers.ia import router as ia_router
from app.routers.billing import router as billing_router, require_assinatura_ativa

settings = get_settings()

app = FastAPI(
    title="Quantum API",
    description="API para gestão de custos e precificação para confeiteiros",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Erro não tratado em %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno no servidor. Tente novamente mais tarde."},
    )


_paywall = [Depends(require_assinatura_ativa)]

app.include_router(auth_router)
app.include_router(ingredientes_router, dependencies=_paywall)
app.include_router(embalagens_router, dependencies=_paywall)
app.include_router(receitas_router, dependencies=_paywall)
app.include_router(produtos_router, dependencies=_paywall)
app.include_router(precificacao_router, dependencies=_paywall)
app.include_router(custos_fixos_router, dependencies=_paywall)
app.include_router(colaboradores_router, dependencies=_paywall)
app.include_router(ia_router, dependencies=_paywall)
app.include_router(billing_router)


@app.get("/health")
def health():
    return {"status": "ok", "servico": "Quantum API"}
