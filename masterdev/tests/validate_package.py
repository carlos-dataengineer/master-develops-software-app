"""Valida a estrutura do pacote: manifestos, skill, 16 agentes (Claude Code e Codex), painel e memória."""
from __future__ import annotations

import json
import py_compile
import subprocess
import sys
import tomllib
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
VERSION_FILE = REPO / "VERSION"
EXPECTED_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else None
SKILL = ROOT / "skills" / "masterdev"
errors: list[str] = []

for manifest in (ROOT / ".claude-plugin/plugin.json", ROOT / ".codex-plugin/plugin.json"):
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["name"] == "masterdev", "nome deve ser masterdev"
        assert EXPECTED_VERSION is None or data["version"] == EXPECTED_VERSION, f"versão {data['version']} != VERSION {EXPECTED_VERSION}"
        assert data["skills"] == "./skills/"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{manifest.relative_to(REPO)}: {exc}")

market = REPO / ".claude-plugin" / "marketplace.json"
if market.exists():
    data = json.loads(market.read_text(encoding="utf-8"))
    if EXPECTED_VERSION and data["plugins"][0]["version"] != EXPECTED_VERSION:
        errors.append("marketplace.json com versão diferente de VERSION")

content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
if not content.startswith("---\nname: masterdev\n"):
    errors.append("Frontmatter da skill sem name: masterdev")
for phrase in ("Construir um software ou aplicativo do zero", "Evoluir um produto existente", "Revisar um código",
               "Corrigir um bug", "team_board.py", "contextual_memory.py", "Resposta final obrigatória"):
    if phrase not in content:
        errors.append(f"SKILL.md sem o trecho obrigatório: {phrase}")

team = json.loads((SKILL / "assets" / "team.json").read_text(encoding="utf-8"))
keys = [a["key"] for a in team["agents"]]
if len(keys) != 16 or len(set(keys)) != 16:
    errors.append(f"team.json deve ter 16 agentes únicos; tem {len(keys)}")
for key in keys:
    if f"`{key}`" not in content:
        errors.append(f"SKILL.md não apresenta o agente {key}")

claude_agents = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))
codex_agents = sorted(p.stem for p in (ROOT / ".codex" / "agents").glob("*.toml"))
if claude_agents != sorted(keys):
    errors.append(f"Agentes do Claude Code diferentes de team.json: {claude_agents}")
if codex_agents != sorted(k.replace("-", "_") for k in keys):
    errors.append(f"Agentes do Codex diferentes de team.json: {codex_agents}")
for agent in (ROOT / ".codex" / "agents").glob("*.toml"):
    try:
        data = tomllib.loads(agent.read_text(encoding="utf-8"))
        assert data.get("name") and data.get("description") and data.get("developer_instructions")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{agent.name}: TOML inválido ou campo faltando: {exc}")

check = subprocess.run([sys.executable, str(REPO / "scripts" / "build_agents.py"), "--check"], capture_output=True,
                       text=True, encoding="utf-8")
if check.returncode != 0:
    errors.append("Agentes desatualizados em relação a team.json:\n" + check.stdout)

for rel in ("scripts/team_board.py", "scripts/contextual_memory.py", "assets/painel.html", "assets/team.json",
            "agents/openai.yaml", "references/PLAYBOOKS.md", "references/DEFINITION-OF-DONE.md",
            "references/CONTEXTUAL-LEARNING.md", "references/BOARD-PROTOCOL.md"):
    if not (SKILL / rel).is_file():
        errors.append(f"Falta {rel}")
panel = SKILL / "assets" / "painel.html"
if panel.is_file() and "/*__MASTERDEV_CONFIG__*/null" not in panel.read_text(encoding="utf-8"):
    errors.append("Painel sem o marcador de configuração")
for script in (SKILL / "scripts" / "team_board.py", SKILL / "scripts" / "contextual_memory.py"):
    try:
        py_compile.compile(str(script), doraise=True)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{script.name} não compila: {exc}")

if errors:
    print("FAIL")
    print("\n".join(errors))
    raise SystemExit(1)
print("PASS: manifestos, skill (4 modos), 16 agentes Claude Code/Codex em dia com team.json, painel e memória contextual válidos.")
