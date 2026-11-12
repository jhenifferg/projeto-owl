"""Marca os recortes que são quase só fundo (vidro) ou tinta, sem alterar o lote.

O lote (NPZ, coordenadas.csv, execucao.json) não é modificado. O script apenas mede
cada recorte e escreve uma tabela de qualidade, para que a média de cada paciente
possa ignorar os recortes marcados com excluir = 1.

De onde vêm os recortes (por esta ordem):
  1. dos PNG em resultados/<caso>/<execucao>/, se ainda existirem;
  2. senão, da lâmina em imagens/<caso>.tif, lendo cada recorte nas coordenadas
     guardadas em coordenadas.csv (não é preciso voltar a extrair nem correr o Phikon).

Uso:
    python filtrar_recortes.py                     # caso e execução do config_local.json
    python filtrar_recortes.py --caso case_radboud_0661 --execucao piloto_v1_1000
    python filtrar_recortes.py --todos             # todos os lotes em resultados/ e resultados_piloto/
    python filtrar_recortes.py --excluir-tinta     # também exclui recortes com muita tinta
    python filtrar_recortes.py --usar-lamina       # lê da lâmina mesmo havendo PNG (comparação)

Saídas:
    resultados_piloto/<caso>/<execucao>/qualidade_recortes.csv   (para partilhar)
    resultados/<caso>/<execucao>/qualidade_recortes.csv          (cópia local)
    resultados/<caso>/<execucao>/recortes_excluidos.png          miniaturas dos excluídos
    resultados/<caso>/<execucao>/recortes_limite.png             mantidos mais perto do limiar
    resultados/<caso>/<execucao>/mapa_filtragem.png              verde = mantido, vermelho = excluído
"""

import argparse
import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import config

PASTA_PROJETO = Path(config.PASTA_PROJETO)

# Um píxel conta como fundo se for claro e quase sem cor (vidro, lamela).
LIMIAR_SATURACAO_FUNDO = 0.08
LIMIAR_BRILHO_FUNDO = 0.85
# Um píxel conta como tinta se for muito escuro.
LIMIAR_BRILHO_TINTA = 0.20

# Um recorte é excluído se tiver menos do que esta fração de píxeis com cor de tecido...
# Testado no 0661: 0.25 limpa o vidro; 0.15 deixava passar recortes de vidro.
MIN_TECIDO_REAL = 0.25
# ...e só se, além disso, for liso: a mediana do desvio-padrão local do cinzento
# (janela 7x7) tem de ficar abaixo deste valor. O vidro é liso; o tecido, mesmo pálido,
# tem textura (fibras, núcleos). Calibrado com o 0661 (vidro: 1.0 a 3.3) e o 0149
# (tecido pálido: mediana 6.9).
MAX_TEXTURA_FUNDO = 3.5
# Com --excluir-tinta, um recorte é excluído se tiver mais do que esta fração de tinta.
MAX_TINTA = 0.30

LARGURA_MAXIMA_MAPA = 2500
MAX_MINIATURAS = 48
LADO_MINIATURA = 112
COLUNAS_MONTAGEM = 8


class FonteRecortes:
    """Dá acesso aos recortes de um lote, a partir dos PNG ou da lâmina."""

    def __init__(self, caso, pasta_png, linhas, forcar_lamina=False):
        self.pasta_png = pasta_png
        self.linhas = linhas
        self.lamina = None
        nomes = [linha["ficheiro"] for linha in linhas]
        self.usa_png = not forcar_lamina and pasta_png.exists() and all((pasta_png / n).exists() for n in nomes)
        self.caminho_lamina = PASTA_PROJETO / "imagens" / f"{caso}.tif"
        if not self.usa_png:
            if not self.caminho_lamina.exists():
                raise FileNotFoundError(
                    "Os recortes PNG já não existem e a lâmina também não está em "
                    f"{self.caminho_lamina}. Descarrega a lâmina do SURFdrive para imagens/ "
                    "e volta a correr (não é preciso repetir a extração nem o Phikon)."
                )
            import openslide
            self.lamina = openslide.OpenSlide(str(self.caminho_lamina))

    def descricao(self):
        return "PNG guardados" if self.usa_png else f"lâmina {self.caminho_lamina.name}"

    def recorte(self, indice):
        linha = self.linhas[indice]
        if self.usa_png:
            with Image.open(self.pasta_png / linha["ficheiro"]) as imagem:
                return imagem.convert("RGB")
        lado = int(float(linha.get("largura_original") or 462))
        alto = int(float(linha.get("altura_original") or lado))
        saida = int(float(linha.get("tamanho_saida") or 224))
        nivel = int(float(linha.get("nivel") or 0))
        regiao = self.lamina.read_region((int(float(linha["x"])), int(float(linha["y"]))),
                                         nivel, (lado, alto))
        return regiao.convert("RGB").resize((saida, saida), Image.BILINEAR)

    def fechar(self):
        if self.lamina is not None:
            self.lamina.close()


