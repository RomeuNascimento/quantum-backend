"""Fixtures compartilhadas: TestClient com banco limpo por módulo.

O engine vive em tests/db.py (módulo neutro) para que os testes possam
importar TestingSession sem reimportar este conftest.
"""
import pytest
from fastapi.testclient import TestClient

from tests.db import engine, TestingSession
from app.database import Base, get_db
from app.main import app


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
