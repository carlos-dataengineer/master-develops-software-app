# Arquitetura

O Master Develops tem quatro peças: a **skill coordenadora**, os **18 agentes**, o **painel de produção** e a **memória contextual**. Tudo roda localmente, dentro do Claude Code ou do Codex, com Python da biblioteca padrão.

```mermaid
flowchart TB
  OP([Você]) -->|/masterdev ou $masterdev| CO
  subgraph Host[Claude Code ou Codex]
    CO[Coordenador<br/>skill masterdev]
    subgraph Squads
      PD[Produto & Design<br/>PM · UX/UI]
      AR[Arquitetura<br/>Software Architect]
      EN[Engenharia<br/>Frontend · Mobile · Backend · Banco]
      DI[Dados & IA<br/>Data Engineer · Data Scientist]
      PQ[Plataforma & Qualidade<br/>DevOps · Segurança · QA · Performance · Docs]
      RV[Revisão independente<br/>Corretude · Manutenibilidade]
      AB[Ataque & Blindagem<br/>Hacker ético · Blindagem]
    end
    CO -->|delegação com escopo| PD & AR & EN & DI & PQ & RV & AB
  end
  CO -->|start · stage · task · artifact · gate · finding · decision| TB[(team_board.py<br/>events.jsonl)]
  HK[Hooks PreToolUse/PostToolUse] -->|início e fim de subagente| TB
  TB -->|SSE 127.0.0.1:47841| PN[Painel de produção<br/>navegador]
  CO <-->|recall · remember| MEM[(contextual_memory.py<br/>SQLite local)]
```

## Fluxo de uma missão

```mermaid
sequenceDiagram
  participant O as Você
  participant C as Coordenador
  participant E as Especialistas
  participant R as Revisores
  participant P as Painel
  O->>C: /masterdev
  C->>O: Construir, evoluir, revisar ou depurar?
  O->>C: Construir
  C->>P: ensure + start (modo, título, plataformas, stack)
  C->>C: memória: status + recall
  C->>E: descoberta (PM, UX, dados)
  C->>E: arquitetura (arquiteto, banco, segurança)
  C->>P: decision ADR-1, artifact docs/...
  C->>E: construção em paralelo (arquivos separados, --after)
  E-->>C: resultados + validações reais
  C->>P: gate build/lint/tipos/testes
  C->>R: revisão independente em paralelo
  R-->>C: achados com severidade e evidência
  C->>P: finding F1..Fn, correções
  C->>E: ataque controlado (hacker ético) no ambiente de testes
  E-->>C: vulnerabilidades com prova de conceito
  C->>E: blindagem + testes de regressão de segurança
  C->>E: reteste do ataque
  C->>P: finding V1..Vn (vulnerabilidade), gate pentest
  C->>P: finish + report
  C->>O: resultado, como rodar, decisões, arquivos, validações, riscos
```

## Peças

| Peça | Onde | Responsabilidade |
|---|---|---|
| Skill coordenadora | `masterdev/skills/masterdev/SKILL.md` | Pergunta o modo, aplica princípios, escolhe especialistas, delega, integra e entrega |
| Playbooks | `references/PLAYBOOKS.md` | Passo a passo de construir, evoluir, revisar e depurar; núcleo sugerido por tipo de produto |
| Definição de pronto | `references/DEFINITION-OF-DONE.md` | Checklist antes da entrega |
| Equipe | `assets/team.json` → `agents/*.md`, `.codex/agents/*.toml` | Fonte única dos 18 especialistas |
| Painel | `scripts/team_board.py` + `assets/painel.html` | Eventos, estado, servidor SSE, hooks, relatório, demonstração |
| Memória | `scripts/contextual_memory.py` | Conhecimento persistente por operador e projeto |
| Instalador | `install.ps1`, `install.sh` → `scripts/install.py` | Copia skill e agentes, liga hooks, gera o painel |

## Decisões

- **Somente biblioteca padrão do Python** no que vai para a máquina do usuário: instala em qualquer lugar sem `pip`.
- **Eventos em JSONL, estado calculado na leitura:** nada se corrompe se dois processos escreverem ao mesmo tempo; eventos malformados são ignorados.
- **Servidor somente leitura em 127.0.0.1:** a escrita acontece só pela linha de comando local.
- **Uma fonte para a equipe:** `team.json` evita divergência entre Claude Code, Codex e painel.
- **Convivência:** o hook usa marcador próprio (`hook --app masterdev`) e o script instalado tem nome próprio (`masterdev_board.py`), para não colidir com o Master Data Engineer.
