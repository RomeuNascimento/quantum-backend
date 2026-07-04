"""Recuperação de senha: /auth/esqueci-senha e /auth/redefinir-senha.

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_reset_senha.py -v
"""
import pytest

import app.auth.router as auth_router


def _registrar(client, email, senha="senha12345"):
    r = client.post("/auth/register", json={"nome": "Maria", "email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _zera_reset_limiter():
    """O limite é 3 pedidos/hora por IP — os testes deste módulo passam disso."""
    auth_router._reset_limiter._hits.clear()
    yield


@pytest.fixture
def captura_email(monkeypatch):
    """Intercepta enviar_email e captura o link do corpo (não manda nada)."""
    enviados = []

    def fake(destinatario, assunto, corpo_html):
        enviados.append({"para": destinatario, "assunto": assunto, "html": corpo_html})
        return True

    monkeypatch.setattr(auth_router, "enviar_email", fake)
    return enviados


def _token_do_email(html):
    # link: .../redefinir-senha?token=XXX"
    inicio = html.index("token=") + len("token=")
    fim = html.index('"', inicio)
    return html[inicio:fim]


def test_fluxo_completo_reset(client, captura_email):
    _registrar(client, "reset@test.com", "senhaVelha1")

    # pede o link
    r = client.post("/auth/esqueci-senha", json={"email": "reset@test.com"})
    assert r.status_code == 200
    assert len(captura_email) == 1
    assert captura_email[0]["para"] == "reset@test.com"
    token = _token_do_email(captura_email[0]["html"])

    # redefine e já sai logado
    r = client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "senhaNova1"})
    assert r.status_code == 200, r.text
    sessao = r.json()["access_token"]
    assert client.get("/auth/me", headers=_h(sessao)).status_code == 200

    # senha velha morreu, nova funciona
    assert client.post("/auth/login", json={"email": "reset@test.com", "senha": "senhaVelha1"}).status_code == 401
    assert client.post("/auth/login", json={"email": "reset@test.com", "senha": "senhaNova1"}).status_code == 200


def test_email_inexistente_resposta_identica(client, captura_email):
    """Anti-enumeração: resposta 200 igual, nenhum e-mail enviado."""
    r = client.post("/auth/esqueci-senha", json={"email": "naoexiste@test.com"})
    assert r.status_code == 200
    assert captura_email == []


def test_link_e_uso_unico(client, captura_email):
    _registrar(client, "unico@test.com")
    client.post("/auth/esqueci-senha", json={"email": "unico@test.com"})
    token = _token_do_email(captura_email[0]["html"])

    assert client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "outraSenha1"}).status_code == 200
    # segunda vez: token_version mudou → 400 amigável
    r = client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "maisOutra1"})
    assert r.status_code == 400
    assert "link" in r.json()["detail"].lower()


def test_reset_derruba_sessoes_antigas(client, captura_email):
    token_sessao = _registrar(client, "derruba@test.com")
    client.post("/auth/esqueci-senha", json={"email": "derruba@test.com"})
    token = _token_do_email(captura_email[0]["html"])
    client.post("/auth/redefinir-senha", json={"token": token, "nova_senha": "novaSenha1"})
    # sessão antiga (pré-reset) morreu — quem achou o celular perdido ficou de fora
    assert client.get("/auth/me", headers=_h(token_sessao)).status_code == 401


def test_token_reset_nao_serve_como_sessao(client, captura_email):
    """O token do link tem purpose=reset e não pode autenticar chamadas."""
    _registrar(client, "purpose@test.com")
    client.post("/auth/esqueci-senha", json={"email": "purpose@test.com"})
    token = _token_do_email(captura_email[0]["html"])
    assert client.get("/auth/me", headers=_h(token)).status_code == 401


def test_token_lixo_da_400_amigavel(client):
    r = client.post("/auth/redefinir-senha", json={"token": "lixo.invalido.aqui", "nova_senha": "senhaBoa123"})
    assert r.status_code == 400
    assert "link" in r.json()["detail"].lower()
