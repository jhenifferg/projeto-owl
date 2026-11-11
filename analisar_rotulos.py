import csv
from collections import Counter

from config import PASTA_PROJETO


caminho_csv = PASTA_PROJETO / "dados" / "training_labels.csv"

with caminho_csv.open(encoding="utf-8-sig", newline="") as ficheiro:
    registos = list(csv.DictReader(ficheiro))

contagem = Counter(int(r["event"]) for r in registos)

print("Total de registos:", len(registos))
print("Com recorrência observada:", contagem[1])
print("Sem recorrência observada:", contagem[0])
print("Identificadores diferentes:", len({r["case_id"] for r in registos}))