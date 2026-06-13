from pydantic import BaseModel, Field, model_validator
from typing import Optional


class CanalCreate(BaseModel):
    nome: str = Field(min_length=1)
    taxa_plataforma_pct: float = Field(default=0.0, ge=0, lt=100)
    taxa_cartao_pct: float = Field(default=0.0, ge=0, lt=100)
    imposto_pct: float = Field(default=0.0, ge=0, lt=100)

    @model_validator(mode="after")
    def _validar_soma_taxas(self):
        soma = self.taxa_plataforma_pct + self.taxa_cartao_pct + self.imposto_pct
        if soma >= 100:
            raise ValueError(
                "A soma das taxas do canal (plataforma + cartão + imposto) deve ser "
                f"menor que 100% — recebido {soma:g}%."
            )
        return self


class CanalUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    taxa_plataforma_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    taxa_cartao_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    imposto_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    ativo: Optional[bool] = None


class CanalOut(BaseModel):
    id: int
    nome: str
    taxa_plataforma_pct: float
    taxa_cartao_pct: float
    imposto_pct: float
    ativo: bool

    class Config:
        from_attributes = True


class ProdutoPrecoCreate(BaseModel):
    canal_id: int
    margem_pct: float = Field(ge=0, lt=100)
    preco_final: Optional[float] = Field(default=None, gt=0)


class ProdutoPrecoUpdate(BaseModel):
    margem_pct: Optional[float] = Field(default=None, ge=0, lt=100)
    preco_final: Optional[float] = Field(default=None, gt=0)


class ProdutoPrecoOut(BaseModel):
    id: int
    produto_id: int
    canal_id: int
    canal_nome: str
    margem_pct: float
    preco_final: Optional[float]
    preco_sugerido: float  # calculado
    custo_total: float  # calculado

    class Config:
        from_attributes = True


class RelatorioMargemCanal(BaseModel):
    canal_id: int
    canal_nome: str
    margem_alvo_pct: float
    preco_final: Optional[float]
    preco_sugerido: float
    preco_praticado: float       # preco_final se definido, senão preco_sugerido
    margem_real_pct: float       # margem efetiva sobre o preço praticado, líquida de taxas
    lucro_unitario: float        # preço praticado − custo − taxas


class RelatorioMargemProduto(BaseModel):
    produto_id: int
    produto_nome: str
    custo_total: float
    canais: list[RelatorioMargemCanal]


class RelatorioMargemOut(BaseModel):
    produtos: list[RelatorioMargemProduto]
