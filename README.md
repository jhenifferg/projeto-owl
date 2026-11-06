# Projeto OWL — guia de utilização

Projeto académico de previsão de recorrência bioquímica do cancro da próstata e estudo de explicações por remoção de regiões de imagens histológicas.

## Estado atual

Esta versão lê uma imagem e a máscara de tecido, gera pré-visualizações, prepara **um recorte** e extrai 768 características com o Phikon pré-treinado.

**Ainda não processa um paciente completo, não treina um modelo de sobrevivência e não prevê recorrência.** O objetivo inicial é reproduzir o teste técnico nas máquinas do grupo.

## 1. Preparar o computador

Instalar Python e VS Code, caso ainda não estejam disponíveis. No VS Code, instalar a extensão Python da Microsoft.

O ambiente já testado foi macOS com Apple M4, 16 GB de memória, Python 3.14.7, OpenSlide 1.4.7, PyTorch 2.15.0 e Transformers 5.22.1. Outras configurações ainda precisam de ser verificadas. Não é obrigatório ter um Mac; no Windows/Linux podem ser necessários ajustes de instalação. Sem uma GPU compatível, o teste pode utilizar CPU.

## 2. Obter o código

No GitHub, abrir o repositório, selecionar **Code → Download ZIP**, extrair o ZIP e abrir a pasta no VS Code em **File → Open Folder**. Quem já utiliza Git pode clonar o repositório.

Abrir **Terminal → New Terminal**. Confirmar que o terminal está na pasta do projeto.

## 3. Criar o ambiente Python

No macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows, em PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, usar um terminal Command Prompt no VS Code e executar `.venv\Scripts\activate.bat`.

Deve aparecer `(.venv)` no início da linha. Sempre que abrir um novo terminal, volte a ativar o ambiente.

Instalar as dependências:

```bash
python -m pip install -r requirements.txt
```

No VS Code, abrir **Python: Select Interpreter** pela paleta de comandos e selecionar o Python de `.venv`.

## 4. Organizar os dados locais

Criar estas pastas na raiz do projeto:

| Pasta | Conteúdo |
|---|---|
| `imagens/` | Imagens originais `.tif`. |
| `mascaras/` | Máscaras correspondentes, com o sufixo `_tissue.tif`. |
| `dados/` | `training_labels.csv`. |
| `resultados/` | Ficheiros produzidos pelos scripts; a pasta é criada pelo código quando necessário. |

Para reproduzir o caso já testado:

- `imagens/case_radboud_0466.tif`
- `mascaras/case_radboud_0466_tissue.tif`
- `dados/training_labels.csv`

Descarregar os dados da fonte oficial do OWL, respeitando as suas condições de acesso e utilização. As imagens grandes não são incluídas no GitHub. Cada pessoa descarrega apenas os casos necessários e confirma o espaço disponível.

## 5. Escolher o caso

O ficheiro `config.py` deve conter:

```python
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
NOME_CASO = "case_radboud_xxxx"
```

O nome é escrito **sem `.tif` e sem `_tissue`**. Todos os scripts devem importar esta configuração e construir os nomes dos ficheiros a partir dela.

Antes de trocar de caso, verificar novamente dimensões, níveis, escala física e sobreposição da máscara.

BASTA RODAR NO TERMINAL python verificar_imagem.py

IRÁ OBTER ALGO COMO:

Imagem aberta com sucesso!
Dimensões originais: (90112, 91136)
Número de níveis: 5
Micrómetros por píxel em X: 0.2425347381273798
Micrómetros por píxel em Y: 0.2425347381273798
Ampliação da objetiva: Não disponível
Nível 0: (90112, 91136)
Nível 1: (22528, 22784)
Nível 2: (5632, 5696)
Nível 3: (1408, 1424) * foi o escolhido!
Nível 4: (352, 356)

## 6. Executar os scripts por ordem

Executar cada comando separadamente e conferir o resultado antes de avançar.

### A. Verificar a imagem

```bash
python verificar_imagem.py
```

Mostra as dimensões, os níveis de resolução e os micrómetros por píxel (MPP). Gera a pré-visualização da lâmina.

No caso 0466, a imagem original tem 90112 × 91136 píxeis; a pré-visualização utiliza o nível 3, com 1408 × 1424 píxeis. O MPP original é aproximadamente 0,2425 nos dois eixos.

