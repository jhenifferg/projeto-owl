import csv
from time import perf_counter

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, ViTModel

import json
import config

from config import (
    PASTA_PROJETO,
    NOME_CASO,
    QUANTIDADE_RECORTES,
    MODELO_PHIKON,
    REVISAO_PHIKON,
    NOME_EXECUCAO
)


# 1. Localizar o lote e as coordenadas.
pasta_lote = (
    PASTA_PROJETO / "resultados" / NOME_CASO / NOME_EXECUCAO
)

with (pasta_lote / "coordenadas.csv").open(
    encoding="utf-8", newline=""
) as ficheiro:
    registos = list(csv.DictReader(ficheiro))

if not registos:
    raise ValueError("O ficheiro de coordenadas está vazio.")

# Impedir a mistura de pacientes.
if any(registo["caso"] != NOME_CASO for registo in registos):
    raise ValueError("As coordenadas pertencem a outro caso.")

caminho_saida = pasta_lote / "caracteristicas.npz"

if caminho_saida.exists():
    raise FileExistsError(
        "As características deste lote já foram guardadas."
    )

# Verificar que os recortes foram concluídos com a configuração atual.
preparacao = json.loads((pasta_lote / "preparacao.json").read_text(encoding="utf-8"))
esperado = {
    "caso": NOME_CASO,
    "execucao": NOME_EXECUCAO,
    "quantidade_recortes": QUANTIDADE_RECORTES,
    "tamanho_saida_px": config.TAMANHO_SAIDA,
    "mpp_alvo": config.MPP_ALVO,
    "fracao_minima_tecido": config.MINIMO_TECIDO,
    "semente": config.SEMENTE,
}
if preparacao != esperado or len(registos) != QUANTIDADE_RECORTES:
    raise ValueError("A configuração difere da preparação dos recortes. Restaure-a ou crie uma nova execução.")

# 2. Selecionar o dispositivo.
dispositivo = torch.device(
    "mps" if torch.backends.mps.is_available() else "cpu"
)
print("Dispositivo:", dispositivo)

# 3. Carregar o modelo uma única vez.
inicio_carga = perf_counter()

preparador = AutoImageProcessor.from_pretrained(
    MODELO_PHIKON,
    revision=REVISAO_PHIKON,
    backend="pil",
)

modelo = ViTModel.from_pretrained(
    MODELO_PHIKON,
    revision=REVISAO_PHIKON,
    add_pooling_layer=False,
).to(dispositivo)

modelo.eval()

if dispositivo.type == "mps":
    torch.mps.synchronize()

tempo_carga = perf_counter() - inicio_carga
print(f"Modelo carregado em {tempo_carga:.2f} segundos")

# 4. Processar um recorte de cada vez.
inicio_extracao = perf_counter()
vetores = []

with torch.inference_mode():
    for numero, registo in enumerate(registos, start=1):
        caminho_png = pasta_lote / registo["ficheiro"]

        with Image.open(caminho_png) as ficheiro:
            recorte = ficheiro.convert("RGB")

        entradas = preparador(
            images=recorte,
            return_tensors="pt",
        )

        entradas = {
            nome: valor.to(dispositivo)
            for nome, valor in entradas.items()
        }

        saida = modelo(**entradas)

        vetor = (
            saida.last_hidden_state[:, 0, :]
            .cpu()
            .numpy()[0]
        )

        vetores.append(vetor)
        print(f"Recorte {numero}/{len(registos)} processado")

caracteristicas = np.stack(vetores).astype(np.float32)

if not np.isfinite(caracteristicas).all():
    raise ValueError("Foram produzidas características inválidas.")

if dispositivo.type == "mps":
    torch.mps.synchronize()

tempo_extracao = perf_counter() - inicio_extracao

# 5. Guardar características e coordenadas na mesma ordem.
coordenadas = np.array(
    [(int(r["x"]), int(r["y"])) for r in registos],
    dtype=np.int64,
)

ficheiros = np.array([r["ficheiro"] for r in registos])

np.savez_compressed(
    caminho_saida,
    caracteristicas=caracteristicas,
    coordenadas=coordenadas,
    ficheiros=ficheiros,
    caso=np.array(NOME_CASO),
    modelo=np.array(MODELO_PHIKON),
    revisao_modelo=np.array(REVISAO_PHIKON),
)

registo_execucao = {
    "preparacao": preparacao,
    "caso": NOME_CASO,
    "execucao": NOME_EXECUCAO,
    "modelo": MODELO_PHIKON,
    "revisao_modelo": REVISAO_PHIKON,
    "recortes_processados": len(registos),
    "formato_caracteristicas": list(caracteristicas.shape),
    "tamanho_saida_px": config.TAMANHO_SAIDA,
    "mpp_alvo": config.MPP_ALVO,
    "fracao_minima_tecido": config.MINIMO_TECIDO,
    "semente": config.SEMENTE,
    "dispositivo": str(dispositivo),
    "tempo_extracao_s": round(tempo_extracao, 2),
}

caminho_registo = pasta_lote / "execucao.json"
caminho_registo.write_text(
    json.dumps(registo_execucao, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print("Configuração guardada em:", caminho_registo)

print("Formato das características:", caracteristicas.shape)
print(f"Tempo de extração: {tempo_extracao:.2f} segundos")
print(
    "Tempo médio por recorte: "
    f"{tempo_extracao / len(registos):.3f} segundos"
)
print(f"Tamanho do resultado: {caminho_saida.stat().st_size / 1024:.1f} KB")
print("Guardado em:", caminho_saida)
