from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 30
    allow_origins: str = "https://quantumcalc.com.br"
    enable_docs: bool = False  # Swagger/ReDoc/OpenAPI expostos só se True (default: off em produção)
    # Rate limit distribuído: se vazio, usa memória (só vale com 1 worker).
    redis_url: str = ""
    # E-mail transacional (recuperação de senha). Sem SMTP configurado, o
    # endpoint /auth/esqueci-senha responde 200 mas não envia nada (loga aviso).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    frontend_url: str = "https://quantumcalc.com.br"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