def desvio_local(cinzento, janela=7):
    """Desvio-padrão do cinzento numa janela quadrada à volta de cada píxel."""
    pad = janela // 2
    a = np.pad(cinzento.astype(np.float64) - float(cinzento.mean()), pad, mode="reflect")
    s1 = np.cumsum(np.cumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    s2 = np.cumsum(np.cumsum(np.pad(a * a, ((1, 0), (1, 0))), 0), 1)
    def soma(s):
        return s[janela:, janela:] - s[:-janela, janela:] - s[janela:, :-janela] + s[:-janela, :-janela]
    n = janela * janela
    media = soma(s1) / n
    return np.sqrt(np.maximum(soma(s2) / n - media * media, 0))


def medir_recorte(imagem):
    """Devolve (fração de tecido real, fração de tinta, medidas de diagnóstico)."""
    hsv = np.asarray(imagem.convert("HSV"), dtype=np.float32) / 255.0
    saturacao = hsv[..., 1]
    brilho = hsv[..., 2]
    fundo = (saturacao < LIMIAR_SATURACAO_FUNDO) & (brilho > LIMIAR_BRILHO_FUNDO)
    tinta = brilho < LIMIAR_BRILHO_TINTA
    cinzento = np.asarray(imagem.convert("L"), dtype=np.float32)
    desvio = desvio_local(cinzento)
    diagnostico = {
        "sat_p50": round(float(np.percentile(saturacao, 50)), 4),
        "sat_p90": round(float(np.percentile(saturacao, 90)), 4),
        "brilho_p50": round(float(np.percentile(brilho, 50)), 4),
        "brilho_p10": round(float(np.percentile(brilho, 10)), 4),
        "textura_p50": round(float(np.percentile(desvio, 50)), 3),
        "fracao_textura3": round(float((desvio > 3).mean()), 4),
        "fracao_textura6": round(float((desvio > 6).mean()), 4),
        "fracao_sat04": round(float((saturacao > 0.04).mean()), 4),
    }
    return float(1.0 - fundo.mean()), float(tinta.mean()), diagnostico


def gravar_imagem(imagem, destino, titulo):
    """Grava a imagem; se o Windows/OneDrive bloquear o ficheiro, avisa e continua."""
    try:
        imagem.save(destino)
        print(f"  {titulo}: {destino}")
    except OSError as erro:
        print(f"  AVISO: não foi possível gravar {destino.name} ({erro}). "
              "Fecha o ficheiro no VS Code ou espera que o OneDrive sincronize, e volta a correr.")


def montar_miniaturas(fonte, indices, destino, titulo):
    """Guarda uma grelha de miniaturas para inspeção visual."""
    indices = indices[:MAX_MINIATURAS]
    if not indices:
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass
        return
    linhas = (len(indices) + COLUNAS_MONTAGEM - 1) // COLUNAS_MONTAGEM
    colunas = min(len(indices), COLUNAS_MONTAGEM)
    montagem = Image.new("RGB", (colunas * LADO_MINIATURA, linhas * LADO_MINIATURA), "white")
    for i, indice in enumerate(indices):
        miniatura = fonte.recorte(indice).resize((LADO_MINIATURA, LADO_MINIATURA))
        montagem.paste(miniatura, ((i % COLUNAS_MONTAGEM) * LADO_MINIATURA,
                                   (i // COLUNAS_MONTAGEM) * LADO_MINIATURA))
    gravar_imagem(montagem, destino, titulo)


def desenhar_mapa(caso, pasta_local, linhas, resultados):
    """Desenha os recortes sobre a lâmina: verde = mantido, vermelho = excluído."""
    caminho_imagem = PASTA_PROJETO / "imagens" / f"{caso}.tif"
    if not caminho_imagem.exists():
        print(f"  Mapa não gerado: falta {caminho_imagem}")
        return
    import openslide

    with openslide.OpenSlide(str(caminho_imagem)) as lamina:
        # Nível mais detalhado cuja largura não passa de LARGURA_MAXIMA_MAPA.
        nivel = lamina.level_count - 1
        for n, (largura, _) in enumerate(lamina.level_dimensions):
            if largura <= LARGURA_MAXIMA_MAPA:
                nivel = n
                break
        reducao = lamina.level_downsamples[nivel]
        fundo = lamina.read_region((0, 0), nivel, lamina.level_dimensions[nivel]).convert("RGB")

    desenho = ImageDraw.Draw(fundo)
    # Primeiro os mantidos e depois os excluídos, para os vermelhos ficarem por cima.
    for querer_excluidos in (False, True):
        for linha, resultado in zip(linhas, resultados):
            if bool(resultado["excluir"]) != querer_excluidos:
                continue
            x0 = float(linha["x"]) / reducao
            y0 = float(linha["y"]) / reducao
            lado = max(float(linha.get("largura_original") or 462) / reducao, 3)
            cor = (220, 0, 0) if querer_excluidos else (0, 170, 0)
            desenho.rectangle([x0, y0, x0 + lado, y0 + lado], outline=cor,
                              width=2 if querer_excluidos else 1)

    n_excluidos = sum(r["excluir"] for r in resultados)
    desenho.rectangle([5, 5, 330, 45], fill="white")
    desenho.text((10, 9), f"verde: mantidos ({len(resultados) - n_excluidos})", fill=(0, 140, 0))
    desenho.text((10, 26), f"vermelho: excluidos ({n_excluidos})", fill=(200, 0, 0))
    gravar_imagem(fundo, pasta_local / "mapa_filtragem.png", "Mapa da filtragem")


def encontrar_lote(caso, execucao):
    """Devolve (pasta com coordenadas.csv, pasta local de resultados, pasta de partilha)."""
    pasta_local = PASTA_PROJETO / "resultados" / caso / execucao
    pasta_partilha = PASTA_PROJETO / "resultados_piloto" / caso / execucao
    for pasta in (pasta_local, pasta_partilha):
        if (pasta / "coordenadas.csv").exists():
            return pasta, pasta_local, pasta_partilha
    raise FileNotFoundError(
        f"Não encontrei coordenadas.csv para {caso}/{execucao} "
        "em resultados/ nem em resultados_piloto/ (faz git pull?)."
    )


def processar_lote(caso, execucao, excluir_tinta, forcar_lamina=False):
    print(f"\n{caso} / {execucao}")
    pasta_dados, pasta_local, pasta_partilha = encontrar_lote(caso, execucao)

    with open(pasta_dados / "coordenadas.csv", encoding="utf-8", newline="") as ficheiro:
        linhas = list(csv.DictReader(ficheiro))
    nomes = [linha["ficheiro"] for linha in linhas]

    # Confirma que a ordem do CSV é a mesma do NPZ, para os índices coincidirem.
    for pasta in (pasta_dados, pasta_local, pasta_partilha):
        caminho_npz = pasta / "caracteristicas.npz"
        if caminho_npz.exists():
            with np.load(caminho_npz) as dados:
                nomes_npz = [str(nome) for nome in dados["ficheiros"]]
                n_caracteristicas = dados["caracteristicas"].shape[0]
            if nomes_npz != nomes or n_caracteristicas != len(nomes):
                raise ValueError(f"A ordem dos recortes em {caminho_npz} não coincide "
                                 "com coordenadas.csv.")
            break

    fonte = FonteRecortes(caso, pasta_local, linhas, forcar_lamina)
    print(f"  Recortes lidos de: {fonte.descricao()}")
    try:
        resultados = []
        for indice, (linha, nome) in enumerate(zip(linhas, nomes)):
            fracao_tecido, fracao_tinta, diagnostico = medir_recorte(fonte.recorte(indice))
            motivos = []
            if (fracao_tecido < MIN_TECIDO_REAL
                    and diagnostico["textura_p50"] < MAX_TEXTURA_FUNDO):
                motivos.append("fundo")
            if excluir_tinta and fracao_tinta > MAX_TINTA:
                motivos.append("tinta")
            resultados.append({
                "indice": indice,
                "ficheiro": nome,
                "x": linha.get("x", ""),
                "y": linha.get("y", ""),
                "fracao_tecido_real": round(fracao_tecido, 4),
                "fracao_tinta": round(fracao_tinta, 4),
                "excluir": 1 if motivos else 0,
                "motivo": "+".join(motivos),
                **diagnostico,
            })

        pasta_local.mkdir(parents=True, exist_ok=True)
        # Em modo de comparação não substitui a tabela feita a partir dos PNG.
        sufixo = "_lamina" if forcar_lamina else ""
        caminho_saida = pasta_local / f"qualidade_recortes{sufixo}.csv"
        with open(caminho_saida, "w", encoding="utf-8", newline="") as ficheiro:
            escritor = csv.DictWriter(ficheiro, fieldnames=list(resultados[0].keys()))
            escritor.writeheader()
            escritor.writerows(resultados)

        excluidos = [r["indice"] for r in resultados if r["excluir"]]
        mantidos = [r["indice"] for r in sorted((r for r in resultados if not r["excluir"]),
                                                 key=lambda r: r["fracao_tecido_real"])]
        com_tinta = sum(1 for r in resultados if r["fracao_tinta"] > MAX_TINTA)
        tecido = np.array([r["fracao_tecido_real"] for r in resultados])

        print(f"  Recortes: {len(resultados)} | excluídos: {len(excluidos)} "
              f"({100 * len(excluidos) / len(resultados):.1f}%) | mantidos: {len(mantidos)}")
        print(f"  Fração de tecido real: mínimo {tecido.min():.2f}, "
              f"mediana {np.median(tecido):.2f}, máximo {tecido.max():.2f}")
        print(f"  Recortes com mais de {MAX_TINTA:.0%} de tinta: {com_tinta}"
              + ("" if excluir_tinta else " (não excluídos; usa --excluir-tinta)"))
        print(f"  Tabela guardada em: {caminho_saida}")

        if not forcar_lamina:
            montar_miniaturas(fonte, excluidos, pasta_local / "recortes_excluidos.png",
                              "Excluídos")
            montar_miniaturas(fonte, mantidos, pasta_local / "recortes_limite.png",
                              "Mantidos mais perto do limiar")
    finally:
        fonte.fechar()

    if not forcar_lamina:
        desenhar_mapa(caso, pasta_local, linhas, resultados)

    if forcar_lamina:
        comparar_com_png(pasta_local, resultados)
        return

    if pasta_partilha.exists():
        shutil.copy2(caminho_saida, pasta_partilha / caminho_saida.name)
        print(f"  Cópia para partilha: {pasta_partilha / caminho_saida.name}")


def comparar_com_png(pasta_local, resultados):
    """Compara a leitura pela lâmina com a tabela feita a partir dos PNG."""
    caminho_png = pasta_local / "qualidade_recortes.csv"
    if not caminho_png.exists():
        print("  Sem tabela dos PNG para comparar (corre primeiro sem --usar-lamina).")
        return
    with open(caminho_png, encoding="utf-8", newline="") as ficheiro:
        anteriores = list(csv.DictReader(ficheiro))
    iguais = sum(int(a["excluir"]) == r["excluir"] for a, r in zip(anteriores, resultados))
    diferenca = np.abs(np.array([float(a["fracao_tecido_real"]) for a in anteriores])
                       - np.array([r["fracao_tecido_real"] for r in resultados]))
    print(f"  Comparação com os PNG: mesma decisão em {iguais}/{len(resultados)} recortes; "
          f"diferença média da fração de tecido {diferenca.mean():.4f} "
          f"(máxima {diferenca.max():.4f})")


def listar_todos():
    lotes = set()
    for raiz in ("resultados", "resultados_piloto"):
        for coordenadas in (PASTA_PROJETO / raiz).glob("*/*/coordenadas.csv"):
            lotes.add((coordenadas.parent.parent.name, coordenadas.parent.name))
    return sorted(lotes)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--caso", default=getattr(config, "NOME_CASO", None))
    parser.add_argument("--execucao", default=getattr(config, "NOME_EXECUCAO", None))
    parser.add_argument("--todos", action="store_true",
                        help="processa todos os lotes em resultados/ e resultados_piloto/")
    parser.add_argument("--excluir-tinta", action="store_true",
                        help="exclui também recortes com muita tinta escura")
    parser.add_argument("--usar-lamina", action="store_true",
                        help="lê os recortes da lâmina mesmo que os PNG existam (para comparar)")
    argumentos = parser.parse_args()

    if argumentos.todos:
        lotes = listar_todos()
        if not lotes:
            sys.exit("Não foi encontrado nenhum lote.")
    else:
        if not argumentos.caso or not argumentos.execucao:
            sys.exit("Indica --caso e --execucao, ou define-os no config_local.json.")
        lotes = [(argumentos.caso, argumentos.execucao)]

    falhas = []
    for caso, execucao in lotes:
        try:
            processar_lote(caso, execucao, argumentos.excluir_tinta, argumentos.usar_lamina)
        except (FileNotFoundError, ValueError) as erro:
            print(f"  ERRO: {erro}")
            falhas.append(caso)

    if falhas:
        sys.exit(f"\n{len(falhas)} lote(s) por tratar: {', '.join(falhas)}")


if __name__ == "__main__":
    main()
