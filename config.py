from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent

# Caso e identificação da execução.
NOME_CASO = "case_radboud_0466"
NOME_EXECUCAO = "piloto_v1_1000"

# Preparação dos recortes.
QUANTIDADE_RECORTES = 1000
TAMANHO_SAIDA = 224
MPP_ALVO = 0.5
MINIMO_TECIDO = 0.80
SEMENTE = 42

# Extrator de características.
MODELO_PHIKON = "owkin/phikon"
REVISAO_PHIKON = "057cc0295895c2df3dd7681a89680da6015cbefe"

# Cada colega escolhe o caso num ficheiro local, sem alterar o código partilhado.
import json

_config_local = PASTA_PROJETO / 'config_local.json'
if _config_local.exists():
    _valores = json.loads(_config_local.read_text(encoding='utf-8'))
    if not isinstance(_valores, dict) or set(_valores) - {'caso', 'execucao'}:
        raise ValueError('config_local.json aceita apenas caso e execucao.')
    for _chave, _valor in _valores.items():
        if not isinstance(_valor, str) or not _valor or _valor in {'.', '..'} or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in _valor):
            raise ValueError(f'Identificador inválido em config_local.json: {_chave}')
    NOME_CASO = _valores.get('caso', NOME_CASO)
    NOME_EXECUCAO = _valores.get('execucao', NOME_EXECUCAO)
