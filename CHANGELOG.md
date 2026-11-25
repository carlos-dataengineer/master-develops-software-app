# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem [SemVer](https://semver.org/lang/pt-BR/).

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
