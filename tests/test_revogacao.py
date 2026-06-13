"""Revogação de JWT: /auth/logout (jti denylist), /auth/logout-all e
/auth/alterar-senha (token_version). Roda em sqlite in-memory:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_revogacao.py -v
"""


def _registrar(client, email, senha="senha12345"):
    r = client.post("/auth/register", json={"nome": "U", "email": email, "senha": senha})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_logout_revoga_token_atual(client):
    token = _registrar(client, "logout@test.com")
    assert client.get("/auth/me", headers=_h(token)).status_code == 200

    assert client.post("/auth/logout", headers=_h(token)).status_code == 204
    # Mesmo token agora é rejeitado
    assert client.get("/auth/me", headers=_h(token)).status_code == 401

    # Novo login emite token válido
    r = client.post("/auth/login", json={"email": "logout@test.com", "senha": "senha12345"})
    assert r.status_code == 200, r.text
    assert client.get("/auth/me", headers=_h(r.json()["access_token"])).status_code == 200


def test_logout_all_derruba_todas_sessoes(client):
    token = _registrar(client, "logoutall@test.com")
    # Segunda sessão (outro dispositivo) com o mesmo usuário
    token2 = client.post(
        "/auth/login", json={"email": "logoutall@test.com", "senha": "senha12345"}
    ).json()["access_token"]
    assert client.get("/auth/me", headers=_h(token2)).status_code == 200

    assert client.post("/auth/logout-all", headers=_h(token)).status_code == 204
    # Ambos os tokens (emitidos antes do bump) ficam inválidos
    assert client.get("/auth/me", headers=_h(token)).status_code == 401
    assert client.get("/auth/me", headers=_h(token2)).status_code == 401


def test_alterar_senha_exige_senha_atual_correta(client):
    token = _registrar(client, "senha@test.com", senha="senhaAntiga1")
    r = client.post("/auth/alterar-senha", headers=_h(token), json={
        "senha_atual": "errada123", "senha_nova": "senhaNova123",
    })
    assert r.status_code == 400, r.text


def test_alterar_senha_troca_e_derruba_sessoes(client):
    token = _registrar(client, "troca@test.com", senha="senhaAntiga1")
    # Sessão paralela que deve cair após a troca
    token2 = client.post(
        "/auth/login", json={"email": "troca@test.com", "senha": "senhaAntiga1"}
    ).json()["access_token"]

    r = client.post("/auth/alterar-senha", headers=_h(token), json={
        "senha_atual": "senhaAntiga1", "senha_nova": "senhaNova123",
    })
    assert r.status_code == 200, r.text
    novo_token = r.json()["access_token"]

    # Token novo funciona; tokens antigos (token e token2) caem
    assert client.get("/auth/me", headers=_h(novo_token)).status_code == 200
    assert client.get("/auth/me", headers=_h(token)).status_code == 401
    assert client.get("/auth/me", headers=_h(token2)).status_code == 401

    # Login só com a senha nova
    assert client.post(
        "/auth/login", json={"email": "troca@test.com", "senha": "senhaAntiga1"}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"email": "troca@test.com", "senha": "senhaNova123"}
    ).status_code == 200


def test_token_sem_tv_continua_valido(client):
    """Retrocompat: token antigo (sem claim `tv`) é aceito enquanto o usuário
    estiver na token_version 0."""
    from app.auth.utils import criar_token

    _registrar(client, "retro@test.com")
    # Descobre o id do usuário recém-criado via login + /auth/me
    token = client.post(
        "/auth/login", json={"email": "retro@test.com", "senha": "senha12345"}
    ).json()["access_token"]
    user_id = client.get("/auth/me", headers=_h(token)).json()["id"]

    legado = criar_token({"sub": str(user_id)})  # sem `tv`
    assert client.get("/auth/me", headers=_h(legado)).status_code == 200
