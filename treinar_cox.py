"""Treina e avalia um modelo de Cox regularizado com elastic net."""

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
    with caminho.open(encoding="utf-8-sig", newline="") as ficheiro:
        leitor = csv.DictReader(ficheiro)
        colunas = [
            nome for nome in (leitor.fieldnames or [])
            if nome.startswith("phikon_")
        ]
        linhas = list(leitor)

    if not linhas:
        raise ValueError(f"O ficheiro {caminho} está vazio.")
    if not colunas:
        raise ValueError("A tabela não contém colunas Phikon.")

    casos = np.array([linha["case_id"] for linha in linhas])
    tempo = np.array([float(linha["follow_up_years"]) for linha in linhas])
    eventos = np.array([int(linha["event"]) for linha in linhas])
    X = np.array([[float(linha[coluna]) for coluna in colunas] for linha in linhas])

    if len(set(casos)) != len(casos):
        raise ValueError("O CSV contém identificadores de paciente repetidos.")
    if not np.isin(eventos, [0, 1]).all():
        raise ValueError("A coluna event deve conter apenas 0 ou 1.")
    if not np.isfinite(tempo).all() or (tempo < 0).any():
        raise ValueError("A tabela contém tempos de acompanhamento inválidos.")
    if not np.isfinite(X).all():
        raise ValueError("A tabela contém características Phikon inválidas.")

    return casos, X, eventos.astype(bool), tempo, colunas


def como_y(evento, tempo):
    return np.array(
        list(zip(evento, tempo)),
        dtype=[("evento", bool), ("tempo", float)],
    )


def c_index(evento, tempo, risco):
    """Devolve None se a partição não permitir calcular o C-index."""
    try:
        return float(concordance_index_censored(evento, tempo, risco)[0])
    except ValueError:
        return None


