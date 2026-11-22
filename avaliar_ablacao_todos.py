"""Avaliar a ablação dos pacientes com os modelos que os deixaram fora do treino."""

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from config import NOME_EXECUCAO, PASTA_PROJETO


def ler_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as ficheiro:
        return list(csv.DictReader(ficheiro))


def guardar_csv(caminho, linhas):
    with caminho.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.DictWriter(ficheiro, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def avaliar_caso(caso, modelo, lote, pasta_saida):
    # Conferir as decisões de qualidade.
    decisoes = {}
    for linha in ler_csv(lote / "qualidade_recortes.csv"):
        nome = linha["ficheiro"]
        decisao = linha["excluir"].strip()
        if nome in decisoes or decisao not in {"0", "1"}:
            raise ValueError(f"Decisão duplicada ou inválida para {nome}.")
        decisoes[nome] = decisao

    with np.load(lote / "caracteristicas.npz", allow_pickle=False) as dados:
        nomes = dados["ficheiros"].tolist()
        vetores = dados["caracteristicas"]
        coordenadas = dados["coordenadas"]
        if dados["caso"].item() != caso:
            raise ValueError("O NPZ pertence a outro caso.")

    if len(set(nomes)) != len(nomes) or set(nomes) != set(decisoes):
        raise ValueError("Os nomes do NPZ e da tabela de qualidade diferem.")
    if vetores.shape != (len(nomes), 768):
        raise ValueError("Formato inválido das características.")
    if coordenadas.shape != (len(nomes), 2):
        raise ValueError("Formato inválido das coordenadas.")
    if not np.isfinite(vetores).all() or not np.isfinite(coordenadas).all():
        raise ValueError("Há valores inválidos no NPZ.")

    manter = np.array([decisoes[nome] == "0" for nome in nomes])
    nomes = np.array(nomes)[manter]
    vetores = vetores[manter].astype(np.float64)
    coordenadas = coordenadas[manter].astype(np.float64)

    indices = [
        int(coluna.removeprefix("phikon_"))
        for coluna in modelo["colunas"].tolist()
    ]
    vetores = vetores[:, indices]

    n = len(vetores)
    tamanho = 50
    if n <= tamanho:
        raise ValueError("Há poucos recortes válidos.")

    media = vetores.mean(axis=0)
    score_original = float(
        ((media - modelo["media"]) / modelo["escala"])
        @ modelo["coef"] - modelo["offset"].item()
    )

    posicao = modelo["casos_teste"].tolist().index(caso)
    np.testing.assert_allclose(
        score_original,
        modelo["scores_teste"][posicao],
        rtol=1e-6,
        atol=1e-8,
    )

    # O Cox é linear no vetor médio. Estas contribuições permitem
    # calcular exatamente a alteração sem repetir as 768 contas.
    contribuicoes = vetores @ (modelo["coef"] / modelo["escala"])
    contribuicao_media = contribuicoes.mean()

    def delta_remocao(removidos):
        q = len(removidos)
        return float(
            (q * contribuicao_media - contribuicoes[removidos].sum())
            / (n - q)
        )

    # Conferir a fórmula rápida contra o recálculo direto da média.
    exemplo = np.arange(tamanho)
    media_restante = (
        vetores.sum(axis=0) - vetores[exemplo].sum(axis=0)
    ) / (n - tamanho)
    score_exemplo = float(
        ((media_restante - modelo["media"]) / modelo["escala"])
        @ modelo["coef"] - modelo["offset"].item()
    )
    np.testing.assert_allclose(
        delta_remocao(exemplo),
        score_exemplo - score_original,
        rtol=1e-6,
        atol=1e-8,
    )

    # Um grupo de 50 vizinhos para cada posição válida.
    grupos = []
    for centro in coordenadas:
        distancias = np.sum((coordenadas - centro) ** 2, axis=1)
        grupos.append(np.argsort(distancias, kind="stable")[:tamanho])

    deltas = np.array([delta_remocao(grupo) for grupo in grupos])

    def ordenar_recortes(ordem):
        return np.array(list(dict.fromkeys(
            int(indice)
            for grupo in ordem
            for indice in grupos[int(grupo)]
        )), dtype=int)

    # Mesma referência espacial aleatória para ambas as direções.
    quantidades = [q for q in (50, 100, 150, 200, 250) if q < n]
    gerador = np.random.default_rng(42)
    aleatorios = np.empty((500, len(quantidades)))

    for repeticao in range(500):
        fila = ordenar_recortes(gerador.permutation(n))
        for coluna, q in enumerate(quantidades):
            aleatorios[repeticao, coluna] = delta_remocao(fila[:q])

    curvas = []
    ordens = {
        "queda": np.argsort(deltas, kind="stable")[np.sort(deltas) < 0],
        "aumento": np.argsort(-deltas, kind="stable")[np.sort(-deltas) < 0],
    }

    for direcao, ordem in ordens.items():
        fila = ordenar_recortes(ordem)
        for coluna, q in enumerate(quantidades):
            if q > len(fila):
                continue

            referencia = aleatorios[:, coluna]
            curvas.append({
                "direcao": direcao,
                "recortes_removidos": q,
                "fracao_removida": q / n,
                "delta_selecionado": delta_remocao(fila[:q]),
                "delta_aleatorio_medio": float(referencia.mean()),
                "delta_aleatorio_p05": float(np.percentile(referencia, 5)),
                "delta_aleatorio_p95": float(np.percentile(referencia, 95)),
            })

    pasta_saida.mkdir()
    guardar_csv(
        pasta_saida / "influencia_grupos.csv",
        [{
            "grupo": i + 1,
            "x_referencia": int(coordenadas[i, 0]),
            "y_referencia": int(coordenadas[i, 1]),
            "delta_score": float(deltas[i]),
            "delta_absoluto": float(abs(deltas[i])),
        } for i in range(n)],
    )

    # Os índices referem-se aos nomes dos recortes válidos deste ficheiro.
    np.savez_compressed(
        pasta_saida / "grupos.npz",
        ficheiros=nomes,
        coordenadas=coordenadas,
        indices_grupos=np.stack(grupos),
    )

    if curvas:
        guardar_csv(
            pasta_saida / "remocao_progressiva_direcoes.csv", curvas
        )

    return {
        "caso": caso,
        "recortes_validos": n,
        "score_original": score_original,
        "coeficientes_ativos": int(np.count_nonzero(modelo["coef"])),
        "pontos_curvas": len(curvas),
        "grupos": n,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelos", type=Path, required=True)
    parser.add_argument("--execucao", default=NOME_EXECUCAO)
    args = parser.parse_args()

    projeto = PASTA_PROJETO
    tabela = (
        projeto / "resultados"
        / f"pacientes_filtrados_{args.execucao}.csv"
    )
    hash_tabela = hashlib.sha256(tabela.read_bytes()).hexdigest()

    # Associar cada paciente à sua única partição de teste.
    modelos = {}
    caminhos = sorted(args.modelos.glob("particao_*.npz"))
    if not caminhos:
        raise ValueError("Não foram encontrados modelos de partição.")

    for caminho in caminhos:
        with np.load(caminho, allow_pickle=False) as ficheiro:
            modelo = {chave: ficheiro[chave] for chave in ficheiro.files}

        if modelo["sha256_tabela"].item() != hash_tabela:
            raise ValueError(
                "A tabela mudou desde o treino. Usa os modelos correspondentes "
                "à tabela atual ou recupera a tabela usada neste treino."
            )

        treino = set(modelo["casos_treino"].tolist())
        teste = modelo["casos_teste"].tolist()
        if treino & set(teste):
            raise ValueError(f"Há sobreposição de treino e teste em {caminho}.")

        for caso in teste:
            if caso in modelos:
                raise ValueError(f"{caso} aparece no teste de duas partições.")
            modelos[caso] = (caminho, modelo)

    pasta_base = projeto / "resultados" / "ablacao_validacao"
    pasta_base.mkdir(parents=True, exist_ok=True)
    saida = Path(tempfile.mkdtemp(prefix="execucao_", dir=pasta_base))

    resumo = []
    falhas = []
    for caso, (caminho_modelo, modelo) in sorted(modelos.items()):
        lote = projeto / "resultados_piloto" / caso / args.execucao
        try:
            linha = avaliar_caso(caso, modelo, lote, saida / caso)
            linha["modelo"] = str(caminho_modelo.resolve())
            linha["sha256_modelo"] = hashlib.sha256(
                caminho_modelo.read_bytes()
            ).hexdigest()
            linha["sha256_caracteristicas"] = hashlib.sha256(
                (lote / "caracteristicas.npz").read_bytes()
            ).hexdigest()
            linha["sha256_qualidade"] = hashlib.sha256(
                (lote / "qualidade_recortes.csv").read_bytes()
            ).hexdigest()

            (saida / caso / "experiencia.json").write_text(
                json.dumps(
                    {**linha, "semente_aleatoria": 42, "repeticoes": 500,
                     "contexto": "paciente fora do treino"},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            resumo.append(linha)
            print(f"{caso}: concluído", flush=True)

        except (OSError, ValueError, KeyError, AssertionError) as erro:
            falhas.append({"caso": caso, "erro": str(erro)})
            print(f"{caso}: falha — {erro}", flush=True)

    if resumo:
        guardar_csv(saida / "resumo.csv", resumo)
    if falhas:
        guardar_csv(saida / "falhas.csv", falhas)

    print(f"\nConcluídos: {len(resumo)} | Falhas: {len(falhas)}")
    print("Resultados guardados em:", saida)


if __name__ == "__main__":
    main()
