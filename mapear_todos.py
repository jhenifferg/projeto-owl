"""Executar o mapa de influência para todos os lotes disponíveis."""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from config import NOME_EXECUCAO, PASTA_PROJETO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execucao", default=NOME_EXECUCAO)
    args = parser.parse_args()

    projeto = PASTA_PROJETO
    script = projeto / "mapear_influencia.py"
    caminho_riscos = (
        projeto / "resultados" / f"risco_cox_{args.execucao}.csv"
    )

    if not script.is_file():
        parser.error(f"Script em falta: {script}")

    if not caminho_riscos.is_file():
        parser.error("Falta o CSV de riscos. Executa primeiro o treino do Cox.")

    with caminho_riscos.open(encoding="utf-8-sig", newline="") as ficheiro:
        casos_modelo = {
            linha["case_id"] for linha in csv.DictReader(ficheiro)
        }

    lotes = sorted(
        (projeto / "resultados_piloto").glob(f"*/{args.execucao}")
    )
    if not lotes:
        parser.error("Não foram encontrados lotes para esta execução.")

    concluidos = []
    pendentes = []
    falhas = []

    for lote in lotes:
        caso = lote.parent.name
        print(f"\n--- {caso} ---", flush=True)

        if caso not in casos_modelo:
            motivo = "Ainda não consta no CSV de riscos do modelo."
            pendentes.append((caso, motivo))
            print(motivo)
            continue

        previa = (
            projeto / "resultados" / caso / "previas" / f"{caso}_previa.png"
        )
        lamina = projeto / "imagens" / f"{caso}.tif"
        metadados = lote / "metadados_lamina.json"

        if not previa.is_file():
            motivo = f"Prévia em falta: {previa}"
            pendentes.append((caso, motivo))
            print(motivo)
            continue

        comando = [
            sys.executable,
            str(script),
            "--caso", caso,
            "--execucao", args.execucao,
        ]

        # Com o TIFF presente, o script individual lê as dimensões.
        # Sem o TIFF, usa as dimensões registadas no JSON do lote.
        if not lamina.is_file():
            if not metadados.is_file():
                motivo = "Faltam o TIFF e o metadados_lamina.json."
                pendentes.append((caso, motivo))
                print(motivo)
                continue

            try:
                dados = json.loads(metadados.read_text(encoding="utf-8"))
                largura = dados["largura_original"]
                altura = dados["altura_original"]

                if (
                    type(largura) is not int
                    or type(altura) is not int
                    or largura <= 0
                    or altura <= 0
                ):
                    raise ValueError("Dimensões inválidas.")

            except (OSError, ValueError, KeyError) as erro:
                falhas.append((caso, str(erro)))
                print(f"Erro nos metadados: {erro}")
                continue

            comando.extend([
                "--largura-original", str(largura),
                "--altura-original", str(altura),
            ])

        processo = subprocess.run(comando, cwd=projeto)

        if processo.returncode == 0:
            concluidos.append(caso)
        else:
            motivo = f"O script terminou com código {processo.returncode}."
            falhas.append((caso, motivo))

    print("\n=== Resultado do processamento ===")
    print(f"Concluídos: {len(concluidos)}")
    print(f"Pendentes: {len(pendentes)}")
    print(f"Falhas: {len(falhas)}")

    for caso, motivo in pendentes + falhas:
        print(f"{caso}: {motivo}")


if __name__ == "__main__":
    main()