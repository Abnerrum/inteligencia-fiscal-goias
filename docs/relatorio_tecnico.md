# Inteligência Fiscal e Socioeconômica com Dados Abertos de Goiás

**Relatório técnico executivo · Business Intelligence · SENAI FATESG**

**Autoria:** ____________________________________  
**Turma:** ______________________________________  
**Data da apresentação:** 23/11/2026

## Resumo executivo

O projeto cruza os repasses brutos de ICMS e a frota registrada de Goiás por município e mês. A entrega integra **1.722 registros**, cobrindo os **246 municípios goianos** em sete competências de janeiro a julho de 2025. Em julho, a correlação de Pearson foi **0,930**, uma associação linear positiva forte. A regressão simples apresentou **R² de 0,864**, com erro absoluto médio de aproximadamente **R$ 1,13 milhão por município** no ajuste. O painel permite reproduzir a análise, consultar os registros e simular estimativas.

## 1. Problema e objetivos

A Economia de Goiás divulga os repasses estaduais, enquanto o DETRAN-GO publica a frota por município. As fontes usam arquivos e estruturas diferentes. O problema de BI é combinar essas informações de forma rastreável e responder à pergunta: **municípios com maior frota registrada também recebem maiores valores brutos de ICMS no mesmo mês?**

Os objetivos são comparar os municípios, acompanhar o comportamento mensal dos indicadores, medir a associação e disponibilizar uma estimativa que possa ser reproduzida a partir dos coeficientes divulgados no painel.

## 2. Fontes e tecnologias

