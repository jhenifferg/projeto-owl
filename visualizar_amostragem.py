import csv

import openslide
from PIL import ImageDraw

from config import (
    PASTA_PROJETO,
    NOME_CASO,
    NOME_EXECUCAO,
)


pasta_lote = (
    PASTA_PROJETO / "resultados" / NOME_CASO / NOME_EXECUCAO
)

caminho_imagem = (
    PASTA_PROJETO / "imagens" / f"{NOME_CASO}.tif"
)

with (pasta_lote / "coordenadas.csv").open(
    encoding="utf-8", newline=""
) as ficheiro:
    registos = list(csv.DictReader(ficheiro))

with openslide.OpenSlide(str(caminho_imagem)) as imagem:
    # Criar uma vista geral sem carregar a lâmina inteira.
    previa = imagem.get_thumbnail((1600, 1600)).convert("RGB")

    escala_x = previa.width / imagem.dimensions[0]
    escala_y = previa.height / imagem.dimensions[1]

    desenho = ImageDraw.Draw(previa)

    for registo in registos:
        x = int(registo["x"])
        y = int(registo["y"])
        largura = int(registo["largura_original"])
        altura = int(registo["altura_original"])

        desenho.rectangle(
            (
                x * escala_x,
                y * escala_y,
                (x + largura) * escala_x,
                (y + altura) * escala_y,
            ),
            outline="red",
            width=2,
        )

    pasta_mapas = PASTA_PROJETO / "visualizacoes" / NOME_CASO / NOME_EXECUCAO
    pasta_mapas.mkdir(parents=True, exist_ok=True)
    caminho_saida = pasta_mapas / "distribuicao_recortes.png"
    previa.save(caminho_saida)

print("Mapa guardado em:", caminho_saida)
