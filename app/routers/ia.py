import base64
import json
import os
import threading
import time
from collections import defaultdict

import anthropic
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.utils import get_usuario_atual
from app.models.models import User

router = APIRouter(prefix="/ia", tags=["IA"])

UNIDADES_VALIDAS = {"g", "kg", "ml", "L", "unid"}

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# Rate limit em memória (1 worker uvicorn) — protege os créditos da API Anthropic
RATE_LIMIT_CHAMADAS = 10
RATE_LIMIT_JANELA_S = 600
_chamadas_por_usuario: dict = defaultdict(list)
_rate_lock = threading.Lock()


def _checar_rate_limit(user_id: int):
    agora = time.time()
    with _rate_lock:
        recentes = [t for t in _chamadas_por_usuario[user_id] if agora - t < RATE_LIMIT_JANELA_S]
        if len(recentes) >= RATE_LIMIT_CHAMADAS:
            raise HTTPException(
                status_code=429,
                detail="Limite de importações via IA atingido. Tente novamente em alguns minutos.",
            )
        recentes.append(agora)
        _chamadas_por_usuario[user_id] = recentes


def _ler_upload(file: UploadFile) -> bytes:
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo muito grande (máximo 15 MB).")
    if not content:
        raise HTTPException(status_code=422, detail="Arquivo vazio.")
    return content

PROMPT_NOTA = """Você é um extrator de itens de nota fiscal. Analise a imagem e extraia os produtos.

REGRAS — NOME:
- Retorne o nome genérico e canônico, sem marca, sem gramagem, sem código fiscal, sem abreviações
- Ex: "CHOCOLATE MID DKT 200G" → "chocolate meio amargo"
- Ex: "MANTEIGA AVIACAO TAB 200G" → "manteiga sem sal"
- Ex: "ACUCAR UNIAO REFINADO 1KG" → "açúcar refinado"
- Ex: "FARINHA TRIGO ESP 1KG" → "farinha de trigo"
- Ex: "OVO GRADE M C/12" → "ovo"
- A especificação só entra se muda o produto: "sem sal", "integral", "meio amargo"
- Se não conseguir identificar, use o texto original em nome_original e nome: null

REGRAS — MARCA:
- Extraia a marca comercial separada (ex: "Nestlé", "Aviação", "União") ou null

REGRAS — PESO DA EMBALAGEM:
- O peso/volume está no nome do produto, não no campo de quantidade da nota
- Ex: "CHOCOLATE MID DKT 200G" → peso_embalagem_g: 200
- Ex: "FARINHA TRIGO ESP 1KG" → peso_embalagem_g: 1000
- Ex: "LEITE UHT TP 1L" → peso_embalagem_g: 1000
- Se não houver peso no nome → peso_embalagem_g: null

REGRAS — QUANTIDADE E PREÇO:
- quantidade: número de embalagens compradas (não o peso; ex: comprou 2 pacotes → 2)
- preco_unitario: preço de UMA embalagem (R$)
- preco_total: total pago pelo item (R$)

Inclua TODOS os itens da nota. Retorne SOMENTE JSON válido, sem markdown:

{"data_compra": "YYYY-MM-DD", "itens": [{"nome": "chocolate meio amargo", "nome_original": "CHOCOLATE MID DKT 200G", "marca": "Harald", "peso_embalagem_g": 200, "quantidade": 2, "unidade": "g", "preco_unitario": 5.99, "preco_total": 11.98}]}

Use null para data_compra se não visível. Use null para peso_embalagem_g se o peso não constar no nome."""

PROMPT_RECEITAS = """Você é um extrator de receitas culinárias. Analise o documento e extraia todas as receitas presentes.

REGRAS — NOME DO INGREDIENTE:
- Retorne o nome genérico e canônico, sem marca, sem forma de preparo, sem adjetivos desnecessários
- Ex: "chocolate meio amargo picado" → "chocolate meio amargo"
- Ex: "manteiga sem sal em cubos" → "manteiga sem sal"
- Ex: "ovos grandes em temperatura ambiente" → "ovo"
- Ex: "farinha de trigo peneirada" → "farinha de trigo"
- A especificação só entra se muda o ingrediente: "sem sal", "integral", "meio amargo"

REGRAS — QUANTIDADE (sempre em gramas ou ml como número):
- Converta tudo para a unidade base:
  1 kg → 1000 | 1 xícara chá → 240 | 1 xícara café → 60
  1 colher sopa → 15 | 1 colher chá → 5 | 1 copo → 200
  1 ovo → 50 | 1 limão → 80 | 1 pitada → 2
- Registre o texto original em unidade_original (ex: "2 xícaras", "3 colheres sopa")

REGRAS — RENDIMENTO:
- rendimento_g: peso estimado do produto final em gramas
- Se informa porções sem peso → estime 150-200g por porção individual
- Se não informado → estime pelo peso total dos ingredientes × 0.9

Retorne SOMENTE JSON válido, sem markdown:

{"receitas": [{"nome": "Bolo de Chocolate", "tipo": "Massa", "rendimento_g": 800, "ingredientes": [{"nome": "farinha de trigo", "quantidade_g": 200, "unidade_original": "2 xícaras"}], "etapas_mo": [{"descricao": "Misture os ingredientes secos", "tempo_min": 5}]}]}"""


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY não configurada no servidor.")
    return anthropic.Anthropic(api_key=key)


def _model():
    return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")


def _parse(resp) -> dict:
    if not resp.content or not hasattr(resp.content[0], "text"):
        raise HTTPException(status_code=422, detail="A IA retornou uma resposta vazia. Tente novamente.")
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def _image_block(content: bytes, media_type: str) -> dict:
    b64 = base64.standard_b64encode(content).decode()
    if "pdf" in media_type:
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
    mt = media_type if media_type in {"image/jpeg", "image/png", "image/gif", "image/webp"} else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}


# Endpoints síncronos (def) de propósito: o FastAPI os despacha para o
# threadpool, então a chamada à API Anthropic (30-90s) não trava o event loop.
@router.post("/nota-fiscal")
def processar_nota_fiscal(
    file: UploadFile = File(...),
    user: User = Depends(get_usuario_atual),
):
    _checar_rate_limit(user.id)
    content = _ler_upload(file)
    block = _image_block(content, file.content_type or "image/jpeg")
    try:
        resp = _client().messages.create(
            model=_model(),
            max_tokens=4096,
            messages=[{"role": "user", "content": [block, {"type": "text", "text": PROMPT_NOTA}]}],
        )
        data = _parse(resp)
        # Normalise units
        for item in data.get("itens", []):
            if item.get("unidade") not in UNIDADES_VALIDAS:
                item["unidade"] = "unid"
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="A IA retornou um formato inesperado. Tente novamente.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/receitas")
def processar_receitas(
    file: UploadFile = File(...),
    user: User = Depends(get_usuario_atual),
):
    _checar_rate_limit(user.id)
    content = _ler_upload(file)
    mt = file.content_type or ""

    is_text = any(t in mt for t in ("spreadsheet", "excel", "csv", "plain", "text"))
    if is_text:
        texto = content.decode("utf-8", errors="replace")
        messages = [{"role": "user", "content": f"Conteúdo do arquivo:\n\n{texto}\n\n{PROMPT_RECEITAS}"}]
    else:
        block = _image_block(content, mt or "image/jpeg")
        messages = [{"role": "user", "content": [block, {"type": "text", "text": PROMPT_RECEITAS}]}]

    try:
        resp = _client().messages.create(model=_model(), max_tokens=4096, messages=messages)
        return _parse(resp)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="A IA retornou um formato inesperado. Tente novamente.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=str(e))
