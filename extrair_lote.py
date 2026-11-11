import csv
import json
import math
from time import perf_counter

import numpy as np
import openslide
from PIL import Image

from config import (
    PASTA_PROJETO,
    NOME_CASO,
    NOME_EXECUCAO,
    QUANTIDADE_RECORTES,
    TAMANHO_SAIDA,
    MPP_ALVO,
    MINIMO_TECIDO,
    SEMENTE,
)


# 1. Definir os parâmetros da execução.
quantidade = QUANTIDADE_RECORTES
tamanho_saida = TAMANHO_SAIDA
mpp_alvo = MPP_ALVO
minimo_tecido = MINIMO_TECIDO
semente = SEMENTE

caminho_imagem = (
    PASTA_PROJETO / "imagens" / f"{NOME_CASO}.tif"
)
caminho_mascara = (
    PASTA_PROJETO / "mascaras" / f"{NOME_CASO}_tissue.tif"
)

# Guardar esta execução numa pasta própria.
pasta_saida = (
    PASTA_PROJETO / "resultados" / NOME_CASO / NOME_EXECUCAO
)

if pasta_saida.exists():
    raise FileExistsError(
        f"A pasta já existe: {pasta_saida}\n"
        "Escolha outro nome para não substituir resultados anteriores."
    )

inicio = perf_counter()

with (
    openslide.OpenSlide(str(caminho_imagem)) as imagem,
    openslide.OpenSlide(str(caminho_mascara)) as mascara,
):
    # 2. Calcular o tamanho original da região.
    mpp_x = float(
        imagem.properties[openslide.PROPERTY_NAME_MPP_X]
    )
    mpp_y = float(
        imagem.properties[openslide.PROPERTY_NAME_MPP_Y]
    )

    largura = round(tamanho_saida * mpp_alvo / mpp_x)
    altura = round(tamanho_saida * mpp_alvo / mpp_y)

    # 3. Ler a máscara no nível 0.
    # Neste caso, ela é muito menor do que a lâmina original.
    previa_mascara = mascara.read_region(
        (0, 0),
        0,
        mascara.dimensions,
    ).convert("RGB")

    tecido = np.asarray(previa_mascara)[:, :, 0] == 1

    escala_x = imagem.dimensions[0] / mascara.dimensions[0]
    escala_y = imagem.dimensions[1] / mascara.dimensions[1]

    # 4. Construir uma grelha de recortes sem sobreposição.
    candidatos = []

    for y in range(0, imagem.dimensions[1] - altura + 1, altura):
        for x in range(
            0, imagem.dimensions[0] - largura + 1, largura
        ):
            # Localizar esta região na máscara.
            mx0 = math.floor(x / escala_x)
            my0 = math.floor(y / escala_y)
            mx1 = math.ceil((x + largura) / escala_x)
            my1 = math.ceil((y + altura) / escala_y)

            regiao_mascara = tecido[my0:my1, mx0:mx1]
            fracao_tecido = float(regiao_mascara.mean())

            if fracao_tecido >= minimo_tecido:
                candidatos.append((x, y, fracao_tecido))

    print("Recortes candidatos:", len(candidatos))

    if len(candidatos) < quantidade:
        raise ValueError(
            f"Encontrámos apenas {len(candidatos)} candidatos."
        )

    # 5. Selecionar as posições sem repetição.
    gerador = np.random.default_rng(semente)
    indices = gerador.choice(
        len(candidatos),
        size=quantidade,
        replace=False,
    )

    pasta_saida.mkdir(parents=True)

    # 6. Extrair os recortes e registar as coordenadas.
    caminho_csv = pasta_saida / "coordenadas.csv"

    with caminho_csv.open(
        "w", newline="", encoding="utf-8"
    ) as ficheiro_csv:
        campos = [
            "caso",
            "ficheiro",
            "x",
            "y",
            "nivel",
            "largura_original",
            "altura_original",
            "tamanho_saida",
            "mpp_x_efetivo",
            "mpp_y_efetivo",
            "fracao_tecido_estimada",
            "semente",
        ]

        escritor = csv.DictWriter(
            ficheiro_csv,
            fieldnames=campos,
        )
        escritor.writeheader()

        for numero, indice in enumerate(indices, start=1):
            x, y, fracao = candidatos[int(indice)]

            recorte = imagem.read_region(
                (x, y),
                0,
                (largura, altura),
            ).convert("RGB")

            recorte = recorte.resize(
                (tamanho_saida, tamanho_saida),
                resample=Image.Resampling.LANCZOS,
            )

            nome_ficheiro = f"recorte_{numero:03d}.png"
            recorte.save(pasta_saida / nome_ficheiro)

            escritor.writerow({
                "caso": NOME_CASO,
                "ficheiro": nome_ficheiro,
                "x": x,
                "y": y,
                "nivel": 0,
                "largura_original": largura,
                "altura_original": altura,
                "tamanho_saida": tamanho_saida,
                "mpp_x_efetivo": largura * mpp_x / tamanho_saida,
                "mpp_y_efetivo": altura * mpp_y / tamanho_saida,
                "fracao_tecido_estimada": fracao,
                "semente": semente,
            })

            print(
                f"Recorte {numero}/{quantidade} guardado "
                f"— tecido estimado: {fracao:.1%}"
            )

duracao = perf_counter() - inicio

print("Pasta dos resultados:", pasta_saida)
print(f"Tempo total de extração: {duracao:.2f} segundos")

# Registar os parâmetros realmente usados, apenas após concluir os recortes.
preparacao = {
    "caso": NOME_CASO,
    "execucao": NOME_EXECUCAO,
    "quantidade_recortes": quantidade,
    "tamanho_saida_px": tamanho_saida,
    "mpp_alvo": mpp_alvo,
    "fracao_minima_tecido": minimo_tecido,
    "semente": semente,
}
(pasta_saida / "preparacao.json").write_text(
    json.dumps(preparacao, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
