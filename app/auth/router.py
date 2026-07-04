from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db, get_settings
from app.email import enviar_email
from app.models.models import User, Configuracao, Canal, RevokedToken, Ingrediente, UnidadeEnum
from app.auth.schemas import (
    UserCreate, UserLogin, Token, UserOut, ConfiguracaoOut, ConfiguracaoUpdate,
    AlterarSenha, EsqueciSenha, RedefinirSenha,
)
from app.auth.utils import (
    hash_senha, verificar_senha, criar_token_usuario, criar_token_reset,
    get_usuario_atual, decodificar_token, oauth2_scheme,
)
from app.ratelimit import RateLimiter

router = APIRouter(prefix="/auth", tags=["Autenticação"])

_login_limiter = RateLimiter(10, 300, "Muitas tentativas de login. Aguarde alguns minutos.")
_register_limiter = RateLimiter(5, 3600, "Muitas contas criadas a partir deste endereço. Tente mais tarde.")
_reset_limiter = RateLimiter(3, 3600, "Muitos pedidos de recuperação. Tente novamente mais tarde.")


def _ip(request: Request) -> str:
    # Atrás do reverse proxy (EasyPanel/Traefik), client.host é o IP do proxy —
    # todos os clientes cairiam no mesmo bucket de rate limit. O proxy ANEXA o
    # IP real ao fim do X-Forwarded-For, então o último valor é o único que ele
    # garante (os anteriores podem ser forjados pelo cliente).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "desconhecido"


# Hash dummy verificado quando o e-mail não existe: iguala o tempo de resposta
# de "usuário inexistente" e "senha errada" (anti-enumeração por timing)
_DUMMY_HASH = hash_senha("timing-equalizer-nao-e-senha-real")


# Mensagem deliberadamente vaga: não confirma que o e-mail existe na base
# (anti-enumeração). O rate limit por IP impede varredura mesmo assim.
_MSG_REGISTRO_INDISPONIVEL = "Não foi possível criar a conta com estes dados. Verifique o e-mail ou faça login."


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def registrar(dados: UserCreate, request: Request, db: Session = Depends(get_db)):
    _register_limiter.checar(_ip(request))
    if db.query(User).filter(User.email == dados.email).first():
        raise HTTPException(status_code=400, detail=_MSG_REGISTRO_INDISPONIVEL)

    user = User(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
    )
    db.add(user)
    db.flush()

    # Configuração padrão
    configuracao = Configuracao(user_id=user.id, valor_hora_padrao=0.0)
    db.add(configuracao)

    # Canal iFood pré-cadastrado
    ifood = Canal(
        user_id=user.id,
        nome="iFood",
        taxa_plataforma_pct=12.0,
        taxa_cartao_pct=2.99,
        imposto_pct=6.0,
        ativo=True,
    )
    db.add(ifood)

    # Água: ingrediente neutro (sem preço → custo 0), já vem pronto
    db.add(Ingrediente(
        user_id=user.id, nome="Água", unidade=UnidadeEnum.ml, fator_correcao=1.0, ativo=True,
    ))
    try:
        db.commit()
    except IntegrityError:
        # Race no check-then-insert: dois registers simultâneos do mesmo e-mail
        db.rollback()
        raise HTTPException(status_code=400, detail=_MSG_REGISTRO_INDISPONIVEL)
    db.refresh(user)

    return Token(access_token=criar_token_usuario(user))


@router.post("/login", response_model=Token)
def login(dados: UserLogin, request: Request, db: Session = Depends(get_db)):
    _login_limiter.checar(_ip(request))
    user = db.query(User).filter(User.email == dados.email).first()
    senha_ok = verificar_senha(dados.senha, user.senha_hash if user else _DUMMY_HASH)
    if not user or not senha_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    return Token(access_token=criar_token_usuario(user))


# Mensagem única (o e-mail existindo ou não) — anti-enumeração.
_MSG_RESET_ENVIADO = (
    "Se este e-mail estiver cadastrado, enviamos um link para criar uma senha nova. "
    "Olhe sua caixa de entrada e o spam."
)


