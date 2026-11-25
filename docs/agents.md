# Os 16 especialistas

A equipe é definida em um único arquivo, [`team.json`](../masterdev/skills/masterdev/assets/team.json). Dele saem os agentes do Claude Code (`masterdev/agents/*.md`) e do Codex (`masterdev/.codex/agents/*.toml`), e o painel lê nomes, siglas, cores e squads do mesmo lugar.

O **coordenador** (a skill `masterdev`) não é um agente separado: é quem conversa com você, escolhe os especialistas, distribui as tarefas, integra os resultados e entrega.

| Squad | Agente (Claude Code) | Codex | Sigla | Papel |
|---|---|---|---|---|
| Produto & Design | `product-manager` | `product_manager` | PM | Problema, escopo, histórias e critérios de aceite |
| Produto & Design | `ux-ui-designer` | `ux_ui_designer` | UX | Fluxos, telas, design system e acessibilidade |
| Arquitetura | `software-architect` | `software_architect` | SA | Arquitetura, módulos, contratos e decisões (ADR) |
| Engenharia | `frontend-engineer` | `frontend_engineer` | FE | Web: interface, estado, rotas e integração |
| Engenharia | `mobile-engineer` | `mobile_engineer` | MB | iOS, Android e multiplataforma |
| Engenharia | `backend-engineer` | `backend_engineer` | BE | APIs, serviços, regras de negócio e integrações |
| Engenharia | `database-engineer` | `database_engineer` | DB | Modelagem, migrations, índices e consultas |
| Dados & IA | `data-engineer` | `data_engineer` | DE | Estrutura de dados do app, eventos, pipelines e analytics |
| Dados & IA | `data-scientist` | `data_scientist` | DS | Métricas, experimentos, ML e recursos de IA/LLM |
| Plataforma & Qualidade | `devops-sre-engineer` | `devops_sre_engineer` | OP | CI/CD, infraestrutura, containers e observabilidade |
| Plataforma & Qualidade | `security-engineer` | `security_engineer` | SE | AppSec, autenticação, segredos e privacidade (LGPD) |
| Plataforma & Qualidade | `qa-test-engineer` | `qa_test_engineer` | QA | Estratégia de testes, automação e regressão |
| Plataforma & Qualidade | `performance-engineer` | `performance_engineer` | PF | Profiling, Web Vitals, carga e custo |
| Plataforma & Qualidade | `technical-writer` | `technical_writer` | TW | README, documentação, guias e changelog |
| Revisão independente | `code-correctness-reviewer` | `code_correctness_reviewer` | CR | Revisão independente de corretude e regressões (somente leitura) |
| Revisão independente | `code-maintainability-reviewer` | `code_maintainability_reviewer` | MR | Simplicidade, legibilidade e manutenção (somente leitura) |

## O que cada um faz

### Produto & Design

**Product Manager** (`product-manager`) — Gerente de produto sênior. Transforma pedidos em problema, público, escopo mínimo, histórias de usuário e critérios de aceite verificáveis.

**UX/UI Designer** (`ux-ui-designer`) — Designer sênior de UX/UI. Desenha jornadas, fluxos, estados de tela, hierarquia visual, design system e acessibilidade (WCAG 2.2 AA) para web e mobile.

### Arquitetura

**Software Architect** (`software-architect`) — Arquiteto de software sênior. Define arquitetura, limites de módulos, modelo de domínio, contratos de API, stack e decisões registradas em ADRs, priorizando a solução mais simples que atende.

### Engenharia

**Frontend Engineer** (`frontend-engineer`) — Engenheiro frontend sênior. Implementa interfaces web acessíveis e responsivas (React, Next.js, Vue, Svelte, Angular ou HTML/CSS/JS), gerenciamento de estado, rotas e integração com APIs.

**Mobile Engineer** (`mobile-engineer`) — Engenheiro mobile sênior. Implementa aplicativos iOS e Android nativos (Swift/SwiftUI, Kotlin/Jetpack Compose) ou multiplataforma (React Native/Expo, Flutter), com navegação, estado, offline e publicação nas lojas.

**Backend Engineer** (`backend-engineer`) — Engenheiro backend sênior. Implementa APIs REST/GraphQL/gRPC, regras de negócio, autenticação, filas, jobs e integrações externas com validação, idempotência e tratamento de erros corretos.

