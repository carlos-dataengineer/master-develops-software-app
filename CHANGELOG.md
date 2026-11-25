# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## 1.1.0 — ataque e blindagem de segurança

- **Novo squad Ataque & Blindagem** (equipe passa a ter 18 especialistas em 7 squads):
  - `offensive-security-tester` (red team / hacker ético): ataca o software ou app criado pela equipe como um invasor, explora e prova cada vulnerabilidade com prova de conceito não destrutiva (OWASP Top 10, API Security, MASVS/MASTG, CWE) e faz o reteste — só no projeto e em ambiente local ou de testes autorizado;
  - `security-hardening-engineer` (blue team): corrige a causa raiz, aplica defesa em profundidade, transforma cada prova de conceito em teste de regressão de segurança e adiciona prevenção contínua.
- **Nova etapa final "Ataque e blindagem"**, entre a revisão independente e a entrega, em todos os playbooks e na definição de pronto.
- Painel: 9 etapas, gate `pentest`, achados com tipo (`bug`, `vulnerabilidade`, `qualidade`) e CWE, contagem de vulnerabilidades abertas, relatório com tipo e CWE; a demonstração inclui ataque, blindagem e reteste.

## 1.0.0 — primeira versão pública

- **Equipe de 16 especialistas** em 6 squads (Produto & Design, Arquitetura, Engenharia, Dados & IA, Plataforma & Qualidade, Revisão independente) + coordenador, para Claude Code (`/masterdev`) e Codex (`$masterdev`).
- **Quatro modos** com playbooks: construir do zero, evoluir um produto, revisar e depurar. Definição de pronto cobrindo produto, acessibilidade, código, segurança, dados, verificação, revisão e entrega.
- **Fonte única da equipe** (`team.json`) gerando os agentes do Claude Code e do Codex (`scripts/build_agents.py`); revisores em modo somente leitura.
- **Painel de produção em tempo real**, evolução do painel do Master Data Engineer:
  - 6 visões: visão geral por squads, tarefas com dependências, linha do tempo com faixa de etapas, qualidade, entregáveis e histórico com métricas;
  - novos eventos: entregáveis (`artifact`), gates de qualidade (`gate`), achados de revisão (`finding`), decisões de arquitetura (`decision`) e dependências entre tarefas (`--after`);
  - índice de saúde da missão (0–100) e faixa "Precisa de atenção" com bloqueios, gates reprovados e achados graves;
  - painel lateral por especialista, filtros por squad e por tipo de atividade, avisos do navegador e relatório da missão em Markdown (`report` e tecla E);
  - versão de celular com abas roláveis, tema claro/escuro, modo TV e Content-Security-Policy.
- **Instalador de um comando** (Windows, macOS e Linux) com escopo de usuário ou de projeto, preservação de arquivos de outras origens e hooks com marcador próprio (convive com o Master Data Engineer instalado na mesma máquina).
- **Memória contextual local** (SQLite), isolada por operador e por projeto.
- Repositório público com CI em Windows/macOS/Linux, modelos de issue e PR, CONTRIBUTING, SECURITY e release por tag.
