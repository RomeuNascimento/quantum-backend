def fator_unidade(unidade) -> float:
    """Fator de conversão da unidade de cadastro para a base g/ml.

    O consumo em receitas/produtos é sempre em g/ml (`quantidade_g`), mas o
    ingrediente pode ser cadastrado em kg/L (embalagem = 1 kg → 1000 g).
    Sem este fator, o custo de ingredientes em kg/L sai 1000× maior.
    """
    u = unidade.value if hasattr(unidade, "value") else str(unidade or "")
    return 1000.0 if u in ("kg", "L") else 1.0