**Database Engineer** (`database-engineer`) — Engenheiro de banco de dados sênior. Modela esquemas relacionais e NoSQL, escreve migrations seguras e reversíveis, índices, consultas eficientes, seeds e políticas de retenção.

### Dados & IA

**Data Engineer** (`data-engineer`) — Engenheiro de dados sênior para produtos digitais. Entende e documenta a estrutura de dados do software, define eventos de analytics, pipelines/ETL, exportações, qualidade e governança dos dados do aplicativo.

**Data Scientist** (`data-scientist`) — Cientista de dados sênior. Define métricas de produto, experimentos A/B, modelos de machine learning e recursos de IA/LLM (busca semântica, RAG, classificação, recomendação), com avaliação honesta e riscos explícitos.

### Plataforma & Qualidade

**DevOps / SRE** (`devops-sre-engineer`) — Engenheiro DevOps/SRE sênior. Configura CI/CD, containers, infraestrutura como código, ambientes, variáveis e segredos, observabilidade (logs, métricas, traces, alertas) e estratégias de deploy e rollback.

**Security Engineer** (`security-engineer`) — Engenheiro de segurança de aplicações sênior. Faz modelagem de ameaças e revisão de segurança (OWASP Top 10, OWASP MASVS para mobile), autenticação, autorização, segredos, dependências e privacidade/LGPD.

**QA / Test Engineer** (`qa-test-engineer`) — Engenheiro de qualidade sênior. Define a estratégia de testes, escreve testes automatizados (unidade, integração, contrato, ponta a ponta), verifica critérios de aceite e cria testes de regressão para bugs.

**Performance Engineer** (`performance-engineer`) — Engenheiro de performance sênior. Mede e melhora tempo de resposta, Core Web Vitals, tamanho de bundle, inicialização de apps, consumo de memória, consultas e capacidade sob carga, sempre contra uma linha de base.

**Technical Writer** (`technical-writer`) — Redator técnico sênior. Escreve README, guias de instalação e uso, documentação de API, decisões, changelog e notas de versão claras, corretas e verificadas contra o código.

### Revisão independente

**Correctness Reviewer** (`code-correctness-reviewer`) — Revisor independente de corretude. Audita a mudança procurando bugs, regressões, quebras de contrato, condições de corrida, casos de borda, falhas de segurança e o que pode quebrar fora do diff.

**Maintainability Reviewer** (`code-maintainability-reviewer`) — Revisor independente de manutenibilidade. Avalia simplicidade, legibilidade, coesão, acoplamento, duplicação, abstrações desnecessárias, testes frágeis e aderência às convenções do projeto.

## Regras comuns a todos

trabalhe só no escopo e nos arquivos que o coordenador atribuiu; não invente requisitos, APIs, dados ou resultados; separe fatos, hipóteses e o que foi realmente executado; nunca exponha segredos, tokens ou dados pessoais reais; operações destrutivas, deploy, publicação, migrations em ambientes compartilhados e alterações de permissões exigem autorização explícita do operador. Ao terminar, responda com: resultado, arquivos tocados, validações executadas (com o resultado real), pendências e riscos.

## Como a equipe trabalha junta

- **Só quem é necessário.** O coordenador não convoca os 16 por padrão; a tabela de *Escolhendo especialistas por tipo de produto* em [`PLAYBOOKS.md`](../masterdev/skills/masterdev/references/PLAYBOOKS.md) sugere o núcleo de cada tipo de projeto.
- **Um escritor por arquivo.** Antes de paralelizar, o coordenador separa os arquivos de cada agente.
- **Dependências explícitas.** O frontend espera o contrato da API; o backend espera o esquema do banco. No painel isso aparece como `depende de T4`.
- **Revisão independente.** Os dois revisores só leem e recebem o código e o pedido original, nunca a conclusão de quem escreveu.
- **Autorização explícita** para deploy, publicação em lojas, migrations em ambientes compartilhados, operações destrutivas e mudanças de permissão ou infraestrutura.

## Mudando ou adicionando um agente

1. Edite `masterdev/skills/masterdev/assets/team.json` (chave, nome, sigla única, cor, squad, papel, descrição, instruções; `"readonly": true` para revisores).
2. Rode `python scripts/build_agents.py`.
3. Cite o agente na tabela da equipe em `SKILL.md` (o validador confere).
4. Rode os testes (`CONTRIBUTING.md`).
