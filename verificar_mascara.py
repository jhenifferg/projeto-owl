from pathlib import Path
import openslide
import numpy as np

pasta_projeto = PASTA_PROJETO
caminho_mascara = pasta_projeto / "mascaras" / f"{nome_caso}_tissue.tif"

if not caminho_mascara.is_file():
    raise FileNotFoundError(f"Máscara não encontrada: {caminho_mascara}")

with openslide.OpenSlide(str(caminho_mascara)) as mascara:
    print("Máscara aberta com sucesso!")
    print("Dimensões:", mascara.dimensions)
    print("Número de níveis:", mascara.level_count)

    for nivel, dimensoes in enumerate(mascara.level_dimensions):
        print(f"Nível {nivel}: {dimensoes}")

    previa_mascara = mascara.read_region(
        (0, 0),
        2,
        mascara.level_dimensions[2]
    ).convert("RGB")

    valores = np.asarray(previa_mascara)

    print("Valores por canal:")
    for canal, nome in enumerate(("Vermelho", "Verde", "Azul")):
        print(nome, np.unique(valores[:, :, canal]))

    pasta_resultados = pasta_projeto / "resultados"
    pasta_resultados.mkdir(exist_ok=True)
    previa_mascara.save(pasta_resultados / "mascara_previa.png")