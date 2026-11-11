import openslide

from config import PASTA_PROJETO, NOME_CASO


pasta_projeto = PASTA_PROJETO
nome_caso = NOME_CASO

caminho_mascara = (
    pasta_projeto / "mascaras" / f"{nome_caso}_tissue.tif"
)

if not caminho_mascara.is_file():
    raise FileNotFoundError(
        f"Máscara não encontrada: {caminho_mascara}"
    )

with openslide.OpenSlide(str(caminho_mascara)) as mascara:
    print("Máscara aberta com sucesso!")
    print("Caso:", nome_caso)
    print("Dimensões:", mascara.dimensions)
    print("Número de níveis:", mascara.level_count)

    for nivel, dimensoes in enumerate(mascara.level_dimensions):
        print(f"Nível {nivel}: {dimensoes}")
