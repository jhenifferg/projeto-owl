from pathlib import Path

from config import PASTA_PROJETO, NOME_CASO

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, ViTModel


# 1. Localizar o recorte preparado.
pasta_projeto = PASTA_PROJETO

caminho_recorte = (
    pasta_projeto
    / "resultados"
    / f"{nome_caso}_phikon_224.png"
)

# 2. Escolher a GPU do Mac, quando disponível.
dispositivo = torch.device(
    "mps" if torch.backends.mps.is_available() else "cpu"
)
print("Dispositivo:", dispositivo)

# 3. Carregar a preparação da imagem e o modelo.
print("A carregar o Phikon...")

preparador = AutoImageProcessor.from_pretrained(
    "owkin/phikon",
    backend="pil",
)

modelo = ViTModel.from_pretrained(
    "owkin/phikon",
    add_pooling_layer=False,
)

modelo = modelo.to(dispositivo)
modelo.eval()

# 4. Abrir e preparar o recorte.
with Image.open(caminho_recorte) as ficheiro:
    recorte = ficheiro.convert("RGB")

entradas = preparador(images=recorte, return_tensors="pt")
entradas = {
    nome: valor.to(dispositivo)
    for nome, valor in entradas.items()
}

# 5. Extrair características sem treinar o modelo.
with torch.inference_mode():
    saida = modelo(**entradas)
    caracteristicas = saida.last_hidden_state[:, 0, :]

# 6. Transferir o resultado para a CPU e guardar.
vetor = caracteristicas.cpu().numpy()

if not np.isfinite(vetor).all():
    raise ValueError("O resultado contém valores numéricos inválidos.")

caminho_saida = (
    pasta_projeto
    / "resultados"
    / f"{nome_caso}_phikon_224_features.npy"
)

np.save(caminho_saida, vetor)

print("Formato das características:", vetor.shape)
print("Primeiros cinco valores:", vetor[0, :5])
print("Características guardadas em:", caminho_saida)