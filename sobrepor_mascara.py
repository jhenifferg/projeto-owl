import numpy as np
from PIL import Image

from config import PASTA_PROJETO, NOME_CASO


pasta_projeto = PASTA_PROJETO
nome_caso = NOME_CASO
pasta_resultados = pasta_projeto / "resultados" / nome_caso / "previas"

# Abrir as duas pré-visualizações que já guardámos.
imagem = Image.open(
    pasta_resultados / f"{nome_caso}_previa.png"
).convert("RGB")

mascara = Image.open(
    pasta_resultados / f"{nome_caso}_mascara_previa.png"
).convert("RGB")

# Confirmar que têm o mesmo tamanho.
if imagem.size != mascara.size:
    raise ValueError("A imagem e a máscara têm tamanhos diferentes.")

# Usar um canal da máscara e identificar os píxeis com valor 1.
valores_mascara = np.asarray(mascara)[:, :, 0]
regiao = valores_mascara == 1

# Criar uma camada vermelha, transparente fora da região selecionada.
camada = np.zeros(
    (imagem.height, imagem.width, 4),
    dtype=np.uint8
)

camada[regiao] = [255, 0, 0, 90]

# Sobrepor a camada à imagem e guardar.
sobreposicao = Image.alpha_composite(
    imagem.convert("RGBA"),
    Image.fromarray(camada)
)

caminho_saida = (
    pasta_resultados / f"{nome_caso}_sobreposicao.png"
)

sobreposicao.convert("RGB").save(caminho_saida)
print("Sobreposição guardada em:", caminho_saida)
