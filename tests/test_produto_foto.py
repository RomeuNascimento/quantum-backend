"""Foto do produto (coluna foto, data URL base64).

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_produto_foto.py -v
"""
import pytest

DATA = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA=="


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Foto", "email": "foto@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_produto_foto_crud(client, auth):
    # Cria produto só com nome + foto (componentes vazios são válidos)
    r = client.post("/produtos/", headers=auth, json={
        "nome": "Bolo com foto", "foto": DATA,
        "preparacoes": [], "ingredientes": [], "embalagens": [], "mo_montagem": [],
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["foto"] == DATA

    # GET devolve a foto
    r = client.get(f"/produtos/{pid}", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["foto"] == DATA

    # PUT sem 'foto' no payload → mantém a foto
    r = client.put(f"/produtos/{pid}", headers=auth, json={"nome": "Bolo com foto"})
    assert r.status_code == 200, r.text
    assert r.json()["foto"] == DATA

    # PUT com foto=null → limpa a foto
    r = client.put(f"/produtos/{pid}", headers=auth, json={"nome": "Bolo com foto", "foto": None})
    assert r.status_code == 200, r.text
    assert r.json()["foto"] is None
