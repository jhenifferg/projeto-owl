import openslide

import numpy as np

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

        # Escolher a resolução correspondente à prévia da imagem.
    nivel_mascara = 2

    previa_mascara = mascara.read_region(
        (0, 0),
        nivel_mascara,
        mascara.level_dimensions[nivel_mascara]
    ).convert("RGB")

    # Consultar os valores existentes na máscara.
    valores = np.asarray(previa_mascara)

    print("Valores por canal:")
    for canal, nome in enumerate(("Vermelho", "Verde", "Azul")):
        print(nome, np.unique(valores[:, :, canal]))

    # Guardar a pré-visualização.
    pasta_resultados = pasta_projeto / "resultados"
    pasta_resultados.mkdir(exist_ok=True)

    caminho_saida = (
        pasta_resultados / f"{nome_caso}_mascara_previa.png"
    )
    previa_mascara.save(caminho_saida)

    print("Máscara guardada em:", caminho_saida)