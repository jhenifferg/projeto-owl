"""Validar um lote local ou recebido, sem carregar o modelo Phikon."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from config import PASTA_PROJETO, NOME_CASO, NOME_EXECUCAO


def verificar(pasta):
    pasta = Path(pasta)
    with (pasta / 'coordenadas.csv').open(encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    registo = json.loads((pasta / 'execucao.json').read_text(encoding='utf-8'))
    def exigir(condicao, mensagem):
        if not condicao:
            raise ValueError(mensagem)
    n = len(linhas)
    exigir(n > 0, 'CSV vazio.')
    exigir(registo['recortes_processados'] == n, 'Contagem diferente entre CSV e JSON.')
    exigir(all(r['caso'] == registo['caso'] for r in linhas), 'Casos diferentes no CSV e JSON.')
    nomes = [r['ficheiro'] for r in linhas]
    exigir(len(set(nomes)) == n, 'Nomes de recortes repetidos.')
    coords = np.array([(int(r['x']), int(r['y'])) for r in linhas])
    with np.load(pasta / 'caracteristicas.npz', allow_pickle=False) as dados:
        exigir(dados['caracteristicas'].shape == (n, 768), 'Formato das características inválido.')
        exigir(list(dados['caracteristicas'].shape) == registo['formato_caracteristicas'], 'Formato difere do JSON.')
        exigir(np.isfinite(dados['caracteristicas']).all(), 'Características não finitas.')
        exigir(np.array_equal(dados['coordenadas'], coords), 'Ordem ou coordenadas diferentes no NPZ e CSV.')
        exigir(np.array_equal(dados['ficheiros'], nomes), 'Nomes ou ordem diferentes no NPZ e CSV.')
        for chave in ('caso', 'modelo', 'revisao_modelo'):
            exigir(dados[chave].item() == registo[chave], f'{chave} difere entre NPZ e JSON.')
    exigir(all(int(r['semente']) == registo['semente'] and int(r['tamanho_saida']) == registo['tamanho_saida_px'] for r in linhas), 'Parâmetros do CSV diferem do JSON.')
    exigir(all(float(r['fracao_tecido_estimada']) >= registo['fracao_minima_tecido'] for r in linhas), 'Recorte abaixo do mínimo de tecido.')
    if 'preparacao' in registo:
        exigir(registo['preparacao']['quantidade_recortes'] == n, 'Contagem diferente da preparação.')
    if (pasta / 'preparacao.json').exists():
        exigir(json.loads((pasta / 'preparacao.json').read_text()) == registo.get('preparacao'), 'Preparação difere do JSON final.')
    print(f'Lote válido: {registo["caso"]}, {n} recortes × 768 características.')
    return registo


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pasta', type=Path, default=PASTA_PROJETO / 'resultados' / NOME_CASO / NOME_EXECUCAO)
    args = parser.parse_args()
    verificar(args.pasta)
