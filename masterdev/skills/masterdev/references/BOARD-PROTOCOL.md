# Protocolo do painel de produção

O coordenador registra o andamento com `scripts/team_board.py`. Cada comando grava um evento curto em `~/MasterDevelops/board/events.jsonl` (ou em `$MASTERDEV_HOME/board`). O painel lê esses eventos e se atualiza ao vivo em `http://127.0.0.1:47841`.

Regras: textos curtos e sanitizados; nada de segredos, dados pessoais ou dados de clientes (o script troca o que parece credencial por um aviso, mas isso é só uma proteção parcial). Se um comando falhar, siga o trabalho.

## Comandos

| Comando | Para quê | Exemplo |
|---|---|---|
| `ensure [--open]` | Sobe o painel em segundo plano (se preciso) e mostra o endereço | `team_board.py ensure` |
| `start` | Abre a missão | `start --mode construir --title "App de agendamento" --project . --host claude --platforms web,ios,android --stack "Next.js · Expo · PostgreSQL"` |
| `stage <etapa>` | Marca a etapa atual (`--done` fecha sem abrir a próxima; `--note`) | `stage arquitetura` |
| `task <id>` | Cria/atualiza tarefa de um agente | `task T3 --agent backend-engineer --status queued --title "API de agenda" --after T1,T2` |
| `artifact <nome>` | Registra um entregável | `artifact src/api/agenda.ts --kind codigo --agent backend-engineer --task T3` |
| `gate <nome>` | Resultado de uma verificação executada | `gate testes --status pass --value 134/134` |
| `finding <id>` | Achado de revisão (novo ou atualização) | `finding F1 --severity alta --agent code-correctness-reviewer --title "..." --where src/x.ts:41` |
| `decision <id>` | Decisão de arquitetura (ADR) | `decision ADR-1 --title "Monólito modular"` |
| `note "<texto>"` | Aviso ou pergunta ao operador no feed | `note "Aguardando credenciais do ambiente de testes"` |
| `finish` | Encerra (`--status done|failed|cancelled`, `--summary`) | `finish --summary "Web + app entregues"` |
| `status [--json]` | Missão ativa em texto | |
| `report [arquivo]` | Relatório da missão em Markdown | `report relatorio.md` |
| `demo [--live]` | Missão fictícia para conhecer o painel | |
| `export [arquivo]` | Painel em um HTML único (foto + demonstração) | |
| `stop` / `prune --keep 30` | Para o servidor / limpa missões antigas | |

## Valores aceitos

- **Modos:** `construir`, `evoluir`, `revisar`, `depurar` (no Claude Code, missões abertas só pelos hooks aparecem como "Sessão livre").
- **Etapas:** `descoberta`, `arquitetura`, `plano`, `construcao`, `qualidade`, `revisao`, `entrega`. Pular etapas é normal: as que não aconteceram aparecem como "não se aplicou".
- **Status de tarefa:** `queued`, `running`, `review`, `done`, `blocked`, `failed`.
- **Agentes:** os 16 de `assets/team.json` (com hífen ou sublinhado) ou `coordinator`.
- **Entregáveis (`--kind`):** `codigo`, `teste`, `doc`, `design`, `infra`, `dados`, `config`.
- **Gates:** `build`, `lint`, `tipos`, `testes`, `e2e`, `cobertura`, `seguranca`, `acessibilidade`, `performance` (outros nomes curtos também são aceitos). Status: `pass`, `fail`, `warn`, `skip`, `running`. Registre só o que foi realmente executado.
- **Achados:** severidade `critica`, `alta`, `media`, `baixa`; status `aberto`, `corrigido`, `aceito`.

## Índice de saúde

Começa em 100 e desconta: gate reprovado −15, gate com avisos −5, achado aberto crítico −25, alto −12, médio −4, baixo −1, tarefa bloqueada −6, tarefa com falha −10, missão com falha −20. Faixas: 80+ Saudável, 55–79 Atenção, abaixo de 55 Em risco.

## Hooks do Claude Code

Com o instalador, os eventos `PreToolUse` e `PostToolUse` da ferramenta de subagentes chamam `masterdev_board.py hook --app masterdev`. O hook liga o subagente à tarefa que o coordenador anunciou para o mesmo agente (ou cria uma), avança a etapa conforme o papel (engenharia → construção, QA/performance → qualidade, revisores → revisão; nunca volta) e nunca interrompe o agente se algo der errado.
