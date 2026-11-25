# Como contribuir

Obrigado pelo interesse! O Master Develops é uma equipe de agentes para **criar, evoluir, revisar e depurar softwares e aplicativos** no Claude Code e no Codex, com um painel de produção local.

## Antes de abrir um PR

1. Abra uma *issue* descrevendo o problema ou a ideia (use os modelos).
2. Crie uma branch a partir de `main`: `feat/...`, `fix/...` ou `docs/...`.
3. Mantenha a mudança pequena e com um único objetivo.

## Estrutura

| Pasta | O que é |
|---|---|
| `masterdev/skills/masterdev/` | A skill coordenadora: `SKILL.md`, `references/` (playbooks, definição de pronto, protocolo do painel, memória), `scripts/` (`team_board.py`, `contextual_memory.py`) e `assets/` (`painel.html`, `team.json`). |
| `masterdev/skills/masterdev/assets/team.json` | **Fonte única da equipe**: nome, sigla, cor, squad, descrição e instruções de cada agente. O painel lê este arquivo. |
| `masterdev/agents/` | Os 18 agentes no formato do Claude Code (`.md`), **gerados** a partir do `team.json`. |
| `masterdev/.codex/agents/` | Os mesmos 18 agentes no formato do Codex (`.toml`), **gerados** a partir do `team.json`. |
| `scripts/build_agents.py` | Gera os agentes a partir do `team.json` (`--check` só confere). |
| `scripts/install.py` | Núcleo do instalador (chamado por `install.sh` e `install.ps1`). |
| `scripts/screenshots.py` | Gera as capturas do README. |
| `tests/`, `masterdev/tests/` | Testes (somente biblioteca padrão). |
| `docs/` | Documentação e imagens. |

## Mudando um agente

Não edite os `.md`/`.toml` à mão. Edite `team.json` e rode:

```bash
python scripts/build_agents.py
```

## Rodando os testes

Requer Python 3.11+ para o validador (usa `tomllib`); a ferramenta em si roda em 3.10+.

```bash
python scripts/build_agents.py --check
python masterdev/tests/validate_package.py
python -m unittest discover -s masterdev/tests -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
```

Os testes do instalador usam uma pasta pessoal falsa: nada é instalado no seu Claude Code ou Codex.

## Capturas de tela

Se mudar o painel, regenere as imagens:

```bash
pip install playwright pillow
python scripts/screenshots.py
```

## Regras

- Sem dependências externas nos scripts que vão para a máquina do usuário (somente biblioteca padrão).
- Nada de telemetria, chamadas de rede ou envio de dados. O painel escuta apenas em `127.0.0.1`.
- Nunca inclua segredos, dados reais, nomes de empresas ou caminhos pessoais em exemplos, testes ou capturas.
- Atualize o `CHANGELOG.md` e, se mudar a versão, o arquivo `VERSION` e os manifestos (`plugin.json`, `marketplace.json`).
- Commits no estilo *Conventional Commits* (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
