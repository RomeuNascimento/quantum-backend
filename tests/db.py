"""Engine sqlite in-memory único para a suíte — importado pelo conftest e
por testes que precisam manipular o banco diretamente (ex: forçar status de
assinatura). Não pode morar no conftest.py: importá-lo como `tests.conftest`
criaria um segundo módulo (e um segundo engine) além do que o pytest carrega.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