AQUI ALTERAR nivel_visualizacao = PARA O VALOR QUE ESCOLHER! 


### B. Verificar a máscara

```bash
python verificar_mascara.py
```

Mostra as dimensões e os valores da máscara e guarda `mascara_previa.png`. No caso testado, o nível 2 tem 1408 × 1424 píxeis e os valores são 0 e 1.

FAZER A MESMA COISA ACIMA! 

 nivel_mascara = 2

alterar aqui para o nivel que mais for parecido com o da imagem

### C. Conferir o alinhamento

```bash
python sobrepor_mascara.py
```

Abrir `resultados/sobreposicao_mascara.png`. A região vermelha deve acompanhar o tecido. Se estiver deslocada ou cobrir o fundo, interromper e partilhar o problema com o grupo.


### D. Extrair um recorte

```bash
python extrair_recorte.py
```

Seleciona uma posição com tecido, lê uma região na resolução original e prepara um PNG de 224 × 224 píxeis com escala próxima de 0,5 µm/píxel.

Para o caso testado, a região original tem 462 × 462 píxeis. São guardados:

- `resultados/case_radboud_0466_phikon_224.png`
- `resultados/case_radboud_0466_phikon_224_posicao.txt`

A seleção atual procura uma posição interior na máscara reduzida, mas ainda não verifica a percentagem de tecido de toda a região extraída. Inspecionar o PNG. É um teste inicial, não a seleção definitiva dos recortes do projeto.

### E. Extrair as características com Phikon

```bash
python testar_phikon.py
```

Na primeira execução, descarrega o modelo (aproximadamente 350 MB, além de configurações). A extração é feita localmente; este código não envia o recorte para um serviço de inferência.

O resultado esperado é:

```text
Formato das características: (1, 768)
```

Significa **um recorte com 768 características**, não 768 pacientes nem uma previsão clínica. O ficheiro gerado é `resultados/case_radboud_0466_phikon_224_features.npy`.

O código atual utiliza GPU Apple (`mps`) quando disponível e CPU nos restantes casos. A utilização de GPU NVIDIA requer uma adaptação explícita para CUDA.

## 7. Trabalhar em equipa

1. Cada integrante reproduz primeiro o teste com o mesmo caso.
2. Comparar dimensões de saída e parâmetros de preparação; pequenas diferenças numéricas entre dispositivos podem ocorrer.
3. Depois de validarmos o processamento de vários recortes, distribuir casos sem duplicação numa tabela com caso, responsável e estado.
4. Utilizar o mesmo código, revisão do modelo e parâmetros. Antes da produção em escala, fixar a revisão dos pesos e registar o ambiente.
5. Partilhar características, coordenadas e configurações numa pasta privada autorizada, mantendo a correspondência por caso.

Ainda falta implementar um processamento completo por paciente e a padronização dos resultados de vários recortes. Não iniciar a extração em massa com esta versão.

## 8. O que pode entrar no GitHub

Incluir scripts, `config.py`, `requirements.txt`, `.gitignore` e este README. Manter dados e resultados fora do repositório.

Conteúdo recomendado do `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.DS_Store
imagens/
mascaras/
dados/
resultados/
.env
```

Antes de fazer commit:

```bash
git status --short
```

Se os dados já estiverem a ser acompanhados pelo Git, acrescentar o `.gitignore` não os remove automaticamente. Resolver isso antes do envio. Nunca publicar tokens ou credenciais.

## 9. Erros frequentes

| Situação | O que verificar |
|---|---|
| `Unsupported or missing image file` | Caminho, download completo e nome exato; a máscara termina em `_tissue.tif`. |
| `ModuleNotFoundError` | Ambiente `.venv` ativo e dependências instaladas nesse ambiente. |
| `FileNotFoundError` | Pastas, nome do caso e ordem de execução dos scripts. |
| PNG da máscara parece preto | Os valores podem ser 0 e 1; verificar a sobreposição colorida. |
| Aviso de falta de `HF_TOKEN` | O teste público já funcionou sem token; esperar o download ou verificar limites se falhar. |
| Aviso de `use_fast` | No preparador, usar `backend="pil"` na versão já testada. |
| Pesos `pooler` inesperados | No teste atual, a camada é excluída intencionalmente com `add_pooling_layer=False`; o vetor vem do CLS token. |


