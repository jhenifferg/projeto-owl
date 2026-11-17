"""Treina e avalia o modelo de Cox regularizado (elastic net) a partir da tabela de pacientes.

Entrada: resultados/pacientes_filtrados_<execucao>.csv, criado por agregar_pacientes.py.

Avaliação (validação cruzada repetida, estratificada pelo evento):
  - em cada partição de treino: normalização (StandardScaler) e escolha da força de
    regularização (alpha) por validação cruzada interna, usando só os dados de treino;
  - no teste: C-index de Harrell (concordance_index_censored).
São reportados o C-index médio por partição e o C-index "agrupado" por repetição
(previsões fora da partição de todos os pacientes avaliadas juntas), mais estável com poucos casos.

No fim treina o modelo final com todos os pacientes e guarda-o, para as experiências de perturbação.

Uso:
    python treinar_cox.py
    python treinar_cox.py --l1-ratio 0.5 --particoes 5 --repeticoes 10 --semente 42

Saídas (em resultados/):
    avaliacao_cox_<execucao>.json   C-index por partição e resumo
    modelo_cox_<execucao>.npz       normalização, coeficientes e alpha do modelo final
    risco_cox_<execucao>.csv        risco previsto fora da partição (1.ª repetição) e no modelo final
"""

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sksurv.linear_model import CoxnetSurvivalAnalysis
from sksurv.metrics import concordance_index_censored

PROJETO = Path(__file__).resolve().parent
EXECUCAO = "piloto_v1_1000"


