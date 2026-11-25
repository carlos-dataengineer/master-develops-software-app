"""Núcleo do instalador do Master Develops (chamado por install.sh e install.ps1).

O que faz, nesta ordem:
  1. instala a skill `masterdev` e os 16 agentes no Claude Code e no Codex;
  2. cria a pasta do aplicativo (padrão ~/MasterDevelops) com o painel de produção;
  3. no Claude Code, liga hooks que registram sozinhos o início e o fim de cada subagente;
  4. gera a ferramenta — o Painel de produção — e abre no navegador (http://127.0.0.1:47841).

Segurança:
  - só substitui uma skill ou agente que o próprio Master Develops instalou; o que vier de
    outra origem é preservado e o instalador avisa (use --force para substituir);
  - antes de mexer no settings.json do Claude Code, guarda uma cópia (settings.json.bak-mdv);
  - nada é enviado para a internet; o painel escuta só em 127.0.0.1.

Uso (a partir da raiz do repositório):
    python scripts/install.py
    python scripts/install.py --scope project --project C:/caminho/do/projeto
    python scripts/install.py --skip-codex --no-hooks --no-open
    python scripts/install.py --uninstall            # remove; mantém o histórico de missões e a memória
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "masterdev"
SKILL_SRC = PKG / "skills" / "masterdev"
CLAUDE_AGENTS_SRC = PKG / "agents"
CODEX_AGENTS_SRC = PKG / ".codex" / "agents"
MARK = ".mdv-install"
AGENT_SIGNATURE = "Regras comuns da equipe:"
HOOK_TAG = "hook --app masterdev"
BOARD_NAME = "masterdev_board.py"  # nome próprio: não se confunde com o team_board.py de outros pacotes
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip() if (REPO / "VERSION").exists() else "dev"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def step(text: str) -> None:
    print(f"  {_c('36', '>')} {text}")


def ok(text: str) -> None:
    print(f"  {_c('32', '✓')} {text}")


def warn(text: str) -> None:
    print(f"  {_c('33', '!')} {text}")


# ---------------------------------------------------------------- destinos

def targets(scope: str, project: Path | None) -> dict[str, Path]:
    if scope == "project":
        assert project is not None
        return {
            "claude_skills": project / ".claude" / "skills",
            "claude_agents": project / ".claude" / "agents",
            "claude_settings": project / ".claude" / "settings.local.json",
            "codex_skills": project / ".agents" / "skills",
            "codex_agents": project / ".codex" / "agents",
        }
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    return {
        "claude_skills": home / ".claude" / "skills",
        "claude_agents": home / ".claude" / "agents",
        "claude_settings": home / ".claude" / "settings.json",
        "codex_skills": home / ".agents" / "skills",
        "codex_agents": codex_home / "agents",
    }


def skill_is_ours(folder: Path) -> bool:
    if (folder / MARK).exists():
        return True
    skill = folder / "SKILL.md"
    if not skill.exists():
        return False
    head = skill.read_text(encoding="utf-8", errors="replace")[:600]
    return "name: masterdev" in head and "software e aplicativos" in head


def agent_is_ours(path: Path) -> bool:
    try:
        return AGENT_SIGNATURE in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


# ---------------------------------------------------------------- instalação

def install_skill(dest_root: Path, label: str, force: bool) -> bool:
    dest = dest_root / "masterdev"
    if dest.exists():
        if not (skill_is_ours(dest) or force):
            warn(f"{dest} já existe e não foi instalada pelo Master Develops. Pulei (use --force).")
            return False
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_SRC, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (dest / MARK).write_text(f"Instalada pelo Master Develops {VERSION}.\n", encoding="utf-8")
    ok(f"{label}: skill masterdev em {dest}")
    return True


def install_agents(src: Path, dest: Path, pattern: str, label: str, force: bool) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    done, skipped = [], []
    for item in sorted(src.glob(pattern)):
        target = dest / item.name
        if target.exists() and not (agent_is_ours(target) or force):
            skipped.append(item.name)
            continue
        shutil.copy2(item, target)
        done.append(str(target))
    if done:
        ok(f"{label}: {len(done)} agentes em {dest}")
    for name in skipped:
        warn(f"{dest / name} já existe e não é deste projeto. Pulei (use --force).")
    return done


def install_app(app_home: Path) -> Path:
    app = app_home / "app"
    if app.exists():
        shutil.rmtree(app)
    (app / "scripts").mkdir(parents=True)
    (app / "assets").mkdir()
    shutil.copy2(SKILL_SRC / "scripts" / "team_board.py", app / "scripts" / BOARD_NAME)
    shutil.copy2(SKILL_SRC / "assets" / "painel.html", app / "assets" / "painel.html")
    shutil.copy2(SKILL_SRC / "assets" / "team.json", app / "assets" / "team.json")
    (app_home / "board").mkdir(parents=True, exist_ok=True)
    (app_home / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (app_home / MARK).write_text("Pasta do Master Develops. board/ guarda o histórico de missões.\n",
                                 encoding="utf-8")
    ok(f"Aplicativo do painel em {app}")
    return app / "scripts" / BOARD_NAME


def board_env(app_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["MASTERDEV_HOME"] = str(app_home)
    return env


def write_launchers(app_home: Path, board: Path) -> list[Path]:
    py = Path(sys.executable)
    custom = str(app_home) != str(Path.home() / "MasterDevelops")
    out = []
    cmd = app_home / "Abrir painel.cmd"
    lines = ["@echo off"]
    if custom:
        lines.append(f'set "MASTERDEV_HOME={app_home}"')
    lines.append(f'"{py}" "{board}" ensure --open')
    cmd.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    out.append(cmd)
    sh = app_home / "abrir-painel.sh"
    env = f'MASTERDEV_HOME="{app_home.as_posix()}" ' if custom else ""
    sh.write_text(f'#!/usr/bin/env sh\n{env}exec "{py.as_posix()}" "{board.as_posix()}" ensure --open\n',
                  encoding="utf-8")
    try:
        sh.chmod(0o755)
    except OSError:
        pass
    out.append(sh)
    return out


def hook_command(board: Path, app_home: Path) -> str:
    base = f'"{Path(sys.executable).as_posix()}" "{board.as_posix()}" {HOOK_TAG}'
    if str(app_home) != str(Path.home() / "MasterDevelops"):
        if os.name == "nt":
            return f'set "MASTERDEV_HOME={app_home}" && {base}'
        return f'MASTERDEV_HOME="{app_home.as_posix()}" {base}'
    return base


def _strip_ours(entries: list) -> list:
    clean = []
    for entry in entries:
        hooks = [h for h in entry.get("hooks", []) if HOOK_TAG not in str(h.get("command", ""))]
        if hooks:
            clean.append({**entry, "hooks": hooks})
        elif not entry.get("hooks"):
            clean.append(entry)
    return clean


def configure_hooks(settings: Path, command: str | None) -> bool:
    """Adiciona (command != None) ou remove (None) os hooks do painel. Preserva todo o resto."""
    data: dict = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            warn(f"{settings} não é um JSON válido; não mexi nele. Hooks do painel não foram configurados.")
            return False
        backup = settings.with_name(settings.name + ".bak-mdv")
        if command and not backup.exists():
            shutil.copy2(settings, backup)
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    changed = False
    for event in ("PreToolUse", "PostToolUse"):
        current = hooks.get(event, []) if isinstance(hooks.get(event), list) else []
        cleaned = _strip_ours(current)
        if command:
            cleaned.append({"matcher": "Task|Agent", "hooks": [{"type": "command", "command": command, "timeout": 10}]})
        if cleaned != current:
            changed = True
        if cleaned:
            hooks[event] = cleaned
        elif event in hooks:
            del hooks[event]
    if hooks:
        data["hooks"] = hooks
    elif "hooks" in data:
        del data["hooks"]
    if changed:
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def run_board(board: Path, app_home: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(board), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=board_env(app_home), timeout=timeout)


# ---------------------------------------------------------------- desinstalação

def uninstall(t: dict[str, Path], app_home: Path, purge: bool) -> int:
    board = app_home / "app" / "scripts" / BOARD_NAME
    if board.exists():
        run_board(board, app_home, "stop", timeout=15)
    for key in ("claude_skills", "codex_skills"):
        dest = t[key] / "masterdev"
        if dest.exists() and skill_is_ours(dest):
            shutil.rmtree(dest)
            ok(f"Removida: {dest}")
    for key, src, pattern in (("claude_agents", CLAUDE_AGENTS_SRC, "*.md"), ("codex_agents", CODEX_AGENTS_SRC, "*.toml")):
        for item in src.glob(pattern):
            target = t[key] / item.name
            if target.exists() and agent_is_ours(target):
                target.unlink()
        ok(f"Agentes removidos de {t[key]}")
    if configure_hooks(t["claude_settings"], None):
        ok(f"Hooks do painel removidos de {t['claude_settings']}")
    if app_home.exists() and (app_home / MARK).exists():
        for name in ("app", "painel.html", "Abrir painel.cmd", "abrir-painel.sh", "VERSION"):
            p = app_home / name
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        if purge and (app_home / "board").exists():
            shutil.rmtree(app_home / "board")
        rest = [p.name for p in app_home.iterdir() if p.name != MARK]
        if rest:
            print(f"    Mantive em {app_home}: {', '.join(sorted(rest))} (histórico de missões; --purge apaga)")
        else:
            (app_home / MARK).unlink()
            app_home.rmdir()
        ok("Painel removido")
    print("\n  Master Develops desinstalado. A memória contextual (SQLite local) foi mantida;")
    print("  para apagá-la, use contextual_memory.py forget-project ou remova a pasta MasterDevelops/Memory.\n")
    return 0


# ---------------------------------------------------------------- principal

def main() -> int:
    ap = argparse.ArgumentParser(description="Instala o Master Develops no Claude Code e no Codex")
    ap.add_argument("--scope", choices=["user", "project"], default="user")
    ap.add_argument("--project", help="pasta do projeto (com --scope project)")
    ap.add_argument("--home", help="pasta do painel e do histórico (padrão ~/MasterDevelops)")
    ap.add_argument("--skip-claude", action="store_true")
    ap.add_argument("--skip-codex", action="store_true")
    ap.add_argument("--no-hooks", action="store_true", help="não liga os hooks do Claude Code")
    ap.add_argument("--no-server", action="store_true", help="não sobe o painel agora")
    ap.add_argument("--no-open", action="store_true", help="não abre o navegador")
    ap.add_argument("--force", action="store_true", help="substitui skill/agentes de mesmo nome de outra origem")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--purge", action="store_true", help="com --uninstall, apaga também o histórico de missões")
    a = ap.parse_args()

    env = os.environ.get
    skip_claude = a.skip_claude or env("MDV_SKIP_CLAUDE") == "1"
    skip_codex = a.skip_codex or env("MDV_SKIP_CODEX") == "1"
    no_hooks = a.no_hooks or env("MDV_NO_HOOKS") == "1"
    no_open = a.no_open or env("MDV_NO_OPEN") == "1"
    no_server = a.no_server or env("MDV_NO_SERVER") == "1"
    home_raw = a.home or env("MASTERDEV_HOME")
    app_home = Path(home_raw).expanduser().resolve() if home_raw else Path.home() / "MasterDevelops"

    project = None
    if a.scope == "project":
        if not a.project:
            print("Informe --project quando usar --scope project.", file=sys.stderr)
            return 2
        project = Path(a.project).expanduser().resolve()
        if not project.is_dir():
            print(f"A pasta do projeto não existe: {project}", file=sys.stderr)
            return 2
    t = targets(a.scope, project)

    print(f"\n  {_c('1', 'Master Develops')} {VERSION} — equipe de desenvolvimento de software e apps para Claude Code e Codex\n")
    if a.uninstall:
        return uninstall(t, app_home, a.purge)

    for required in (SKILL_SRC / "SKILL.md", SKILL_SRC / "scripts" / "team_board.py", SKILL_SRC / "assets" / "painel.html",
                     SKILL_SRC / "assets" / "team.json"):
        if not required.exists():
            print(f"Pacote incompleto: falta {required}", file=sys.stderr)
            return 1

    installed_any = False
    if not skip_claude:
        installed_any |= install_skill(t["claude_skills"], "Claude Code", a.force)
        install_agents(CLAUDE_AGENTS_SRC, t["claude_agents"], "*.md", "Claude Code", a.force)
    if not skip_codex:
        installed_any |= install_skill(t["codex_skills"], "Codex", a.force)
        install_agents(CODEX_AGENTS_SRC, t["codex_agents"], "*.toml", "Codex", a.force)
    if not installed_any:
        warn("Nenhuma skill foi instalada (veja os avisos acima).")

    step("Gerando o Painel de produção")
    board = install_app(app_home)
    launchers = write_launchers(app_home, board)
    r = run_board(board, app_home, "export", str(app_home / "painel.html"))
    if r.returncode == 0:
        ok(f"Ferramenta gerada: {app_home / 'painel.html'}")
    else:
        warn("Não consegui gerar o painel estático: " + (r.stderr.strip().splitlines() or ["erro"])[-1])

    if not skip_claude and not no_hooks:
        if configure_hooks(t["claude_settings"], hook_command(board, app_home)):
            ok(f"Claude Code: hooks do painel ligados em {t['claude_settings']}")
        else:
            ok("Claude Code: hooks do painel já estavam ligados")

    url = None
    if not no_server:
        r = run_board(board, app_home, "ensure", *([] if no_open else ["--open"]), timeout=30)
        if r.returncode == 0:
            url = r.stdout.strip().split()[-1]
            ok(f"Painel no ar: {url}" + ("" if no_open else " (aberto no navegador)"))
        else:
            warn("O painel não subiu agora; use o atalho 'Abrir painel' depois.")

    print()
    print(f"  {_c('1', 'Pronto.')} Abra uma sessão nova do agente para carregar a skill:")
    if not skip_claude:
        print("    Claude Code  →  /masterdev")
    if not skip_codex:
        print("    Codex        →  $masterdev  (ou /skills → masterdev)")
    print(f"  Painel de produção: {url or 'http://127.0.0.1:47841'}")
    print(f"  Atalho para reabrir: {launchers[0] if os.name == 'nt' else launchers[1]}")
    print("  Para conhecer o painel sem um projeto real: abra o painel e tecle D (demonstração).\n")
    time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
