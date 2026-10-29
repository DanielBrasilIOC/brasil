# Agente de Consulta — Ambiente de Teste

Este diretório é um protótipo separado da produção para testar consultas em linguagem natural sobre os dados que alimentam o Painel Financeiro e Orçamentário IOC.

## Regras do protótipo
- Não altera o dashboard de produção.
- Consulta apenas o `data.json` disponível no repositório.
- Prioriza respostas determinísticas.
- Quando não consegue identificar a base ou o campo necessário, informa que não pode confirmar em vez de inventar.
- Exibe a fonte/conjunto de dados quando disponível.

## Primeiras consultas
- última OB paga
- maior pagamento
- saldo financeiro
- restos a pagar
- empenhos 2026

## Próxima etapa
Conectar o agente diretamente à base validada de sincronização e ampliar a interpretação de perguntas, mantendo trilha de auditoria e data da base consultada.
