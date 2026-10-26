# Backup completo — Painel Financeiro e Orçamentário IOC

- **Data do snapshot:** 26/10/2026 (UTC)
- **Repositório de origem:** https://github.com/DanielBrasilIOC/brasil
- **Branch de origem:** `main`
- **Commit de origem:** `a20758c05e1516f751910fa1bf0c719b77af1d53`
- **Branch deste backup:** `backup-completo-dashboard-2026-10-26`
- **Dashboard público preservado:** https://danielbrasilioc.github.io/brasil/

## O que está incluído

Este backup é uma cópia do repositório inteiro no commit de origem, incluindo o dashboard, dados publicados, scripts, fluxos de automação, testes, validações, logs e arquivos auxiliares. Os principais arquivos incluem:

- `index.html` e `dashboard-v2.html` — interface do painel
- `data.json`, `repasses.json` e `source_state.json` — dados e estado da sincronização
- `.github/workflows/pages.yml` — fluxo de sincronização/publicação
- `.github/workflows/restore-dashboard-backup.yml` — fluxo de recuperação existente
- `.github/scripts/` — lógica de sincronização, auditoria, descoberta de fontes, testes e validação de backup
- `executive-enhancements.js`, `fonte-correlacionada.js`, `rap-columns.js`, `rap-thermometer.js` — scripts auxiliares do painel
- `logs/atualizacoes_dashboard.csv` — histórico persistido disponível no momento do snapshot
- `README.md` e demais arquivos versionados

## Como baixar uma cópia local

Abra o arquivo ZIP deste branch no GitHub ou use o link de download do ZIP informado na conversa. Guarde o ZIP fora do repositório, para que uma falha no repositório não seja a única cópia disponível.

## Como recuperar

1. Confira o conteúdo do backup antes de restaurar.
2. Para recuperar um arquivo isolado, copie-o deste branch para `main) por meio de um commit revisado.
3. Para recuperar o projeto inteiro, compare o branch de backup com `main` e restaure os arquivos necessários, preservando os dados mais recentes que tenham sido validados depois da data do snapshot.
4. Não publique o branch de backup como produção. A publicação automática é configurada para `main`.

## Limites do snapshot

Este backup preserva os arquivos versionados do repositório e seu histórico Git anterior ao snapshot. Não inclui credenciais secretas armazenadas nas configurações do GitHub nem cópias externas das planilhas do Google Drive.
