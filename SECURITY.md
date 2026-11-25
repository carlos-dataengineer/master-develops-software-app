# Política de segurança

## Versões suportadas

| Versão | Suporte |
|---|---|
| 1.0.x | ✅ |

## Como relatar uma vulnerabilidade

**Não abra uma issue pública.** Use o recurso *Report a vulnerability* do GitHub, na aba **Security** do repositório: https://github.com/carlos-dataengineer/master-develops-software-app/security/advisories/new. Descreva o problema, como reproduzir e o impacto. A resposta inicial acontece em até 7 dias.

## O que o projeto faz e não faz

- **Instalador:** copia arquivos para `~/.claude`, `~/.agents`, `~/.codex` e `~/MasterDevelops`. No Claude Code, adiciona dois hooks (`PreToolUse`/`PostToolUse` da ferramenta de subagentes) ao `settings.json`, depois de salvar uma cópia em `settings.json.bak-mdv`. Hooks de outras ferramentas são preservados. Use `--no-hooks` para não alterar o `settings.json`.
- **Painel:** servidor HTTP **somente leitura** que escuta apenas em `127.0.0.1`, com Content-Security-Policy restritiva. Não aceita escrita pela rede e só libera leitura entre origens para o próprio arquivo local do painel (origem `null`).
- **Eventos do painel:** ficam em `~/MasterDevelops/board/events.jsonl`, só com textos curtos. Textos que parecem credenciais (chaves de API, tokens, senhas, connection strings) são substituídos por um aviso antes de serem gravados. Caminhos absolutos são reduzidos às três últimas partes.
- **Memória contextual:** SQLite local, fora do repositório, sem criptografia automática. Não guarde segredos nem dados pessoais.
- **Sem telemetria:** nenhum script faz chamadas de rede, exceto o instalador ao baixar este repositório do GitHub.
- **Ações com impacto:** a equipe não faz deploy, não publica em lojas, não roda migrations em ambientes compartilhados, não apaga dados e não muda permissões ou infraestrutura sem autorização explícita do operador. Os revisores independentes atuam em modo somente leitura.
