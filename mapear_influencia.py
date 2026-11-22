"""Calcular a influência de grupos de recortes e desenhar as referências."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from config import NOME_CASO, NOME_EXECUCAO, PASTA_PROJETO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caso", default=NOME_CASO)
    parser.add_argument("--execucao", default=NOME_EXECUCAO)
    parser.add_argument("--largura-original", type=int)
    parser.add_argument("--altura-original", type=int)
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument(
        "--todas-posicoes",
        action="store_true",
        help="Avaliar um grupo centrado em cada recorte válido.",
    )
    parser.add_argument("--modelo", type=Path)
    args = parser.parse_args()

    for valor in (args.caso, args.execucao):
        if not valor or not all(
            c.isascii() and (c.isalnum() or c in "_-") for c in valor
        ):
            parser.error("Caso e execução devem ser identificadores válidos.")

    projeto = PASTA_PROJETO
    caso = args.caso
    execucao = args.execucao

    lote = projeto / "resultados_piloto" / caso / execucao
    resultados = projeto / "resultados"
    caminho_modelo = (
        args.modelo
        if args.modelo is not None
        else resultados / f"modelo_cox_{execucao}.npz"
    )
    caminho_qualidade = lote / "qualidade_recortes.csv"
    caminho_npz = lote / "caracteristicas.npz"
    caminho_coordenadas = lote / "coordenadas.csv"
    caminho_metadados = lote / "metadados_lamina.json"

    # A prévia é uma imagem inteira da lâmina, sem recorte das margens.
    caminho_previa = (
        resultados / caso / "previas" / f"{caso}_previa.png"
    )

    # Ler as dimensões originais do JSON ou dos argumentos do terminal.
    if (
        args.largura_original is not None
        or args.altura_original is not None
    ):
        largura_original = args.largura_original
        altura_original = args.altura_original
    else:
        if not caminho_metadados.is_file():
            parser.error(
                f"Falta {caminho_metadados}. Guarda as dimensões do nível 0 "
                "nesse JSON ou fornece --largura-original e --altura-original."
            )
        metadados = json.loads(
            caminho_metadados.read_text(encoding="utf-8")
        )
        largura_original = metadados["largura_original"]
        altura_original = metadados["altura_original"]

    if (
        type(largura_original) is not int
        or type(altura_original) is not int
        or largura_original <= 0
        or altura_original <= 0
    ):
        raise ValueError("Indica largura e altura originais inteiras e positivas.")

    with Image.open(caminho_previa) as ficheiro:
        previa = ficheiro.convert("RGB")
    previa.thumbnail((1200, 1200))

    # Ler uma decisão de qualidade por recorte.
    decisoes = {}
    with caminho_qualidade.open(
        encoding="utf-8-sig", newline=""
    ) as ficheiro:
        for linha in csv.DictReader(ficheiro):
            nome = linha["ficheiro"]
            decisao = linha["excluir"].strip()
            if nome in decisoes or decisao not in {"0", "1"}:
                raise ValueError(
                    f"Decisão duplicada ou inválida para {nome}."
                )
            decisoes[nome] = decisao

    with np.load(caminho_npz, allow_pickle=False) as dados:
        nomes = dados["ficheiros"].tolist()
        vetores = dados["caracteristicas"]
        coordenadas = dados["coordenadas"]
        caso_npz = dados["caso"].item()

    if caso_npz != caso:
        raise ValueError("O NPZ pertence a outro caso.")
    if len(set(nomes)) != len(nomes) or set(nomes) != set(decisoes):
        raise ValueError("Os nomes do NPZ e da tabela de qualidade diferem.")
    if vetores.shape != (len(nomes), 768):
        raise ValueError("Dimensão inválida da matriz Phikon.")
    if coordenadas.shape != (len(nomes), 2):
        raise ValueError("Dimensão inválida da matriz de coordenadas.")
    if not np.isfinite(vetores).all():
        raise ValueError("O NPZ contém características inválidas.")

    # Conferir que as coordenadas do CSV correspondem às do NPZ.
    with caminho_coordenadas.open(
        encoding="utf-8-sig", newline=""
    ) as ficheiro:
        linhas = list(csv.DictReader(ficheiro))

    if [linha["ficheiro"] for linha in linhas] != nomes:
        raise ValueError("A ordem dos nomes difere entre CSV e NPZ.")

    coordenadas_csv = np.array([
        (int(linha["x"]), int(linha["y"])) for linha in linhas
    ])
    if not np.array_equal(coordenadas, coordenadas_csv):
        raise ValueError("As coordenadas diferem entre CSV e NPZ.")

    manter = np.array(
        [decisoes[nome] == "0" for nome in nomes], dtype=bool
    )
    nomes = np.array(nomes)[manter]
    vetores = vetores[manter].astype(np.float64)
    coordenadas = coordenadas[manter].astype(np.float64)

    with np.load(caminho_modelo, allow_pickle=False) as modelo:
        colunas = modelo["colunas"].tolist()
        media_treino = modelo["media"]
        escala_treino = modelo["escala"]
        coeficientes = modelo["coef"]
        offset = modelo["offset"].item()

        if args.modelo is not None:
            casos_treino = modelo["casos_treino"].tolist()
            casos_teste = modelo["casos_teste"].tolist()

            if caso in casos_treino or casos_teste.count(caso) != 1:
                raise ValueError(
                    "Este modelo deve ter o paciente apenas no conjunto de teste."
                )

            posicao = casos_teste.index(caso)
            score_referencia = float(modelo["scores_teste"][posicao])
            contexto = "paciente fora do treino deste modelo"
        else:
            casos_modelo = modelo["casos"].tolist()
            if caso not in casos_modelo:
                raise ValueError("O paciente não pertence ao modelo final.")

            riscos = pd.read_csv(
                resultados / f"risco_cox_{execucao}.csv"
            )
            referencia = riscos.loc[
                riscos["case_id"] == caso, "risco_modelo_final"
            ]
            if len(referencia) != 1:
                raise ValueError("Esperávamos um score de referência.")

            score_referencia = float(referencia.iloc[0])
            contexto = "modelo final ajustado incluindo este paciente"

    indices_colunas = [
        int(coluna.removeprefix("phikon_")) for coluna in colunas
    ]
    vetores = vetores[:, indices_colunas]

    n = len(vetores)
    tamanho_grupo = 50
    if n <= tamanho_grupo:
        raise ValueError("Há poucos recortes válidos para esta experiência.")

    soma = vetores.sum(axis=0)

    def prever(media):
        padronizado = (media - media_treino) / escala_treino
        return float(padronizado @ coeficientes - offset)

    score_original = prever(soma / n)

    np.testing.assert_allclose(
        score_original,
        score_referencia,
        rtol=1e-6,
        atol=1e-8,
    )

    # Reproduzir a seleção usada na experiência anterior.
    if args.todas_posicoes:
        referencias = np.arange(n)
    else:
        gerador = np.random.default_rng(args.semente)
        for _ in range(500):
            gerador.choice(n, size=tamanho_grupo, replace=False)
        referencias = gerador.choice(n, size=20, replace=False)

    avaliacoes = []
    membros = []

    for numero, indice in enumerate(referencias, start=1):
        centro = coordenadas[indice]
        distancias = np.sum((coordenadas - centro) ** 2, axis=1)
        grupo = np.argsort(
            distancias, kind="stable"
        )[:tamanho_grupo]

        media_restante = (
            soma - vetores[grupo].sum(axis=0)
        ) / (n - tamanho_grupo)

        score_remocao = prever(media_restante)
        delta = score_remocao - score_original

        avaliacoes.append({
            "grupo": numero,
            "x_referencia": int(centro[0]),
            "y_referencia": int(centro[1]),
            "recortes_removidos": tamanho_grupo,
            "score_original": score_original,
            "score_apos_remocao": score_remocao,
            "delta_score": delta,
            "delta_absoluto": abs(delta),
        })

        for posicao in grupo:
            membros.append({
                "grupo": numero,
                "ficheiro": nomes[posicao],
                "x": int(coordenadas[posicao, 0]),
                "y": int(coordenadas[posicao, 1]),
            })

    # Criar o mapa antes de guardar os resultados.
    escala_x = previa.width / largura_original
    escala_y = previa.height / altura_original

    mapa = Image.new(
        "RGB", (previa.width, previa.height + 75), "white"
    )
    mapa.paste(previa, (0, 75))
    desenho = ImageDraw.Draw(mapa)
    desenho.text(
        (10, 10),
        "Alteracao do score ao retirar 50 recortes vizinhos",
        fill="black",
    )
    desenho.text(
        (10, 30),
        "Vermelho: retirar baixa o score | Azul: retirar sobe o score",
        fill="black",
    )
    desenho.text(
        (10, 50),
        "Circulos maiores indicam maior alteracao absoluta",
        fill="black",
    )

    maior_delta = max(linha["delta_absoluto"] for linha in avaliacoes)

    for linha in sorted(
        avaliacoes,
        key=lambda r: r["delta_absoluto"],
        reverse=True,
    ):
        x = linha["x_referencia"] * escala_x
        y = linha["y_referencia"] * escala_y + 75
        proporcao = (
            linha["delta_absoluto"] / maior_delta if maior_delta else 0
        )
        
        raio = (
            2 + 4 * proporcao
            if args.todas_posicoes
            else 8 + 15 * proporcao
        )
        cor = "red" if linha["delta_score"] < 0 else "blue"
        if linha["delta_score"] == 0:
            cor = "gray"

        desenho.ellipse(
            (x - raio, y - raio, x + raio, y + raio),
            outline=cor,
            width=1 if args.todas_posicoes else 3,
        )

        if not args.todas_posicoes:
            desenho.text(
                (x + raio + 2, y - 5),
                str(linha["grupo"]),
                fill="black",
            )

    # Uma pasta nova preserva cada execução anterior.
    saida_base = resultados / "ablacao" / caso
    saida_base.mkdir(parents=True, exist_ok=True)
    numero_execucao = 1
    saida = saida_base / f"teste_{numero_execucao:03d}"
    while saida.exists():
        numero_execucao += 1
        saida = saida_base / f"teste_{numero_execucao:03d}"
    saida.mkdir()

    for nome_csv, registos in [
        ("influencia_grupos.csv", avaliacoes),
        ("recortes_por_grupo.csv", membros),
    ]:
        with (saida / nome_csv).open(
            "w", encoding="utf-8", newline=""
        ) as ficheiro:
            escritor = csv.DictWriter(
                ficheiro, fieldnames=list(registos[0])
            )
            escritor.writeheader()
            escritor.writerows(registos)

    fontes = {
        "modelo": caminho_modelo,
        "caracteristicas": caminho_npz,
        "qualidade": caminho_qualidade,
        "coordenadas": caminho_coordenadas,
        "previa": caminho_previa,
    }
    registo = {
        "caso": caso,
        "execucao_recortes": execucao,
        "recortes_validos": n,
        "recortes_por_grupo": tamanho_grupo,
        "grupos": len(referencias),
        "modo_referencias": (
            "todas_posicoes" if args.todas_posicoes else "amostra_aleatoria"
        ),
        "semente": None if args.todas_posicoes else args.semente,
        "sorteios_anteriores_a_selecao": (
            0 if args.todas_posicoes else 500
        ),
        "largura_original": largura_original,
        "altura_original": altura_original,
        "score_original": score_original,
        "contexto": contexto,
        "sha256_fontes": {
            nome: hashlib.sha256(caminho.read_bytes()).hexdigest()
            for nome, caminho in fontes.items()
        },
    }
    (saida / "experiencia.json").write_text(
        json.dumps(registo, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    mapa.save(saida / "mapa_referencias.png")

    print("Caso:", caso)
    print("Recortes válidos:", n)
    print(f"Score original: {score_original:.6f}")
    print("Resultados guardados em:", saida)


if __name__ == "__main__":
    main()