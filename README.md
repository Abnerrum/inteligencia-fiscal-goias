# Inteligência Fiscal e Socioeconômica com Dados Abertos de Goiás

Projeto de Business Intelligence do SENAI FATESG. O painel compara o ICMS bruto repassado e a frota registrada dos municípios goianos em uma mesma competência. Os dados vêm da Economia de Goiás, do DETRAN-GO e do IBGE.

## Abrir no Windows e no VS Code

Abra a pasta `inteligencia_fiscal_goias_vscode` no VS Code. Os comandos abaixo partem dela e usam o ambiente virtual na pasta imediatamente acima. Selecione esse mesmo interpretador pelo comando **Python: Select Interpreter** do VS Code para usar o depurador.

```powershell
# Só é preciso criar o ambiente se ele ainda não existir.
if (-not (Test-Path ..\.venv\Scripts\python.exe)) { python -m venv ..\.venv }
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m streamlit run app.py
```

Use Python 3.12. Abra o endereço local exibido pelo Streamlit, normalmente `http://localhost:8501`. Se ainda não houver banco em uma cópia nova do projeto, siga a importação abaixo e recarregue o painel.

## Importar os dados oficiais

Para importar julho de 2025, competência padrão do ETL:

```powershell
..\.venv\Scripts\python.exe -m src.pipeline --periodo 2025-07
```

Para puxar todos os dados, abra **Importação de dados** na barra lateral e clique em **Puxar todos os dados**. Também é possível rodar em lote pelo PowerShell:

```powershell
..\.venv\Scripts\python.exe -m src.pipeline --todos
```

O lote tenta todas as competências de 2025 e os meses adicionais encontrados nos arquivos locais de repasses. Ele informa o resultado por competência e continua quando um mês falha. Para usar só os arquivos locais, marque **Usar apenas arquivos locais** no painel ou acrescente `--offline` ao comando.

Para 2025, o ETL usa a aba **Agregado** da [conciliação anual publicada pela Secretaria da Economia](https://goias.gov.br/economia/repasse-aos-municipios/) e as 12 bases mensais de frota do DETRAN-GO. O ZIP anterior traz apenas IPVA de agosto a dezembro. A planilha anual cobre ICMS em todos os meses e também revisa os valores de janeiro a abril em relação ao ZIP. Cada importação substitui apenas os registros da competência informada.

Para reconstruir o ano inteiro offline, guarde a planilha anual como `data/raw/conciliacao_2025.xlsx`, os 12 CSVs de frota como `frota_AAAAMM.csv` e o catálogo do IBGE como `municipios_go.json`. Então rode `..\.venv\Scripts\python.exe -m src.pipeline --todos --offline`. O resumo esperado é **12 competências importadas e 0 não importadas**.

### Importação manual de CSV ou XLSX

1. Baixe os arquivos da mesma competência no [Portal de Repasses](https://dadosabertos.go.gov.br/dataset/repasses) e no [Portal de Frota do DETRAN-GO](https://dadosabertos.go.gov.br/dataset/frota-de-veiculos).
2. Use a primeira aba para XLSX. Informe `NOME_MUNICIPIO` e `VALOR_BRUTO_ICMS` na base de repasses e `MUNICIPIO` e `QTD` na de frota. Quando houver uma coluna de competência, use `AAAAMM` ou `AAAA-MM`. Quando ela não existir, confira a competência na página de publicação do arquivo antes de executar.
3. Informe os caminhos como no exemplo. Para modo totalmente offline, guarde também a [lista de municípios do IBGE](https://servicodados.ibge.gov.br/api/v1/localidades/estados/52/municipios) como `data/raw/municipios_go.json`.

```powershell
..\.venv\Scripts\python.exe -m src.pipeline --periodo 2025-07 --icms '.\data\raw\icms_202507.csv' --frota '.\data\raw\frota_202507.xlsx'
```

Você pode omitir o caminho da frota se o arquivo estiver em `data/raw/` com nome `frota_AAAAMM.csv` ou `.xlsx`. Use `--icms` para substituir explicitamente a planilha anual em um mês. Em modo offline, sem a planilha anual, o ETL também procura `icms_AAAAMM.csv`, `.xlsx` ou o CSV do ZIP. Use `--offline` para impedir downloads.

## Usar o painel

1. Em **Filtros**, selecione a competência. Digite parte do nome em **Municípios** para encontrar uma cidade.
2. Em **Visão geral**, alterne entre ICMS e frota para examinar o ranking e a série mensal. A série acompanha o município selecionado ao longo das competências importadas.
3. Em **Regressão e simulador**, veja a dispersão, a reta OLS e as métricas. O ajuste usa todos os municípios cruzados no mês para manter a amostra de referência. Informe uma quantidade de veículos e clique em **Calcular estimativa**. Uma entrada fora da faixa observada gera aviso.
4. Em **Registros**, confira os pares município-mês e exporte o recorte em CSV.

## Arquivos e testes

| Arquivo ou pasta | Responsabilidade |
| --- | --- |
| `app.py` e `.streamlit/config.toml` | Painel, filtros, gráficos, exportação, simulador e tema |
| `src/pipeline.py` | Leitura, validação, agregação e cruzamento de fontes |
| `src/database.py` | Esquema SQLite, gravação transacional e consultas |
| `src/model.py` | Pearson, OLS, MAE, RMSE e simulação |
| `database/inteligencia_fiscal.db` | Banco local gerado pela importação |
| `tests/` | Testes da integração, do modelo e do painel |
| `docs/relatorio_tecnico.md` | Metodologia, resultados, limitações e roteiro para PDF |

```powershell
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Publicação no Render

O `render.yaml` descreve o serviço gratuito em Python. A variável `FISCAL_PUBLICADO=1` ativa o modo público, que consulta `data/demonstracao.sqlite3`, uma cópia da base oficial consolidada de janeiro a dezembro de 2025. Nesse modo ficam disponíveis os filtros, os gráficos, o simulador e a exportação CSV. A carga de dados continua disponível na instalação local.

O banco de trabalho e os downloads brutos ficam fora do Git. O repositório inclui a cópia consolidada para o painel público abrir com dados mesmo quando as fontes de download estiverem indisponíveis.

Abra o [painel publicado](https://inteligencia-fiscal-goias.onrender.com) ou baixe o [relatório técnico em Word](docs/relatorio_tecnico.docx). O [relatório em Markdown](docs/relatorio_tecnico.md) acompanha a versão do código.
