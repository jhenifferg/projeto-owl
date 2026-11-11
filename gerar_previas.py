import argparse

import openslide

from config import NOME_CASO, PASTA_PROJETO


parser = argparse.ArgumentParser(description="Gerar prévias da lâmina e da máscara.")
parser.add_argument("--nivel-imagem", type=int, required=True)
parser.add_argument("--nivel-mascara", type=int, required=True)
args = parser.parse_args()

caminho_imagem = PASTA_PROJETO / "imagens" / f"{NOME_CASO}.tif"
caminho_mascara = PASTA_PROJETO / "mascaras" / f"{NOME_CASO}_tissue.tif"
resultados = PASTA_PROJETO / "resultados" / NOME_CASO / "previas"

with (
    openslide.OpenSlide(str(caminho_imagem)) as imagem,
    openslide.OpenSlide(str(caminho_mascara)) as mascara,
):
    if not 0 <= args.nivel_imagem < imagem.level_count:
        parser.error("O nível da imagem está fora do intervalo disponível.")
    if not 0 <= args.nivel_mascara < mascara.level_count:
        parser.error("O nível da máscara está fora do intervalo disponível.")

    dimensoes = imagem.level_dimensions[args.nivel_imagem]
    dimensoes_mascara = mascara.level_dimensions[args.nivel_mascara]
    if dimensoes != dimensoes_mascara:
        parser.error(f"Os níveis têm dimensões diferentes: {dimensoes} e {dimensoes_mascara}.")
    if dimensoes[0] * dimensoes[1] > 40_000_000:
        parser.error("Escolhe níveis mais reduzidos para gerar as prévias.")

    previa = imagem.read_region((0, 0), args.nivel_imagem, dimensoes)
    previa_mascara = mascara.read_region((0, 0), args.nivel_mascara, dimensoes)
    resultados.mkdir(parents=True, exist_ok=True)
    previa.convert("RGB").save(resultados / f"{NOME_CASO}_previa.png")
    previa_mascara.convert("RGB").save(resultados / f"{NOME_CASO}_mascara_previa.png")

print(f"Prévias de {NOME_CASO} guardadas em {resultados}")
