"""Gera os perfis dos agentes a partir da fonte única `team.json`.

    python scripts/build_agents.py          # escreve masterdev/agents/*.md e masterdev/.codex/agents/*.toml
    python scripts/build_agents.py --check  # só confere se os arquivos estão em dia (usado nos testes e no CI)

Edite os agentes em masterdev/skills/masterdev/assets/team.json e rode este script. O painel
lê o mesmo arquivo, então nomes, siglas, cores e squads ficam sempre iguais em todo lugar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "masterdev"
TEAM = PKG / "skills" / "masterdev" / "assets" / "team.json"
CLAUDE_DIR = PKG / "agents"
CODEX_DIR = PKG / ".codex" / "agents"
READONLY_TOOLS = "Read, Grep, Glob, Bash, WebFetch, WebSearch"


def _q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _toml_ml(text: str) -> str:
    return '"""' + text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '"""'


def render(team: dict) -> dict[Path, str]:
    out: dict[Path, str] = {}
    rules = team["common_rules"]
    for a in team["agents"]:
        body = f"{a['instructions']}\n\n{rules}\n"
        front = [f"name: {a['key']}", f"description: {_q(a['description'])}"]
        if a.get("readonly"):
            front.append(f"tools: {READONLY_TOOLS}")
        out[CLAUDE_DIR / f"{a['key']}.md"] = "---\n" + "\n".join(front) + "\n---\n\n" + body
        codex_name = a["key"].replace("-", "_")
        lines = [f"name = {_q(codex_name)}", f"description = {_q(a['description'])}"]
        if a.get("readonly"):
            lines.append('sandbox_mode = "read-only"')
        lines.append(f"developer_instructions = {_toml_ml(body.rstrip())}")
        out[CODEX_DIR / f"{codex_name}.toml"] = "\n".join(lines) + "\n"
    return out


def main(argv: list[str]) -> int:
    team = json.loads(TEAM.read_text(encoding="utf-8"))
    files = render(team)
    check = "--check" in argv
    stale = []
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    expected = set(files)
    extra = [p for d, pat in ((CLAUDE_DIR, "*.md"), (CODEX_DIR, "*.toml")) for p in d.glob(pat) if p not in expected]
    if check:
        if stale or extra:
            for p in stale + extra:
                print(f"desatualizado: {p.relative_to(ROOT)}")
            print("Rode: python scripts/build_agents.py")
            return 1
        print(f"OK: {len(team['agents'])} agentes em dia (Claude Code e Codex).")
        return 0
    for p in extra:
        p.unlink()
        print(f"removido: {p.relative_to(ROOT)}")
    print(f"{len(stale)} arquivo(s) escrito(s); {len(team['agents'])} agentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
