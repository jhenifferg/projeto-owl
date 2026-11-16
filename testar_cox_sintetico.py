from io import StringIO

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index


rng = np.random.default_rng(42)
n_pacientes = 240
n_caracteristicas = 768

colunas_phikon = [f"phikon_{i:03d}" for i in range(n_caracteristicas)]
caracteristicas = rng.normal(size=(n_pacientes, n_caracteristicas))

# Três características simulam um sinal de risco conhecido.
# As restantes são ruído.
risco_simulado = (
    1.2 * caracteristicas[:, 0]
    - 0.9 * caracteristicas[:, 1]
    + 0.7 * caracteristicas[:, 2]
)

tempo_recorrencia = rng.exponential(scale=5 * np.exp(-risco_simulado))
tempo_censura = rng.uniform(1, 10, size=n_pacientes)

tabela = pd.DataFrame(caracteristicas, columns=colunas_phikon)
tabela.insert(0, "event", (tempo_recorrencia <= tempo_censura).astype(int))
tabela.insert(0, "follow_up_years", np.minimum(tempo_recorrencia, tempo_censura))
tabela.insert(0, "case_id", [f"sintetico_{i:03d}" for i in range(n_pacientes)])

# Testa a leitura do formato CSV em memória.
dados = pd.read_csv(StringIO(tabela.to_csv(index=False)))

indices = rng.permutation(len(dados))
treino = dados.iloc[indices[:180]]
teste = dados.iloc[indices[180:]]

modelo = CoxPHFitter(penalizer=1.0)
modelo.fit(
    treino.drop(columns="case_id"),
    duration_col="follow_up_years",
    event_col="event",
)

scores = modelo.predict_log_partial_hazard(teste[colunas_phikon])

# O C-index desta função espera scores mais altos para tempos mais longos.
# Como o Cox devolve scores mais altos para maior risco, invertemos o sinal.
c_index = concordance_index(
    teste["follow_up_years"],
    -scores.to_numpy(),
    teste["event"],
)

colunas_com_sinal = colunas_phikon[:3]

modelo_3 = CoxPHFitter(penalizer=1.0)
modelo_3.fit(
    treino[["follow_up_years", "event", *colunas_com_sinal]],
    duration_col="follow_up_years",
    event_col="event",
)

scores_3 = modelo_3.predict_log_partial_hazard(teste[colunas_com_sinal])
c_index_3 = concordance_index(
    teste["follow_up_years"],
    -scores_3.to_numpy(),
    teste["event"],
)

print(f"Treino: {len(treino)} pacientes, {treino['event'].sum()} recorrências")
print(f"Teste: {len(teste)} pacientes, {teste['event'].sum()} recorrências")
print(f"C-index no teste sintético: {c_index:.3f}")
print("\nScores de risco dos primeiros cinco pacientes de teste:")
print(teste[["case_id"]].assign(score_risco=scores).head().to_string(index=False))
print(f"\nC-index com 768 características: {c_index:.3f}")
print(f"C-index com as 3 características que contêm sinal: {c_index_3:.3f}")