def ajustar_caminho(X, evento, tempo, l1_ratio, alphas=None):
    """Tenta aumentar a penalização mínima se houver erro numérico."""
    for razao in (0.01, 0.05, 0.1, 0.3):
        modelo = CoxnetSurvivalAnalysis(
            l1_ratio=l1_ratio,
            alphas=alphas,
            alpha_min_ratio=razao,
            n_alphas=30,
            max_iter=100_000,
        )
        try:
            with warnings.catch_warnings():
                # Um candidato com todos os coeficientes a zero é permitido.
                warnings.filterwarnings(
                    "ignore", message="all coefficients are zero.*"
                )
                modelo.fit(X, como_y(evento, tempo))
            return modelo
        except ArithmeticError:
            if alphas is not None:
                alphas = alphas[:max(len(alphas) // 2, 1)]

    raise ArithmeticError("O Cox não convergiu com nenhum alpha.")


def ajustar_alpha_fixo(X, evento, tempo, l1_ratio, alpha):
    """Ajustar exatamente o alpha solicitado e verificar a convergência."""
    from sklearn.exceptions import ConvergenceWarning

    modelo = CoxnetSurvivalAnalysis(
        l1_ratio=l1_ratio,
        alphas=[float(alpha)],
        max_iter=300_000,
        tol=1e-7,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="all coefficients are zero.*"
        )
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            modelo.fit(X, como_y(evento, tempo))
        except ConvergenceWarning as erro:
            raise ArithmeticError(
                f"O ajuste não convergiu com alpha={alpha:.6g}."
            ) from erro

    return modelo


def escolher_alpha(
    X, evento, tempo, l1_ratio, semente,
    particoes_internas=3, diagnostico=False,
):
    """Comparar uma grelha fixa usando apenas o treino de cada partição."""
    alphas = np.logspace(1, -3, 30)

    k = min(
        particoes_internas,
        int(evento.sum()),
        int((~evento).sum()),
    )
    if k < 2:
        raise ValueError(
            "Há poucos eventos ou casos censurados para selecionar alpha."
        )

    divisor = StratifiedKFold(
        n_splits=k, shuffle=True, random_state=semente
    )
    particoes = []

    for numero, (treino, validacao) in enumerate(
        divisor.split(X, evento), start=1
    ):
        # A existência de pares depende dos desfechos da validação.
        comparavel = c_index(
            evento[validacao],
            tempo[validacao],
            np.zeros(len(validacao)),
        )
        if comparavel is None:
            if diagnostico:
                print(f"Partição {numero}: sem pares comparáveis.")
            continue

        escala = StandardScaler().fit(X[treino])
        particoes.append((
            numero,
            escala.transform(X[treino]),
            escala.transform(X[validacao]),
            evento[treino],
            tempo[treino],
            evento[validacao],
            tempo[validacao],
        ))

    if len(particoes) < 2:
        raise ValueError(
            "Menos de duas partições internas têm pares comparáveis. "
            "A seleção automática do alpha ficou indisponível."
        )

    medias = np.full(len(alphas), -np.inf)

    if diagnostico:
        print("\nAlpha | Ajustes válidos | C-index médio")

    for i, alpha in enumerate(alphas):
        pontos = []

        for (
            numero, X_treino, X_validacao,
            evento_treino, tempo_treino,
            evento_validacao, tempo_validacao,
        ) in particoes:
            try:
                modelo = ajustar_alpha_fixo(
                    X_treino,
                    evento_treino,
                    tempo_treino,
                    l1_ratio,
                    alpha,
                )
                risco = modelo.predict(X_validacao)
                if not np.isfinite(risco).all():
                    raise ArithmeticError("Scores não finitos.")

                concordancia = c_index(
                    evento_validacao, tempo_validacao, risco
                )
                if concordancia is not None:
                    pontos.append(concordancia)

            except ArithmeticError as erro:
                if diagnostico:
                    print(
                        f"  Alpha {alpha:.6g}, partição {numero}: {erro}"
                    )

        # Comparar apenas candidatos avaliados em todas as mesmas partições.
        if len(pontos) == len(particoes):
            medias[i] = np.mean(pontos)

        if diagnostico:
            valor = (
                f"{medias[i]:.6f}"
                if np.isfinite(medias[i])
                else "indisponível"
            )
            print(
                f"{alpha:.6g} | "
                f"{len(pontos)}/{len(particoes)} | {valor}"
            )

    if not np.isfinite(medias).any():
        raise ValueError(
            "Nenhum alpha teve ajustes válidos em todas as partições."
        )

    # Os alphas estão em ordem decrescente.
    # Em empate exato, escolher a penalização mais forte.
    melhor = int(np.argmax(medias))

    if diagnostico:
        print(
            f"\nPartições internas comparáveis: {len(particoes)}/{k}"
        )
        if melhor in (0, len(alphas) - 1):
            print(
                "O alpha escolhido está numa extremidade da grelha. "
                "Regista este resultado para rever o intervalo."
            )

    return (
        float(alphas[melhor]),
        "validação interna com grelha fixa",
    )


def treinar(X, evento, tempo, l1_ratio, semente):
    """Selecionar alpha e ajustar exatamente esse valor."""
    alpha, metodo = escolher_alpha(
        X, evento, tempo, l1_ratio, semente
    )
    escala = StandardScaler().fit(X)
    modelo = ajustar_alpha_fixo(
        escala.transform(X),
        evento,
        tempo,
        l1_ratio,
        alpha,
    )
    return escala, modelo, alpha, metodo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execucao", default=EXECUCAO)
    parser.add_argument("--l1-ratio", type=float, default=0.5)
    parser.add_argument("--particoes", type=int, default=5)
    parser.add_argument("--repeticoes", type=int, default=10)
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument(
        "--diagnostico-alpha",
        action="store_true",
        help="Imprime a validação interna do modelo final e termina.",
    )
    args = parser.parse_args()

    if not 0 < args.l1_ratio <= 1:
        parser.error("--l1-ratio deve ser maior que 0 e menor ou igual a 1.")
    if args.particoes < 2 or args.repeticoes < 1:
        parser.error("Indica pelo menos duas partições e uma repetição.")

    pasta = PROJETO / "resultados"
    entrada = pasta / f"pacientes_filtrados_{args.execucao}.csv"
    if not entrada.is_file():
        sys.exit(f"Não encontrei {entrada}. Corre primeiro: python agregar_pacientes.py")

    casos, X, evento, tempo, colunas = ler_tabela(entrada)
    n = len(casos)
    n_eventos = int(evento.sum())
    print(
        f"Pacientes: {n} | eventos: {n_eventos} | censurados: {n - n_eventos} "
        f"| características: {X.shape[1]}"
    )

    if args.diagnostico_alpha:
        alpha, metodo = escolher_alpha(
            X, evento, tempo, args.l1_ratio, args.semente, diagnostico=True
        )
        print(f"\nAlpha escolhido: {alpha:.6g} ({metodo})")
        return

    k = min(args.particoes, n_eventos, n - n_eventos)
    if k < 2:
        sys.exit("São precisos pelo menos dois eventos e dois casos censurados.")
    if k < args.particoes:
        print(f"A validação usa {k} partições em vez de {args.particoes}.")
    if n_eventos < 20:
        print("AVISO: há poucos eventos. Interpreta o C-index como exploratório.")

    resultados_particoes = []
    agrupados = []
    risco_fora = np.full(n, np.nan)

    for rep in range(args.repeticoes):
        semente = args.semente + rep
        divisor = StratifiedKFold(n_splits=k, shuffle=True, random_state=semente)
        risco_rep = np.full(n, np.nan)

        for parte, (treino, teste) in enumerate(divisor.split(X, evento)):
            escala, modelo, alpha, metodo = treinar(
                X[treino], evento[treino], tempo[treino], args.l1_ratio, semente
            )
            risco = modelo.predict(escala.transform(X[teste]), alpha=alpha)
            risco_rep[teste] = risco
            indice_alpha = int(np.argmin(np.abs(modelo.alphas_ - alpha)))

            # Guardar os modelos da primeira repetição para a ablação.
            if rep == 0:
                import hashlib
                import tempfile

                # Criar uma pasta própria para esta execução do treino.
                if parte == 0:
                    pasta_modelos = pasta / "modelos_validacao"
                    pasta_modelos.mkdir(parents=True, exist_ok=True)
                    pasta_validacao = Path(tempfile.mkdtemp(
                        prefix=f"{args.execucao}_",
                        dir=pasta_modelos,
                    ))
                    print("Modelos para ablação:", pasta_validacao)

                coef_particao = modelo.coef_[:, indice_alpha]
                offset_particao = float(modelo.offset_[indice_alpha])

                # Confirmar que o modelo exportado reproduz as previsões.
                risco_reconstruido = (
                    escala.transform(X[teste]) @ coef_particao
                    - offset_particao
                )
                np.testing.assert_allclose(
                    risco_reconstruido, risco, rtol=1e-6, atol=1e-8
                )

                np.savez(
                    pasta_validacao / f"particao_{parte + 1}.npz",
                    media=escala.mean_,
                    escala=escala.scale_,
                    coef=coef_particao,
                    offset=offset_particao,
                    colunas=np.array(colunas),
                    alpha=float(modelo.alphas_[indice_alpha]),
                    l1_ratio=args.l1_ratio,
                    casos_treino=casos[treino],
                    casos_teste=casos[teste],
                    scores_teste=risco,
                    repeticao=1,
                    particao=parte + 1,
                    sha256_tabela=hashlib.sha256(
                        entrada.read_bytes()
                    ).hexdigest(),
                )

                if parte == k - 1:
                    print("Modelos das partições guardados em:", pasta_validacao)

            resultados_particoes.append({
                "repeticao": rep,
                "particao": parte,
                "c_index": c_index(evento[teste], tempo[teste], risco),
                "alpha": alpha,
                "metodo_alpha": metodo,
                "coeficientes_nao_nulos": int(
                    np.count_nonzero(modelo.coef_[:, indice_alpha])
                ),
                "n_teste": len(teste),
                "eventos_teste": int(evento[teste].sum()),
            })

        c_agrupado = c_index(evento, tempo, risco_rep)
        agrupados.append(c_agrupado)
        if rep == 0:
            risco_fora = risco_rep
        valor = "n/d" if c_agrupado is None else f"{c_agrupado:.3f}"
        print(f"Repetição {rep + 1}/{args.repeticoes}: C-index agrupado = {valor}")

    validos = [
        parte["c_index"] for parte in resultados_particoes
        if parte["c_index"] is not None
    ]
    agrupados_validos = [valor for valor in agrupados if valor is not None]
    resumo = {
        "execucao": args.execucao,
        "pacientes": n,
        "eventos": n_eventos,
        "l1_ratio": args.l1_ratio,
        "particoes": k,
        "repeticoes": args.repeticoes,
        "semente": args.semente,
        "c_index_particoes_media": float(np.mean(validos)) if validos else None,
        "c_index_particoes_desvio": float(np.std(validos)) if validos else None,
        "particoes_sem_pares_comparaveis": len(resultados_particoes) - len(validos),
        "c_index_agrupado_media": (
            float(np.mean(agrupados_validos)) if agrupados_validos else None
        ),
        "c_index_agrupado_desvio": (
            float(np.std(agrupados_validos)) if agrupados_validos else None
        ),
    }

    escala, modelo, alpha, metodo = treinar(
        X, evento, tempo, args.l1_ratio, args.semente
    )
    indice_alpha = int(np.argmin(np.abs(modelo.alphas_ - alpha)))
    alpha = float(modelo.alphas_[indice_alpha])
    coef = modelo.coef_[:, indice_alpha]
    offset = float(modelo.offset_[indice_alpha])
    X_padronizado = escala.transform(X)
    risco_final = modelo.predict(X_padronizado, alpha=alpha)

    np.testing.assert_allclose(X_padronizado @ coef - offset, risco_final)
    resumo.update({
        "modelo_final_alpha": alpha,
        "modelo_final_metodo_alpha": metodo,
        "modelo_final_coeficientes_nao_nulos": int(np.count_nonzero(coef)),
        "modelo_final_c_index_treino": c_index(evento, tempo, risco_final),
    })

    with (pasta / f"avaliacao_cox_{args.execucao}.json").open(
        "w", encoding="utf-8"
    ) as ficheiro:
        json.dump(
            {
                "resumo": resumo,
                "particoes": resultados_particoes,
                "c_index_agrupado_por_repeticao": agrupados,
            },
            ficheiro,
            ensure_ascii=False,
            indent=2,
        )

    np.savez(
        pasta / f"modelo_cox_{args.execucao}.npz",
        media=escala.mean_,
        escala=escala.scale_,
        coef=coef,
        offset=offset,
        colunas=np.array(colunas),
        alpha=alpha,
        l1_ratio=args.l1_ratio,
        casos=casos,
    )

    with (pasta / f"risco_cox_{args.execucao}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as ficheiro:
        escritor = csv.writer(ficheiro)
        escritor.writerow([
            "case_id", "event", "follow_up_years",
            "risco_fora_particao_rep1", "risco_modelo_final",
        ])
        escritor.writerows(zip(casos, evento.astype(int), tempo, risco_fora, risco_final))

    def formatar(valor):
        return "n/d" if valor is None else f"{valor:.3f}"

    print("\n=== Resumo ===")
    print(
        f"C-index por partição: {formatar(resumo['c_index_particoes_media'])} "
        f"± {formatar(resumo['c_index_particoes_desvio'])} "
        f"({len(validos)} partições válidas)"
    )
    print(
        f"C-index agrupado: {formatar(resumo['c_index_agrupado_media'])} "
        f"± {formatar(resumo['c_index_agrupado_desvio'])}"
    )
    print(
        f"Modelo final: alpha = {alpha:.6g} ({metodo}), "
        f"{np.count_nonzero(coef)} coeficientes não nulos, "
        f"C-index no treino = {formatar(resumo['modelo_final_c_index_treino'])}"
    )
    print(f"Guardado em: {pasta}")


if __name__ == "__main__":
    main()