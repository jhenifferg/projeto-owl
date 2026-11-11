import openslide
from config import PASTA_PROJETO, NOME_CASO


pasta_projeto = PASTA_PROJETO
nome_caso = NOME_CASO

caminho_imagem = pasta_projeto / "imagens" / f"{nome_caso}.tif"

if not caminho_imagem.is_file(): ## Se não existir um ficheiro nesse caminho, interrompa o programa e apresente o erro.
    raise FileNotFoundError(f"Imagem não encontrada: {caminho_imagem}")

with openslide.OpenSlide(str(caminho_imagem)) as imagem:
    print("Imagem aberta com sucesso!")
    print("Dimensões originais:", imagem.dimensions)
    print("Número de níveis:", imagem.level_count)
    print("Micrómetros por píxel em X:",
          imagem.properties.get(openslide.PROPERTY_NAME_MPP_X, "Não disponível"))

    print("Micrómetros por píxel em Y:",
          imagem.properties.get(openslide.PROPERTY_NAME_MPP_Y, "Não disponível"))

    print("Ampliação da objetiva:",
          imagem.properties.get(openslide.PROPERTY_NAME_OBJECTIVE_POWER,
                                "Não disponível"))

    for nivel, dimensoes in enumerate(imagem.level_dimensions):
        print(f"Nível {nivel}: {dimensoes}")
