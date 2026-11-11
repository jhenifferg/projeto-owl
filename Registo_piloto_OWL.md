# Registo do piloto OWL

Este documento acompanha a passagem dos recortes de cada lâmina para uma representação por paciente. Atualizem uma linha por caso à medida que verificarem os ficheiros. A tabela regista o progresso da equipa e os resultados completos ficam na pasta `resultados_piloto/`. O caminho pode ser local; a publicação do lote 0466 no GitHub ainda está pendente.

## Configuração comum

| Parâmetro | Valor |
|---|---|
| Execução | `piloto_v1_1000` |
| Recortes previstos por lâmina | 1 000 |
| Tamanho e escala alvo | 224 × 224 px a 0,5 µm/px |
| Fração mínima de tecido | 80% |
| Semente | 42 |
| Phikon | `owkin/phikon`, revisão `057cc0295895c2df3dd7681a89680da6015cbefe` |

## Acompanhamento por caso

| Caso | Responsável | Alinhamento visual | NPZ e CSV | JSON | Rótulo associado | Caminho do lote |
|---|---|---|---|---|---|---|
| `case_radboud_0466` | Jheniffer | Verificado no teste anterior | NPZ presente, formato 1 000 × 768 registado no JSON. CSV com 1 000 linhas de dados. Ordem e coordenadas conferidas automaticamente. | Presente | Pendente | `resultados_piloto/case_radboud_0466/piloto_v1_1000/` |
| `case_radboud_0596` | A definir | Pendente | Pendente | Pendente | Pendente | A preencher |
| Adicionar novo caso | | | | | | |
| `case_radboud_0247` | Catarina | Verificado | NPZ presente, formato 1 000 × 768 registado no JSON. CSV com 1 000 linhas de dados. Ordem e coordenadas conferidas automaticamente. | Presente | Pendente | `resultados_piloto/case_radboud_0247/piloto_v1_1000/` |
| `case_radboud_0594` | Catarina | Verificado | NPZ presente, formato 1 000 × 768 registado no JSON. CSV com 1 000 linhas de dados. Ordem e coordenadas conferidas automaticamente. | Presente | Pendente | `resultados_piloto/case_radboud_0594/piloto_v1_1000/` |
| `case_radboud_0626` | Catarina | Verificado | NPZ presente, formato 1 000 × 768 registado no JSON. CSV com 1 000 linhas de dados. Ordem e coordenadas conferidas automaticamente. | Presente | Pendente | `resultados_piloto/case_radboud_0626/piloto_v1_1000/` |
| Adicionar novo caso | | | | | | |

## Antes de marcar um caso como pronto

- Confirmar visualmente o alinhamento da lâmina e da máscara.
- Verificar a dimensão e os valores finitos do NPZ. Confirmar que cada vetor corresponde ao recorte na mesma posição do CSV, usando os identificadores ou nomes de recorte registados nos ficheiros.
- Conferir a configuração no `execucao.json` da própria execução. Registar desvios ou falhas na tabela.
- Guardar juntos `caracteristicas.npz`, `coordenadas.csv` e `execucao.json`, numa pasta com o identificador do caso e o nome da execução.
- Ligar o caso a exatamente uma linha de `training_labels.csv` por `case_id`. O tempo e o indicador de recorrência entram na tabela de análise, que fica com os dados do projeto.

## Próximas etapas

1. **Teste com 2 pacientes.** Calcular a média dos vetores dos recortes, por coluna, para obter um vetor de 768 características por paciente. A saída esperada é uma matriz 2 × 768, ligada aos dois identificadores e respetivos rótulos.
2. **Piloto técnico com 10 pacientes no total.** Verificar se o Cox regularizado e a ablação correm de ponta a ponta. Confirmar que há recorrências observadas no conjunto usado para ajustar o Cox.
3. **Avaliação.** Usar o maior número viável de pacientes e medir o C-index em pacientes separados do treino. Para a ablação, usar os vetores individuais e as coordenadas para recalcular a média sem os grupos de recortes removidos. Comparar com remoções aleatórias do mesmo tamanho.

## Onde guardar

- **Partilha autorizada pela equipa** — os três ficheiros de cada lote validado em `resultados_piloto/<caso>/<execucao>/`, conforme as condições de utilização do OWL.
- **Localmente** — imagens, máscaras, rótulos e saídas originais dos scripts.