def _email_reset_html(nome: str, link: str) -> str:
    primeiro_nome = (nome or "").split(" ")[0] or "confeiteiro(a)"
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
      <h2 style="color: #0B0B0F;">Quantum</h2>
      <p style="font-size: 16px; color: #0B0B0F;">Oi, {primeiro_nome}!</p>
      <p style="font-size: 16px; color: #0B0B0F;">
        Você pediu para criar uma <strong>senha nova</strong> no Quantum.
        É só apertar o botão abaixo:
      </p>
      <p style="margin: 28px 0;">
        <a href="{link}" style="background: #D6FF3F; color: #0B0B0F; padding: 14px 28px;
           text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">
          CRIAR SENHA NOVA
        </a>
      </p>
      <p style="font-size: 14px; color: #5A584F;">
        O link vale por 30 minutos. Se não foi você que pediu, pode ignorar
        este e-mail — sua senha continua a mesma.
      </p>
    </div>
    """


@router.post("/esqueci-senha")
def esqueci_senha(
    dados: EsqueciSenha,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Envia (em background) o link de redefinição. Resposta idêntica com e-mail
    existente ou não — não revela quem tem conta (anti-enumeração)."""
    _reset_limiter.checar(_ip(request))
    user = db.query(User).filter(User.email == dados.email).first()
    if user:
        settings = get_settings()
        link = f"{settings.frontend_url.rstrip('/')}/redefinir-senha?token={criar_token_reset(user)}"
        background.add_task(
            enviar_email, user.email, "Quantum — criar senha nova", _email_reset_html(user.nome, link)
        )
    return {"detail": _MSG_RESET_ENVIADO}


@router.post("/redefinir-senha", response_model=Token)
def redefinir_senha(dados: RedefinirSenha, db: Session = Depends(get_db)):
    """Troca a senha a partir do token do e-mail (uso único, expira em 30min)
    e já devolve uma sessão nova — a pessoa entra direto, sem redigitar."""
    token_invalido = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Este link já foi usado ou venceu. Peça um novo em 'Esqueci minha senha'.",
    )
    try:
        payload = decodificar_token(dados.token)
    except HTTPException:
        raise token_invalido  # mensagem amigável no lugar do 401 genérico
    if payload.get("purpose") != "reset":
        raise token_invalido
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise token_invalido
    user = db.query(User).filter(User.id == user_id).first()
    # tv desatualizado = senha já trocada depois da emissão (link de uso único)
    if user is None or payload.get("tv", 0) != user.token_version:
        raise token_invalido

    user.senha_hash = hash_senha(dados.nova_senha)
    user.token_version += 1  # derruba sessões antigas E invalida este token
    db.commit()
    db.refresh(user)
    return Token(access_token=criar_token_usuario(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Revoga o token atual (logout deste dispositivo) adicionando o jti à
    denylist. Idempotente; aproveita para expurgar tokens já expirados."""
    payload = decodificar_token(token)  # 401 se inválido/expirado
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        ja_revogado = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
        if not ja_revogado:
            db.add(RevokedToken(
                jti=jti,
                user_id=int(payload.get("sub")),
                expira_em=datetime.utcfromtimestamp(exp),
            ))
        # Expurgo oportunista: entradas expiradas já não bloqueiam nada.
        db.query(RevokedToken).filter(RevokedToken.expira_em < datetime.utcnow()).delete()
        db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: User = Depends(get_usuario_atual), db: Session = Depends(get_db)):
    """Derruba TODAS as sessões do usuário (todos os dispositivos) bumpando o
    token_version — qualquer token emitido antes deixa de ser aceito."""
    user.token_version += 1
    db.commit()


@router.post("/alterar-senha", response_model=Token)
def alterar_senha(
    dados: AlterarSenha,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    """Troca a senha e derruba todas as outras sessões (bump em token_version).
    Devolve um token novo para o dispositivo atual seguir logado."""
    if not verificar_senha(dados.senha_atual, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    user.senha_hash = hash_senha(dados.senha_nova)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return Token(access_token=criar_token_usuario(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_usuario_atual)):
    return user


@router.get("/configuracao", response_model=ConfiguracaoOut)
def get_configuracao(
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    return user.configuracao


@router.put("/configuracao", response_model=ConfiguracaoOut)
def atualizar_configuracao(
    dados: ConfiguracaoUpdate,
    user: User = Depends(get_usuario_atual),
    db: Session = Depends(get_db),
):
    config = user.configuracao
    config.valor_hora_padrao = dados.valor_hora_padrao
    db.commit()
    db.refresh(config)
    return config
