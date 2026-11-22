import csv
import hashlib
import json
from pathlib import Path

import numpy as np


PROJETO = Path(__file__).resolve().parent
CASO = "case_radboud_0466"
EXECUCAO = "piloto_v1_1000"
TESTE = "teste_007"

lote = PROJETO / "resultados_piloto" / CASO / EXECUCAO
experiencia = PROJETO / "resultados" / "ablacao" / CASO / TESTE
caminho_modelo = (
    PROJETO
    / "resultados"
    / "modelos_validacao"
    / "piloto_v1_1000_6s_94zbe"
    / "particao_5.npz"
)


def ler_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as ficheiro:
        return list(csv.DictReader(ficheiro))


# Confirmar que usamos os ficheiros da experiência original.
registo = json.loads(
    (experiencia / "experiencia.json").read_text(encoding="utf-8")
)
fontes = {
    "modelo": caminho_modelo,
    "caracteristicas": lote / "caracteristicas.npz",
    "qualidade": lote / "qualidade_recortes.csv",
}
for nome, caminho in fontes.items():
    atual = hashlib.sha256(caminho.read_bytes()).hexdigest()
    if atual != registo["sha256_fontes"][nome]:
        raise ValueError(
            f"O ficheiro {nome} mudou desde {TESTE}. "
            "Gera um novo mapa com o modelo e os dados atuais."
        )

qualidade = ler_csv(lote / "qualidade_recortes.csv")
decisoes = {linha["ficheiro"]: linha["excluir"] for linha in qualidade}

with np.load(lote / "caracteristicas.npz", allow_pickle=False) as dados:
    nomes = dados["ficheiros"].tolist()
    vetores = dados["caracteristicas"]

manter = np.array([decisoes[nome] == "0" for nome in nomes])
nomes = np.array(nomes)[manter].tolist()
vetores = vetores[manter].astype(np.float64)
indice_por_nome = {nome: i for i, nome in enumerate(nomes)}

with np.load(caminho_modelo, allow_pickle=False) as modelo:
    colunas = modelo["colunas"].tolist()
    media_treino = modelo["media"]
    escala_treino = modelo["escala"]
    coeficientes = modelo["coef"]
    offset = modelo["offset"].item()

indices_colunas = [int(c.removeprefix("phikon_")) for c in colunas]
vetores = vetores[:, indices_colunas]
soma = vetores.sum(axis=0)
n = len(vetores)


def prever(media):
    return float(
        ((media - media_treino) / escala_treino) @ coeficientes - offset
    )


score_original = prever(soma / n)
np.testing.assert_allclose(
    score_original, registo["score_original"], rtol=1e-6, atol=1e-8
)

influencia = ler_csv(experiencia / "influencia_grupos.csv")
grupos = {int(linha["grupo"]): [] for linha in influencia}

# O CSV preserva a ordem de proximidade dentro de cada grupo.
for linha in ler_csv(experiencia / "recortes_por_grupo.csv"):
    grupos[int(linha["grupo"])].append(
        indice_por_nome[linha["ficheiro"]]
    )

def ordenar_recortes(ordem_grupos):
    # Cada recorte entra apenas uma vez, mesmo com grupos sobrepostos.
    return np.array(list(dict.fromkeys(
        indice
        for grupo in ordem_grupos
        for indice in grupos[grupo]
    )), dtype=int)


def alterar_score(fila, quantidade):
    removidos = fila[:quantidade]
    media_restante = (
        soma - vetores[removidos].sum(axis=0)
    ) / (n - quantidade)
    return prever(media_restante) - score_original


# Ordenar as quedas da maior para a menor.
grupos_queda = sorted(
    [
        linha for linha in influencia
        if float(linha["delta_score"]) < 0
    ],
    key=lambda linha: float(linha["delta_score"]),
)

# Ordenar os aumentos do maior para o menor.
grupos_aumento = sorted(
    [
        linha for linha in influencia
        if float(linha["delta_score"]) > 0
    ],
    key=lambda linha: float(linha["delta_score"]),
    reverse=True,
)

filas = {
    "queda": ordenar_recortes([
        int(linha["grupo"]) for linha in grupos_queda
    ]),
    "aumento": ordenar_recortes([
        int(linha["grupo"]) for linha in grupos_aumento
    ]),
}

# Usar todas as regiões candidatas na referência aleatória.
gerador = np.random.default_rng(42)
filas_aleatorias = [
    ordenar_recortes(gerador.permutation(list(grupos)))
    for _ in range(500)
]

linhas = []

for direcao, fila in filas.items():
    quantidades = [
        q for q in (50, 100, 150, 200, 250)
        if q <= len(fila) and q < n
    ]

    print(f"\nCURVA DE {direcao.upper()}")
    print("Removidos | Delta selecionado | Delta aleatório médio | P05 | P95")

    if not quantidades:
        print("Há poucos recortes disponíveis nesta direção.")
        continue

    for quantidade in quantidades:
        delta = alterar_score(fila, quantidade)
        aleatorios = np.array([
            alterar_score(fila_aleatoria, quantidade)
            for fila_aleatoria in filas_aleatorias
        ])

        p05, p95 = np.percentile(aleatorios, [5, 95])

        linhas.append({
            "direcao": direcao,
            "recortes_removidos": quantidade,
            "fracao_removida": quantidade / n,
            "delta_selecionado": delta,
            "delta_aleatorio_medio": aleatorios.mean(),
            "delta_aleatorio_p05": p05,
            "delta_aleatorio_p95": p95,
        })

        print(
            f"{quantidade:9d} | {delta:+.6f} | "
            f"{aleatorios.mean():+.6f} | {p05:+.6f} | {p95:+.6f}"
        )

if not linhas:
    raise ValueError("Não foi possível construir nenhuma curva.")

saida = experiencia / "remocao_progressiva_direcoes.csv"
with saida.open("x", encoding="utf-8", newline="") as ficheiro:
    escritor = csv.DictWriter(ficheiro, fieldnames=list(linhas[0]))
    escritor.writeheader()
    escritor.writerows(linhas)

print("\nTabela guardada em:", saida)