from pathlib import Path

from config import PASTA_PROJETO, NOME_CASO

from PIL import Image
import numpy as np
import openslide


# 1. Definir os caminhos.
pasta_projeto = PASTA_PROJETO
nome_caso = NOME_CASO

caminho_imagem = pasta_projeto / "imagens" / f"{nome_caso}.tif"
caminho_mascara = pasta_projeto / "mascaras" / f"{nome_caso}_tissue.tif"

pasta_resultados = pasta_projeto / "resultados"
pasta_resultados.mkdir(exist_ok=True)


# 2. Abrir a imagem e a máscara.
with (
    openslide.OpenSlide(str(caminho_imagem)) as imagem,
    openslide.OpenSlide(str(caminho_mascara)) as mascara,
):
    # 3. Ler uma versão pequena da máscara.
    nivel_mascara = 2

    previa = mascara.read_region(
        (0, 0),
        nivel_mascara,
        mascara.level_dimensions[nivel_mascara],
    ).convert("RGB")

    tecido = np.asarray(previa)[:, :, 0] == 1

    # 4. Encontrar posições rodeadas por tecido.
    interior = np.zeros_like(tecido)

    interior[1:-1, 1:-1] = (
        tecido[:-2, :-2]
        & tecido[:-2, 1:-1]
        & tecido[:-2, 2:]
        & tecido[1:-1, :-2]
        & tecido[1:-1, 1:-1]
        & tecido[1:-1, 2:]
        & tecido[2:, :-2]
        & tecido[2:, 1:-1]
        & tecido[2:, 2:]
    )

    linhas, colunas = np.where(interior)

    if len(linhas) == 0:
        raise ValueError("Não encontrámos uma região interior de tecido.")

    # 5. Escolher uma posição de forma reprodutível.
    gerador = np.random.default_rng(42)
    indice = gerador.integers(len(linhas))

    linha = linhas[indice]
    coluna = colunas[indice]

    # 6. Converter a posição para a imagem original.
    escala_x = imagem.dimensions[0] / previa.width
    escala_y = imagem.dimensions[1] / previa.height

    centro_x = int((coluna + 0.5) * escala_x)
    centro_y = int((linha + 0.5) * escala_y)

    # 7. Calcular a região necessária para aproximadamente 0,5 µm/píxel.
    # Nesta lâmina, já confirmámos que a escala em X e Y é igual.
    tamanho_saida = 224
    mpp_alvo = 0.5

    mpp_original = float(
        imagem.properties[openslide.PROPERTY_NAME_MPP_X]
    )

    tamanho = round(tamanho_saida * mpp_alvo / mpp_original)

    x = max(
        0,
        min(centro_x - tamanho // 2, imagem.dimensions[0] - tamanho),
    )
    y = max(
        0,
        min(centro_y - tamanho // 2, imagem.dimensions[1] - tamanho),
    )

    # 8. Ler a região na resolução original.
    recorte = imagem.read_region(
        (x, y),
        0,
        (tamanho, tamanho),
    ).convert("RGB")

    # 9. Reduzir para 224 × 224 píxeis.
    recorte = recorte.resize(
        (tamanho_saida, tamanho_saida),
        resample=Image.Resampling.LANCZOS,
    )

    # 10. Guardar a imagem preparada.
    caminho_recorte = (
        pasta_resultados / f"{nome_caso}_phikon_224.png"
    )
    recorte.save(caminho_recorte)

    # 11. Guardar a localização e a escala efetivamente obtida.
    mpp_efetivo = tamanho * mpp_original / tamanho_saida

    caminho_posicao = (
        pasta_resultados / f"{nome_caso}_phikon_224_posicao.txt"
    )

    caminho_posicao.write_text(
        f"x={x}\n"
        f"y={y}\n"
        f"nivel=0\n"
        f"largura_original={tamanho}\n"
        f"altura_original={tamanho}\n"
        f"tamanho_saida={tamanho_saida}\n"
        f"mpp_original={mpp_original}\n"
        f"mpp_alvo={mpp_alvo}\n"
        f"mpp_efetivo={mpp_efetivo}\n",
        encoding="utf-8",
    )

    print("Recorte guardado em:", caminho_recorte)
    print(f"Região lida: {tamanho} × {tamanho} píxeis")
    print(f"Imagem preparada: {recorte.size}")
    print(f"Escala efetiva: {mpp_efetivo:.4f} µm/píxel")
    print(f"Posição na imagem original: x={x}, y={y}")