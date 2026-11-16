import argparse
import csv
import math
from pathlib import Path

import numpy as np

import config
from verificar_lote import verificar


def agregar(execucao, saida):
    projeto = config.PASTA_PROJETO
    lotes = sorted((projeto / "resultados_piloto").glob(f"*/{execucao}"))
    if not lotes:
        raise ValueError(f"Nenhum lote encontrado para a execução {execucao}.")

    rotulos = {}
    with (projeto / "dados" / "training_labels.csv").open(
        encoding="utf-8-sig", newline=""
    ) as ficheiro:
        for linha in csv.DictReader(ficheiro):
            caso = linha["case_id"].strip().removesuffix(".tif")
            if caso in rotulos:
                raise ValueError(f"Rótulo repetido para {caso}.")

            tempo = float(linha["follow_up_years"])
            evento = int(linha["event"])
            if not math.isfinite(tempo) or tempo < 0 or evento not in (0, 1):
                raise ValueError(f"Rótulo inválido para {caso}.")

            rotulos[caso] = (tempo, evento)

    parametros = {
        "recortes_processados": config.QUANTIDADE_RECORTES,
        "modelo": config.MODELO_PHIKON,
        "revisao_modelo": config.REVISAO_PHIKON,
        "tamanho_saida_px": config.TAMANHO_SAIDA,
        "mpp_alvo": config.MPP_ALVO,
        "fracao_minima_tecido": config.MINIMO_TECIDO,
        "semente": config.SEMENTE,
    }

    linhas = []
    for lote in lotes:
        caso = lote.parent.name
        registo = verificar(lote)

        if registo["caso"] != caso or registo["execucao"] != execucao:
            raise ValueError(f"Caso ou execução diferente do caminho de {lote}.")

        for chave, valor in parametros.items():
            if registo.get(chave) != valor:
                raise ValueError(f"{caso} tem {chave} diferente da configuração comum.")

        if caso not in rotulos:
            raise ValueError(f"Rótulo em falta para {caso}.")

        with np.load(lote / "caracteristicas.npz", allow_pickle=False) as dados:
            media = dados["caracteristicas"].mean(axis=0, dtype=np.float64)

        linhas.append([caso, *rotulos[caso], *media])

    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("x", encoding="utf-8", newline="") as ficheiro:
        escritor = csv.writer(ficheiro)
        colunas_phikon = [f"phikon_{i:03d}" for i in range(768)]
        escritor.writerow(["case_id", "follow_up_years", "event", *colunas_phikon])
        escritor.writerows(linhas)

    eventos = sum(linha[2] for linha in linhas)
    print(f"Matriz: ({len(linhas)}, 768). Recorrências observadas: {eventos}.")
    print(f"Tabela guardada em: {saida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agrega os recortes por paciente.")
    parser.add_argument("--execucao", default=config.NOME_EXECUCAO)
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()

    if not args.execucao or not all(
        c.isascii() and (c.isalnum() or c in "_-") for c in args.execucao
    ):
        parser.error("Identificador de execução inválido.")

    saida = args.saida or (
        config.PASTA_PROJETO / "resultados" / f"pacientes_{args.execucao}.csv"
    )

    try:
        agregar(args.execucao, saida)
    except (OSError, ValueError, KeyError) as erro:
        parser.exit(1, f"Erro: {erro}\n")