| Fonte | Dados usados | Abrangência na entrega |
| --- | --- | --- |
| [Economia de Goiás — Repasses](https://dadosabertos.go.gov.br/dataset/repasses) | Eventos de repasse mensal e o campo de ICMS bruto | Janeiro a julho de 2025 |
| [DETRAN-GO — Frota de Veículos](https://dadosabertos.go.gov.br/dataset/frota-de-veiculos) | Soma de `QTD` para as situações ativa e inativa publicadas | Janeiro a julho de 2025 |
| [IBGE — Municípios de Goiás](https://servicodados.ibge.gov.br/api/v1/localidades/estados/52/municipios) | Código oficial e nome de exibição de cada município | 246 municípios |

O Python 3.12 executa o ETL e o painel. Pandas e NumPy tratam e verificam os registros. Requests baixa os recursos, openpyxl lê planilhas XLSX, SQLite armazena as tabelas, Statsmodels ajusta a regressão OLS, Streamlit monta a interface e Plotly desenha os gráficos. Pytest verifica o ETL e o modelo, com o AppTest do Streamlit cobrindo a interface.

## 3. Processo de ETL

1. **Extração.** O pipeline procura arquivos locais CSV/XLSX, a pasta de repasses extraídos ou o ZIP anual. Se necessário, baixa os recursos oficiais disponíveis para a competência. No XLSX, usa a primeira aba. A frota oficial não traz a competência em cada linha. Nesses arquivos, a referência é o mês indicado no recurso publicado e no nome do arquivo.
2. **Padronização.** A leitura aceita CSV em UTF-8 ou Windows-1252 e detecta o separador. O ETL padroniza os cabeçalhos e as chaves municipais, removendo diferenças de acento, caixa e pontuação. O catálogo do IBGE fornece os códigos e a grafia final. “BOM JESUS” é associado ao código **5203500**, Bom Jesus de Goiás.
3. **Validação.** Quando o arquivo traz uma coluna de competência, ela precisa coincidir com o mês declarado. O ICMS exige valor numérico finito e permite ajustes negativos da fonte. A frota exige contagem inteira não negativa. Uma linha inválida de um município identificado interrompe a importação. Rótulos sem correspondência são exibidos no terminal. A linha “MUNICIPIO NAO INFORMADO”, encontrada nos repasses, fica fora dos totais municipais.
4. **Agregação.** O ETL soma eventos de ICMS bruto após eliminar repetições exatas de linhas de repasse. A frota soma apenas `QTD`; as colunas de ano de fabricação detalham a mesma contagem. A base de frota tem linhas iguais nos campos publicados e carece de um identificador de origem que comprove duplicação. Essas linhas são preservadas na soma. Em julho, removê-las por igualdade visual reduziria a frota oficial publicada de 4.938.420 para 4.492.142 veículos.
5. **Integração e carga.** O cruzamento exige município e mês presentes nas duas fontes. A carga grava cada competência em uma transação. Reimportar julho substitui julho por inteiro, evitando entradas duplicadas. Caso uma gravação falhe, a transação mantém os dados anteriores.

## 4. Estrutura do banco SQLite

O banco fica em `database/inteligencia_fiscal.db`. A chave composta de repasses e frota garante um indicador de cada tipo por município e mês.

| Objeto | Chave | Conteúdo |
| --- | --- | --- |
| `municipios` | `codigo_ibge` | Código IBGE e nome oficial |
| `repasses_icms` | `periodo, codigo_ibge` | Soma mensal do ICMS bruto em reais |
| `frota_veiculos` | `periodo, codigo_ibge` | Contagem mensal de veículos |
| `importacoes` | `periodo` | Caminho ou URL de origem por fonte |
| `indicadores` | Combinação de mês e município | Visão SQL que une as duas tabelas de fatos com o catálogo |

As tabelas de indicadores têm chaves estrangeiras para o catálogo municipal. O painel lê a visão SQL e calcula as estatísticas na abertura da análise. O código também consegue consultar o antigo `data/goias.db` quando o novo banco ainda não existe.

## 5. Método estatístico

Cada observação representa um município na competência escolhida. **X** é a frota registrada e **Y** é o valor bruto de ICMS repassado, em reais. Pearson varia de −1 a +1 e mede a direção e a intensidade da relação linear. O painel usa limiares descritivos de magnitude `|r|`: abaixo de 0,30, associação fraca, de 0,30 a menos de 0,70, moderada, e a partir de 0,70, forte.

A equação é **Ŷ = b + aX**. O Statsmodels estima a inclinação **a** e o intercepto **b** por mínimos quadrados ordinários, que minimizam a soma dos quadrados dos resíduos `Y − Ŷ`. A inclinação informa a diferença estimada por veículo adicional ao comparar municípios pela reta. O intercepto é o valor da equação quando X = 0. Essa entrada fica fora das faixas oficiais importadas.

- **R²** mede a proporção da variação observada de ICMS representada pela reta no recorte.
- **MAE** é a média do erro absoluto em reais. Ajuda a entender a ordem de grandeza dos desvios.
- **RMSE** é a raiz da média dos erros quadráticos em reais. Desvios grandes têm mais peso.
- **Simulador.** Substitui X na equação ajustada à competência. A interface sinaliza quando X está abaixo da frota mínima ou acima da máxima observada.

O ajuste é descritivo, e as métricas foram calculadas na amostra de ajuste. Avaliar previsões futuras exigiria competências reservadas para teste temporal e controle da repetição dos mesmos municípios entre treino e teste.

## 6. Resultados observados

| Competência 2025 | Municípios | ICMS bruto (R$) | Frota publicada | Pearson | R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| Janeiro | 246 | 504.485.562,74 | 4.837.965 | 0,929 | 0,863 |
| Fevereiro | 246 | 555.541.192,37 | 4.853.609 | 0,929 | 0,863 |
| Março | 246 | 608.560.890,43 | 4.869.720 | 0,929 | 0,863 |
| Abril | 246 | 634.714.312,26 | 4.886.843 | 0,929 | 0,864 |
| Maio | 246 | 603.548.697,59 | 4.904.638 | 0,929 | 0,864 |
| Junho | 246 | 617.015.186,72 | 4.920.141 | 0,930 | 0,864 |
| Julho | 246 | 663.417.883,55 | 4.938.420 | 0,930 | 0,864 |

Em julho, a equação arredondada foi **Ŷ = 1.335.612,92 + 67,8065 × X**. O modelo cobriu frotas entre **468 e 1.392.726 veículos**. O **MAE foi de R$ 1.126.489,10** e o **RMSE foi de R$ 2.558.891,33**. A diferença entre essas métricas indica que desvios maiores pesam no ajuste. Ainda que a frota e os repasses tenham forte associação linear, uma estimativa pontual deve ser interpretada levando em conta essa magnitude de erro.

## 7. Limitações e conclusão

- De agosto a dezembro de 2025, o ZIP analisado contém campos de IPVA e omite a coluna de ICMS bruto. Esses meses ficaram fora da série integrada. É possível importá-los quando houver um arquivo oficial com o indicador e a competência correspondentes.
- A análise usa frota registrada ativa e inativa e ICMS bruto em reais nominais. O significado dos indicadores precisa ser mantido ao adicionar fontes.
- População, atividade econômica e critérios de repartição podem influenciar a associação. Municípios muito grandes podem exercer forte influência na reta. A observação de Pearson elevado não estabelece causalidade.
- A análise compara municípios dentro de cada mês. O simulador descreve essa relação na amostra e tem finalidade acadêmica.

A base integrada responde à pergunta de negócio no período estudado: municípios com frotas maiores tendem a receber repasses brutos maiores. A série, o gráfico de dispersão e os erros do ajuste ajudam a mostrar onde essa tendência funciona como descrição e onde as estimativas se afastam dos valores observados.

## 8. Como reproduzir e validar

Execute os comandos dentro da pasta do projeto no PowerShell. Use o [README](../README.md) para reconstruir a série completa ou importar arquivos manuais.

```powershell
if (-not (Test-Path ..\.venv\Scripts\python.exe)) { python -m venv ..\.venv }
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m src.pipeline --todos
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
..\.venv\Scripts\python.exe -m streamlit run app.py
```

O painel oferece o mesmo lote em **Importação de dados → Puxar todos os dados**. O resumo mostra os meses importados, os municípios cruzados e o motivo de cada falha.

A validação no Windows incluiu testes automatizados, importação de sete competências oficiais, checagem de integridade do SQLite e inicialização do Streamlit. Os testes verificam CSV e XLSX, rejeição de mês incompatível, reimportação sem duplicação, leitura do banco legado, regressão em uma relação conhecida, dados degenerados, filtros, extrapolação no simulador e acionamento da importação em lote. Os dados artificiais dos testes ficam em bancos temporários.

## 9. Figuras e exportação para PDF

- **Figura 1 · Visão geral de julho de 2025.** Inserir captura que mostre a competência, os três cartões e o ranking.
- **Figura 2 · Dispersão e ajuste linear.** Inserir captura com a reta, Pearson, R², MAE e RMSE.
- **Figura 3 · Simulador e filtro municipal.** Inserir captura do simulador e uma captura da tabela após filtrar Goiânia.

Preencha a autoria na capa e insira as capturas reais nos locais indicados. Abra a visualização Markdown no VS Code para revisar tabelas e títulos. Para gerar o PDF, cole a versão renderizada em um editor de texto, revise a paginação em A4 e use a opção **Exportar para PDF** do editor.