def ler_tabela(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as ficheiro:
        linhas = list(csv.DictReader(ficheiro))
    if not linhas:
        sys.exit(f"{caminho} está vazio.")
    colunas = [c for c in linhas[0] if c.startswith("phikon_")]
    casos = np.array([l["case_id"] for l in linhas])
    tempo = np.array([float(l["follow_up_years"]) for l in linhas])
    evento = np.array([int(l["event"]) == 1 for l in linhas])
    X = np.array([[float(l[c]) for c in colunas] for l in linhas])
    return casos, X, evento, tempo


def como_y(evento, tempo):
    return np.array(list(zip(evento, tempo)), dtype=[("evento", bool), ("tempo", float)])


def c_index(evento, tempo, risco):
    """C-index de Harrell; devolve None se não houver pares comparáveis."""
    try:
        return float(concordance_index_censored(evento, tempo, risco)[0])
    except ValueError:
        return None


def ajustar_caminho(X, evento, tempo, l1_ratio, alphas=None):
    """Ajusta o caminho de regularização; aumenta o alpha mínimo se houver erro numérico."""
    for razao in (0.01, 0.05, 0.1, 0.3):
        modelo = CoxnetSurvivalAnalysis(l1_ratio=l1_ratio, alphas=alphas,
                                        alpha_min_ratio=razao, n_alphas=30, max_iter=100000)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                modelo.fit(X, como_y(evento, tempo))
            return modelo
        except ArithmeticError:
            if alphas is not None:
                # Com alphas fixos, remove os mais pequenos e tenta de novo.
                alphas = alphas[: max(len(alphas) // 2, 1)]
            continue
    raise ArithmeticError("O Cox não convergiu com nenhum alpha.")


def escolher_alpha(X, evento, tempo, l1_ratio, semente, particoes_internas=3):
    """Escolhe o alpha por validação cruzada interna, só com os dados recebidos."""
    print("\nAlpha          Partições válidas   C-index médio   Coef. ativos*")
    for i, alpha_candidato in enumerate(alphas):
        c_medio = f"{medias[i]:.3f}" if pontuacoes[i] else "n/d"
        ativos = np.count_nonzero(caminho.coef_[:, i])
        print(
            f"{alpha_candidato:<14.6g} "
            f"{len(pontuacoes[i])}/{k:<18} "
            f"{c_medio:<15} {ativos}"
        )
    print("* Coeficientes ativos no ajuste com os dados recebidos pela função.")
    escala = StandardScaler().fit(X)
    Xn = escala.transform(X)
    caminho = ajustar_caminho(Xn, evento, tempo, l1_ratio)
    alphas = caminho.alphas_

    k = min(particoes_internas, int(evento.sum()), int((~evento).sum()))
    if k < 2:
        # Poucos eventos para validação interna: usa um alpha intermédio do caminho.
        return float(alphas[len(alphas) // 2]), "meio do caminho (poucos eventos)"

    pontuacoes = [[] for _ in alphas]
    divisor = StratifiedKFold(n_splits=k, shuffle=True, random_state=semente)
    for treino, valid in divisor.split(X, evento):
        esc = StandardScaler().fit(X[treino])
        try:
            modelo = ajustar_caminho(esc.transform(X[treino]), evento[treino], tempo[treino],
                                     l1_ratio, alphas=alphas)
        except ArithmeticError:
            continue
        Xv = esc.transform(X[valid])
        for i, a in enumerate(alphas):
            if a < modelo.alphas_.min():
                continue
            c = c_index(evento[valid], tempo[valid], modelo.predict(Xv, alpha=a))
            if c is not None:
                pontuacoes[i].append(c)

    medias = [np.mean(p) if p else -np.inf for p in pontuacoes]
    if not np.isfinite(max(medias)):
        return float(alphas[len(alphas) // 2]), "meio do caminho (sem C-index interno)"
    return float(alphas[int(np.argmax(medias))]), "validação cruzada interna"


def treinar(X, evento, tempo, l1_ratio, semente):
    """Normaliza, escolhe alpha e ajusta o Cox; devolve (escala, modelo, alpha, metodo)."""
    alpha, metodo = escolher_alpha(X, evento, tempo, l1_ratio, semente)
    escala = StandardScaler().fit(X)
    modelo = ajustar_caminho(escala.transform(X), evento, tempo, l1_ratio)
    alpha = max(alpha, float(modelo.alphas_.min()))
    return escala, modelo, alpha, metodo


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execucao", default=EXECUCAO)
    parser.add_argument("--l1-ratio", type=float, default=0.5,
                        help="mistura L1/L2 do elastic net (1 = lasso, perto de 0 = ridge)")
    parser.add_argument("--particoes", type=int, default=5)
    parser.add_argument("--repeticoes", type=int, default=10)
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args()

    entrada = PROJETO / "resultados" / f"pacientes_filtrados_{args.execucao}.csv"
    if not entrada.exists():
        sys.exit(f"Não encontrei {entrada}. Corre primeiro: python agregar_pacientes.py")
    casos, X, evento, tempo = ler_tabela(entrada)
    n, n_eventos = len(casos), int(evento.sum())
    print(f"Pacientes: {n} | eventos: {n_eventos} | censurados: {n - n_eventos} "
          f"| características: {X.shape[1]}")

    k = min(args.particoes, n_eventos, n - n_eventos)
    if k < 2:
        sys.exit("São precisos pelo menos 2 eventos e 2 casos censurados para validar o modelo.")
    if k < args.particoes:
        print(f"AVISO: só há {n_eventos} eventos; a validação usa {k} partições em vez de {args.particoes}.")
    if n_eventos < 20:
        print("AVISO: com menos de ~20 eventos o C-index é muito instável. "
              "Usa estes resultados só para testar o código.")

    resultados_particoes, agrupados = [], []
    risco_fora = np.full(n, np.nan)
    for rep in range(args.repeticoes):
        divisor = StratifiedKFold(n_splits=k, shuffle=True, random_state=args.semente + rep)
        risco_rep = np.full(n, np.nan)
        for parte, (treino, teste) in enumerate(divisor.split(X, evento)):
            escala, modelo, alpha, metodo = treinar(X[treino], evento[treino], tempo[treino],
                                                    args.l1_ratio, args.semente + rep)
            risco = modelo.predict(escala.transform(X[teste]), alpha=alpha)
            risco_rep[teste] = risco
            c = c_index(evento[teste], tempo[teste], risco)
            n_coef = int(np.sum(np.abs(
                modelo.coef_[:, np.argmin(np.abs(modelo.alphas_ - alpha))]) > 0))
            resultados_particoes.append({"repeticao": rep, "particao": parte, "c_index": c,
                                         "alpha": alpha, "metodo_alpha": metodo,
                                         "coeficientes_nao_nulos": n_coef,
                                         "n_teste": int(len(teste)),
                                         "eventos_teste": int(evento[teste].sum())})
        c_agr = c_index(evento, tempo, risco_rep)
        agrupados.append(c_agr)
        if rep == 0:
            risco_fora = risco_rep
        print(f"Repetição {rep + 1}/{args.repeticoes}: C-index agrupado = "
              + (f"{c_agr:.3f}" if c_agr is not None else "n/d"))

    validos = [r["c_index"] for r in resultados_particoes if r["c_index"] is not None]
    agrupados_validos = [c for c in agrupados if c is not None]
    resumo = {
        "execucao": args.execucao, "pacientes": n, "eventos": n_eventos,
        "l1_ratio": args.l1_ratio, "particoes": k, "repeticoes": args.repeticoes,
        "semente": args.semente,
        "c_index_particoes_media": float(np.mean(validos)) if validos else None,
        "c_index_particoes_desvio": float(np.std(validos)) if validos else None,
        "particoes_sem_pares_comparaveis": len(resultados_particoes) - len(validos),
        "c_index_agrupado_media": float(np.mean(agrupados_validos)) if agrupados_validos else None,
        "c_index_agrupado_desvio": float(np.std(agrupados_validos)) if agrupados_validos else None,
    }

    # Modelo final com todos os pacientes (para as experiências de perturbação).
    escala, modelo, alpha, metodo = treinar(X, evento, tempo, args.l1_ratio, args.semente)
    indice_alpha = int(np.argmin(np.abs(modelo.alphas_ - alpha)))
    coef = modelo.coef_[:, indice_alpha]
    risco_final = modelo.predict(escala.transform(X), alpha=alpha)
    resumo.update({"modelo_final_alpha": alpha, "modelo_final_metodo_alpha": metodo,
                   "modelo_final_coeficientes_nao_nulos": int(np.sum(np.abs(coef) > 0)),
                   "modelo_final_c_index_treino": c_index(evento, tempo, risco_final)})

    pasta = PROJETO / "resultados"
    with open(pasta / f"avaliacao_cox_{args.execucao}.json", "w", encoding="utf-8") as f:
        json.dump({"resumo": resumo, "particoes": resultados_particoes,
                   "c_index_agrupado_por_repeticao": agrupados}, f, ensure_ascii=False, indent=2)
    np.savez(pasta / f"modelo_cox_{args.execucao}.npz", media=escala.mean_, escala=escala.scale_,
             coef=coef, alpha=alpha, l1_ratio=args.l1_ratio, casos=casos)
    with open(pasta / f"risco_cox_{args.execucao}.csv", "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["case_id", "event", "follow_up_years",
                           "risco_fora_particao_rep1", "risco_modelo_final"])
        for linha in zip(casos, evento.astype(int), tempo, risco_fora, risco_final):
            escritor.writerow(linha)

    def fmt(v):
        return "n/d" if v is None else f"{v:.3f}"
    print("\n=== Resumo ===")
    print(f"C-index por partição:  {fmt(resumo['c_index_particoes_media'])} "
          f"± {fmt(resumo['c_index_particoes_desvio'])} "
          f"({len(validos)} partições válidas)")
    print(f"C-index agrupado:      {fmt(resumo['c_index_agrupado_media'])} "
          f"± {fmt(resumo['c_index_agrupado_desvio'])} ({len(agrupados_validos)} repetições)")
    print(f"Modelo final: alpha = {alpha:.4g} ({metodo}), "
          f"{resumo['modelo_final_coeficientes_nao_nulos']} coeficientes não nulos, "
          f"C-index no treino = {fmt(resumo['modelo_final_c_index_treino'])} (otimista)")
    print(f"Guardado em: {pasta}")


if __name__ == "__main__":
    main()
