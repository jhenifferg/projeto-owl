import csv
from pathlib import Path

import numpy as np


PROJETO = Path(__file__).resolve().parent
EXECUCAO = "piloto_v1_1000"


def calcular_media(lote):
    # Lê uma decisão de qualidade por nome de recorte.
    decisoes = {}
    with (lote / "qualidade_recortes.csv").open(
        encoding="utf-8-sig", newline=""
    ) as ficheiro:
        for linha in csv.DictReader(ficheiro):
            nome = linha["ficheiro"]
            excluir = linha["excluir"].strip()
            if nome in decisoes or excluir not in {"0", "1"}:
                raise ValueError(f"Decisão duplicada ou inválida para {nome}.")
            decisoes[nome] = excluir

    # Lê os nomes e os vetores na ordem em que foram guardados.
    with np.load(lote / "caracteristicas.npz", allow_pickle=False) as dados:
        nomes = dados["ficheiros"].tolist()
        vetores = dados["caracteristicas"]

    if len(nomes) != len(set(nomes)) or set(nomes) != set(decisoes):
        raise ValueError("Os nomes do NPZ e do CSV de qualidade não correspondem.")
    if vetores.shape != (len(nomes), 768) or not np.isfinite(vetores).all():
        raise ValueError("A matriz de características está inválida.")

    # Aplica cada decisão ao vetor do recorte com o mesmo nome.
    manter = np.array([decisoes[nome] == "0" for nome in nomes], dtype=bool)
    vetores_mantidos = vetores[manter]
    if len(vetores_mantidos) == 0:
        raise ValueError("O lote ficou sem recortes válidos.")

    media = vetores_mantidos.mean(axis=0, dtype=np.float64)
    return media, len(vetores), len(vetores_mantidos)

def ler_rotulos():
    caminho = PROJETO / "dados" / "training_labels.csv"
    rotulos = {}

    with caminho.open(encoding="utf-8-sig", newline="") as ficheiro:
        for linha in csv.DictReader(ficheiro):
            caso = linha["case_id"].strip().removesuffix(".tif")
            if caso in rotulos:
                raise ValueError(f"Rótulo duplicado para {caso}.")

            tempo = float(linha["follow_up_years"])
            evento = int(linha["event"])
            if not np.isfinite(tempo) or tempo < 0 or evento not in {0, 1}:
                raise ValueError(f"Rótulo inválido para {caso}.")

            rotulos[caso] = (tempo, evento)

    return rotulos

def main():
    lotes = sorted((PROJETO / "resultados_piloto").glob(f"*/{EXECUCAO}"))
    if not lotes:
        raise SystemExit(f"Nenhum lote encontrado para {EXECUCAO}.")

    try:
        rotulos = ler_rotulos()
    except (OSError, ValueError, KeyError) as erro:
        raise SystemExit(f"Erro ao ler os rótulos: {erro}") from erro

    linhas = []
    for lote in lotes:
        caso = lote.parent.name
        try:
            media, total, mantidos = calcular_media(lote)
            tempo, evento = rotulos[caso]
        except KeyError as erro:
            raise SystemExit(f"Campo ou rótulo em falta no caso {caso}: {erro}") from erro
        except (OSError, ValueError) as erro:
            raise SystemExit(f"Erro no caso {caso}: {erro}") from erro

        linhas.append([caso, tempo, evento, total, mantidos, *media])
        print(f"{caso}: {mantidos}/{total} recortes mantidos")

    saida = PROJETO / "resultados" / f"pacientes_filtrados_{EXECUCAO}.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)

    colunas_phikon = [f"phikon_{i:03d}" for i in range(768)]
    with saida.open("w", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.writer(ficheiro)
        escritor.writerow([
            "case_id", "follow_up_years", "event",
            "recortes_total", "recortes_mantidos", *colunas_phikon,
        ])
        escritor.writerows(linhas)

    eventos = sum(linha[2] for linha in linhas)
    print(f"\nMatriz de características: ({len(linhas)}, 768)")
    print(f"Recorrências observadas: {eventos}/{len(linhas)}")
    print(f"Tabela guardada em: {saida}")

if __name__ == "__main__":
    main()