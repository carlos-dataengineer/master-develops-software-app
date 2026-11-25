#!/usr/bin/env python3
"""Painel de produção da equipe Master Develops: registro de eventos e servidor local em tempo real.

O coordenador (skill masterdev) registra a missão, as etapas, as tarefas de cada agente, os
entregáveis, os gates de qualidade, os achados de revisão e as decisões de arquitetura.
No Claude Code, hooks opcionais registram sozinhos o início e o fim de cada subagente.
O painel (assets/painel.html) mostra tudo ao vivo em http://127.0.0.1:47841.

Somente biblioteca padrão. O servidor escuta apenas em 127.0.0.1, é somente leitura e não faz
chamadas de rede. Eventos ficam em ~/MasterDevelops/board/events.jsonl.

Uso rápido:
    python team_board.py ensure --open
    python team_board.py start --mode construir --title "App de agendamento" --platforms web,ios,android
    python team_board.py stage descoberta
    python team_board.py task T1 --agent product-manager --status running --title "MVP e critérios de aceite"
    python team_board.py task T2 --agent ux-ui-designer --status queued --title "Telas" --after T1
    python team_board.py artifact docs/telas.md --kind design --agent ux-ui-designer
    python team_board.py gate testes --status pass --value 134/134
    python team_board.py finding F1 --severity alta --agent code-correctness-reviewer --title "..."
    python team_board.py decision ADR-1 --title "Monólito modular" --agent software-architect
    python team_board.py finish --summary "Web + app entregues"
    python team_board.py report                 # relatório da missão em Markdown
    python team_board.py demo --live            # missão simulada, para conhecer o painel
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

APP = "master-develops"
SCHEMA = 1
DEFAULT_PORT = 47841
HERE = Path(__file__).resolve().parent
PANEL_FILE = HERE.parent / "assets" / "painel.html"
TEAM_FILE = HERE.parent / "assets" / "team.json"
MAX_TEXT = 240
MAX_EVENTS_BYTES = 5_000_000


def _load_team() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    team = json.loads(TEAM_FILE.read_text(encoding="utf-8"))
    squads = {s["key"]: s for s in team["squads"]}
    agents = [{**{k: team["coordinator"][k] for k in ("key", "name", "role", "short", "color")},
               "squad": "coordenacao", "squad_name": "Coordenação"}]
    for a in team["agents"]:
        agents.append({"key": a["key"], "name": a["name"], "role": a["role"], "short": a["short"],
                       "color": a["color"], "squad": a["squad"], "squad_name": squads[a["squad"]]["name"],
                       "readonly": bool(a.get("readonly"))})
    return agents, team["squads"]


AGENTS, SQUADS = _load_team()
AGENT_KEYS = {a["key"] for a in AGENTS}
AGENT_BY_KEY = {a["key"]: a for a in AGENTS}

STAGES: list[tuple[str, str]] = [
    ("modo", "Modo de trabalho"),
    ("descoberta", "Produto e requisitos"),
    ("arquitetura", "Arquitetura e design"),
    ("plano", "Plano e equipe"),
    ("construcao", "Construção"),
    ("qualidade", "Testes e qualidade"),
    ("revisao", "Revisão independente"),
    ("entrega", "Entrega"),
]
STAGE_KEYS = [k for k, _ in STAGES]
STAGE_LABEL = dict(STAGES)
STAGE_ALIASES = {
    "mode": "modo", "discovery": "descoberta", "requisitos": "descoberta", "produto": "descoberta",
    "contexto": "descoberta", "memoria": "descoberta", "memória": "descoberta",
    "architecture": "arquitetura", "design": "arquitetura", "planejamento": "plano", "plan": "plano",
    "selecao": "plano", "seleção": "plano", "build": "construcao", "construção": "construcao",
    "implementacao": "construcao", "implementação": "construcao", "execucao": "construcao", "execução": "construcao",
    "testes": "qualidade", "qa": "qualidade", "quality": "qualidade", "validacao": "qualidade", "validação": "qualidade",
    "review": "revisao", "revisão": "revisao", "consolidacao": "entrega", "consolidação": "entrega",
    "delivery": "entrega", "deploy": "entrega",
}
# Hooks: quando um subagente começa, a etapa avança sozinha (nunca volta) conforme o papel.
STAGE_HINT = {
    "frontend-engineer": "construcao", "mobile-engineer": "construcao", "backend-engineer": "construcao",
    "database-engineer": "construcao", "devops-sre-engineer": "construcao",
    "qa-test-engineer": "qualidade", "performance-engineer": "qualidade",
    "code-correctness-reviewer": "revisao", "code-maintainability-reviewer": "revisao",
}
MODES = {"construir": "Construção", "evoluir": "Evolução", "revisar": "Revisão", "depurar": "Debugging",
         "livre": "Sessão livre"}
MODE_ALIASES = {"build": "construir", "novo": "construir", "construcao": "construir", "construção": "construir", "1": "construir",
                "evolve": "evoluir", "feature": "evoluir", "evolucao": "evoluir", "evolução": "evoluir", "melhorar": "evoluir", "2": "evoluir",
                "review": "revisar", "revisao": "revisar", "revisão": "revisar", "3": "revisar",
                "debug": "depurar", "debugging": "depurar", "corrigir": "depurar", "bug": "depurar", "4": "depurar"}
TASK_STATUSES = ("queued", "running", "review", "done", "blocked", "failed")
STATUS_ALIASES = {"fila": "queued", "pendente": "queued", "executando": "running", "em-execucao": "running",
                  "revisao": "review", "revisão": "review", "concluida": "done", "concluída": "done", "ok": "done",
                  "bloqueada": "blocked", "falhou": "failed", "erro": "failed"}
ARTIFACT_KINDS = {"codigo": "Código", "teste": "Teste", "doc": "Documentação", "design": "Design",
                  "infra": "Infraestrutura", "dados": "Dados", "config": "Configuração"}
KIND_ALIASES = {"code": "codigo", "código": "codigo", "test": "teste", "testes": "teste", "docs": "doc",
                "documentacao": "doc", "documentação": "doc", "ui": "design", "ux": "design", "ci": "infra",
                "data": "dados", "db": "dados", "configuracao": "config", "configuração": "config"}
GATES: list[tuple[str, str]] = [
    ("build", "Build"), ("lint", "Lint"), ("tipos", "Tipos"), ("testes", "Testes"), ("e2e", "Ponta a ponta"),
    ("cobertura", "Cobertura"), ("seguranca", "Segurança"), ("acessibilidade", "Acessibilidade"),
    ("performance", "Performance"),
]
GATE_LABEL = dict(GATES)
GATE_ALIASES = {"types": "tipos", "typecheck": "tipos", "tests": "testes", "unit": "testes", "unitarios": "testes",
                "integracao": "testes", "end-to-end": "e2e", "coverage": "cobertura", "security": "seguranca",
                "segurança": "seguranca", "a11y": "acessibilidade", "perf": "performance", "desempenho": "performance"}
GATE_STATUSES = ("pass", "fail", "warn", "skip", "running")
GATE_STATUS_ALIASES = {"ok": "pass", "passou": "pass", "aprovado": "pass", "falhou": "fail", "erro": "fail",
                       "aviso": "warn", "atencao": "warn", "atenção": "warn", "pulado": "skip", "na": "skip",
                       "rodando": "running", "executando": "running"}
SEVERITIES = ("critica", "alta", "media", "baixa")
SEVERITY_LABEL = {"critica": "Crítica", "alta": "Alta", "media": "Média", "baixa": "Baixa"}
SEVERITY_ALIASES = {"crítica": "critica", "critical": "critica", "high": "alta", "média": "media", "medium": "media",
                    "low": "baixa"}
FINDING_STATUSES = ("aberto", "corrigido", "aceito")
FINDING_ALIASES = {"open": "aberto", "fixed": "corrigido", "resolvido": "corrigido", "accepted": "aceito"}

SENSITIVE = [
    re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|password|passwd|senha|secret|access[_-]?token|refresh[_-]?token)\s*[:=]\s*\S{6,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/]+:[^\s@/]+@"),
]

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# ---------------------------------------------------------------- utilidades

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def app_home() -> Path:
    raw = os.environ.get("MASTERDEV_HOME")
    return Path(raw).expanduser() if raw else Path.home() / "MasterDevelops"


def board_dir() -> Path:
    raw = os.environ.get("MASTERDEV_BOARD_HOME")
    path = Path(raw).expanduser() if raw else app_home() / "board"
    path.mkdir(parents=True, exist_ok=True)
    return path


def events_file() -> Path:
    return board_dir() / "events.jsonl"


def server_file() -> Path:
    return board_dir() / "server.json"


def clean(text: Any, limit: int = MAX_TEXT) -> str:
    """Texto curto e de uma linha; troca o que parece credencial por um aviso."""
    if text is None:
        return ""
    value = " ".join(str(text).split())
    for pat in SENSITIVE:
        if pat.search(value):
            return "[conteúdo omitido: parece conter uma credencial]"
    return value if len(value) <= limit else value[: limit - 1] + "…"


def short_path(raw: str) -> str:
    """Guarda caminhos relativos; de um caminho absoluto, só as três últimas partes."""
    value = clean(raw, 160).replace("\\", "/")
    if re.match(r"^([A-Za-z]:/|/|~)", value):
        parts = [p for p in value.split("/") if p and not p.endswith(":")]
        value = "/".join(parts[-3:])
    return value


def _norm(raw: str, aliases: dict[str, str], valid: Iterable[str], what: str) -> str:
    key = raw.strip().lower()
    key = aliases.get(key, key)
    valid = list(valid)
    if key not in valid:
        raise ValueError(f"{what} desconhecido(a): {raw}. Use: {', '.join(valid)}")
    return key


def norm_agent(raw: str | None) -> str:
    if not raw:
        return "coordinator"
    key = raw.strip().lower().replace("_", "-").replace(" ", "-")
    key = key.split(":")[-1]  # plugin:agente
    if key in ("coordenador", "masterdev", "coord"):
        return "coordinator"
    return key


def norm_stage(raw: str) -> str:
    return _norm(raw, STAGE_ALIASES, STAGE_KEYS, "Etapa")


def norm_mode(raw: str) -> str:
    return _norm(raw, MODE_ALIASES, [m for m in MODES if m != "livre"], "Modo")


def norm_status(raw: str) -> str:
    return _norm(raw, STATUS_ALIASES, TASK_STATUSES, "Status")


def norm_kind(raw: str) -> str:
    return _norm(raw, KIND_ALIASES, ARTIFACT_KINDS, "Tipo de entregável")


def norm_gate(raw: str) -> str:
    key = raw.strip().lower()
    key = GATE_ALIASES.get(key, key)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,23}", key):
        raise ValueError(f"Nome de gate inválido: {raw}. Sugestões: {', '.join(GATE_LABEL)}")
    return key


def norm_gate_status(raw: str) -> str:
    return _norm(raw, GATE_STATUS_ALIASES, GATE_STATUSES, "Status do gate")


def norm_severity(raw: str) -> str:
    return _norm(raw, SEVERITY_ALIASES, SEVERITIES, "Severidade")


def norm_finding_status(raw: str) -> str:
    return _norm(raw, FINDING_ALIASES, FINDING_STATUSES, "Status do achado")


def check_agent(raw: str) -> str:
    agent = norm_agent(raw)
    if agent not in AGENT_KEYS:
        raise ValueError(f"Agente desconhecido: {raw}. Use: {', '.join(sorted(AGENT_KEYS))}")
    return agent


# ---------------------------------------------------------------- eventos

_lock = threading.Lock()


def append(event: dict[str, Any], ts: datetime | None = None) -> dict[str, Any]:
    event = {"v": SCHEMA, "ts": iso(ts or utc_now()), **event}
    line = json.dumps(event, ensure_ascii=False)
    with _lock, open(events_file(), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return event


def read_events(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or events_file()
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict) and ev.get("type") and ev.get("ts"):
                out.append(ev)
    return out


def new_run_id(now: datetime) -> str:
    return now.strftime("r%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]


def active_run_id(events: Iterable[dict[str, Any]]) -> str | None:
    started: dict[str, str] = {}
    ended: set[str] = set()
    for ev in events:
        if ev["type"] == "run.start":
            started[ev["run"]] = ev["ts"]
        elif ev["type"] == "run.end":
            ended.add(ev.get("run", ""))
    live = [(ts, rid) for rid, ts in started.items() if rid not in ended]
    return max(live)[1] if live else None


def resolve_run(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("MASTERDEV_RUN")
    if env:
        return env
    rid = active_run_id(read_events())
    if not rid:
        raise SystemExit("Nenhuma missão ativa. Comece com: team_board.py start --mode construir --title \"...\"")
    return rid


# ---------------------------------------------------------------- estado

def _blank_run(ev: dict[str, Any]) -> dict[str, Any]:
    mode = ev.get("mode", "livre")
    return {
        "id": ev["run"], "title": ev.get("title") or "Missão sem título", "mode": mode,
        "mode_label": MODES.get(mode, "Sessão livre"), "project": ev.get("project") or "",
        "host": ev.get("host") or "", "platforms": ev.get("platforms") or [], "stack": ev.get("stack") or "",
        "status": "active", "started": ev["ts"], "ended": None, "summary": "", "current_stage": None,
        "stages": {k: {"key": k, "label": label, "status": "pending", "started": None, "ended": None, "note": ""}
                   for k, label in STAGES},
        "tasks": {}, "task_order": [], "feed": [], "updated": ev["ts"],
        "artifacts": [], "gates": {}, "gate_order": [], "findings": {}, "finding_order": [], "decisions": [],
    }


def _feed(run: dict[str, Any], ev: dict[str, Any], kind: str, text: str, agent: str = "coordinator",
          status: str = "") -> None:
    run["feed"].append({"ts": ev["ts"], "kind": kind, "agent": agent, "text": text, "status": status})


def _set_stage(run: dict[str, Any], key: str, ts: str, status: str = "running", note: str = "") -> None:
    idx = STAGE_KEYS.index(key)
    for k in STAGE_KEYS[:idx]:
        st = run["stages"][k]
        if st["status"] != "done":
            st["status"] = "done" if st["started"] or k == "modo" else "skipped"
            st["started"] = st["started"] or (ts if st["status"] == "done" else None)
            st["ended"] = st["ended"] or ts
    st = run["stages"][key]
    if status == "done":
        st["status"] = "done"
        st["started"] = st["started"] or ts
        st["ended"] = ts
    else:
        st["status"] = "running"
        st["started"] = st["started"] or ts
        st["ended"] = None
        run["current_stage"] = key
        for k in STAGE_KEYS[idx + 1:]:  # voltou uma etapa (ex.: revisão reabriu a construção)
            if run["stages"][k]["status"] == "running":
                run["stages"][k]["status"] = "pending"
    if note:
        st["note"] = note


def _apply_task(run: dict[str, Any], ev: dict[str, Any]) -> None:
    ts = ev["ts"]
    tasks = run["tasks"]
    agent = norm_agent(ev.get("agent")) if ev.get("agent") else None
    status = ev.get("status", "running")
    tid = ev.get("task")
    hook_id = ev.get("hook_id")

    if ev.get("source") == "hook" and hook_id:
        linked = next((t for t in tasks.values() if t.get("hook_id") == hook_id), None)
        if linked is None and status == "running":
            # liga ao item que o coordenador já anunciou para esse agente
            linked = next((tasks[i] for i in reversed(run["task_order"])
                           if tasks[i]["agent"] == agent and tasks[i]["status"] in ("queued", "running")
                           and not tasks[i].get("hook_id")), None)
        if linked is not None:
            tid = linked["id"]
            linked["hook_id"] = hook_id
        elif not tid:
            tid = "H" + hook_id[-6:]

    if not tid:
        return
    task = tasks.get(tid)
    if task is None:
        task = {"id": tid, "agent": agent or "coordinator", "title": ev.get("title") or tid, "status": "queued",
                "note": "", "created": ts, "started": None, "ended": None, "updated": ts, "after": [],
                "source": ev.get("source", "coordinator")}
        if hook_id:
            task["hook_id"] = hook_id
        tasks[tid] = task
        run["task_order"].append(tid)
    if agent:
        task["agent"] = agent
    if ev.get("title") and (ev.get("source") != "hook" or task["title"] == tid):
        task["title"] = ev["title"]
    if ev.get("note"):
        task["note"] = ev["note"]
    if ev.get("after"):
        task["after"] = [a for a in ev["after"] if a != tid]
    previous = task["status"]
    task["status"] = status
    task["updated"] = ts
    if status == "running" and not task["started"]:
        task["started"] = ts
    if status in ("done", "failed"):
        task["started"] = task["started"] or ts
        task["ended"] = ts
    elif status in ("queued", "running", "review"):
        task["ended"] = None
    if previous != status or ev.get("note"):
        verb = {"queued": "entrou na fila", "running": "começou", "review": "foi para revisão",
                "done": "concluiu", "blocked": "está bloqueada", "failed": "falhou"}[status]
        text = f"{task['title']} — {verb}"
        if ev.get("note"):
            text += f" · {ev['note']}"
        _feed(run, ev, "task", text, task["agent"], status)
    hint = STAGE_HINT.get(task["agent"])
    if (status == "running" and ev.get("source") == "hook" and hint and run["mode"] != "livre"
            and (run["current_stage"] is None or STAGE_KEYS.index(hint) > STAGE_KEYS.index(run["current_stage"]))):
        _set_stage(run, hint, ts)


def _apply_gate(run: dict[str, Any], ev: dict[str, Any]) -> None:
    key = ev["gate"]
    gate = run["gates"].get(key)
    if gate is None:
        gate = run["gates"][key] = {"key": key, "label": GATE_LABEL.get(key, key.capitalize()), "status": "running",
                                    "value": "", "note": "", "updated": ev["ts"], "history": []}
        run["gate_order"].append(key)
    gate["status"] = ev.get("status", "pass")
    gate["value"] = ev.get("value", "")
    gate["note"] = ev.get("note", "")
    gate["updated"] = ev["ts"]
    gate["history"].append({"ts": ev["ts"], "status": gate["status"], "value": gate["value"]})
    word = {"pass": "aprovado", "fail": "reprovado", "warn": "com avisos", "skip": "não se aplica",
            "running": "em execução"}[gate["status"]]
    text = f"Gate {gate['label']} {word}" + (f" ({gate['value']})" if gate["value"] else "") + \
        (f" · {gate['note']}" if gate["note"] else "")
    status = {"pass": "done", "fail": "failed", "warn": "blocked", "running": "running"}.get(gate["status"], "")
    _feed(run, ev, "gate", text, norm_agent(ev.get("agent")), status)


def _apply_finding(run: dict[str, Any], ev: dict[str, Any]) -> None:
    fid = ev["finding"]
    f = run["findings"].get(fid)
    if f is None:
        f = run["findings"][fid] = {"id": fid, "severity": ev.get("severity", "media"), "title": ev.get("title") or fid,
                                    "agent": norm_agent(ev.get("agent")) if ev.get("agent") else "coordinator",
                                    "where": ev.get("where", ""), "status": "aberto", "note": "",
                                    "created": ev["ts"], "updated": ev["ts"]}
        run["finding_order"].append(fid)
        new = True
    else:
        new = False
    for k in ("severity", "title", "where", "note"):
        if ev.get(k):
            f[k] = ev[k]
    if ev.get("agent") and new:
        f["agent"] = norm_agent(ev["agent"])
    previous = f["status"]
    f["status"] = ev.get("status") or f["status"]
    f["updated"] = ev["ts"]
    if new:
        text = f"Achado {fid} ({SEVERITY_LABEL[f['severity']]}): {f['title']}" + (f" · {f['where']}" if f["where"] else "")
        _feed(run, ev, "finding", text, f["agent"], "failed" if f["severity"] in ("critica", "alta") else "blocked")
    elif previous != f["status"]:
        word = {"corrigido": "corrigido", "aceito": "aceito pelo operador", "aberto": "reaberto"}[f["status"]]
        _feed(run, ev, "finding", f"Achado {fid} {word}: {f['title']}", norm_agent(ev.get("agent") or f["agent"]),
              "done" if f["status"] != "aberto" else "blocked")


def fold(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for ev in events:
        typ = ev.get("type")
        rid = ev.get("run")
        if typ == "run.start":
            run = runs[rid] = _blank_run(ev)
            _set_stage(run, "modo", ev["ts"], "done")
            _feed(run, ev, "run", f"Missão iniciada: {run['title']} ({run['mode_label']})")
            continue
        run = runs.get(rid)
        if run is None:
            continue
        run["updated"] = ev["ts"]
        try:
            if typ == "stage":
                _set_stage(run, ev["stage"], ev["ts"], ev.get("status", "running"), ev.get("note", ""))
                verb = "concluída" if ev.get("status") == "done" else "em andamento"
                text = f"Etapa {STAGE_LABEL[ev['stage']]} {verb}" + (f" · {ev['note']}" if ev.get("note") else "")
                _feed(run, ev, "stage", text)
            elif typ == "task":
                _apply_task(run, ev)
            elif typ == "note":
                _feed(run, ev, "note", ev.get("text", ""), norm_agent(ev.get("agent")))
            elif typ == "artifact":
                art = {"name": ev.get("name", ""), "kind": ev.get("kind", "codigo"), "agent": norm_agent(ev.get("agent")),
                       "task": ev.get("task", ""), "note": ev.get("note", ""), "ts": ev["ts"]}
                run["artifacts"] = [a for a in run["artifacts"] if a["name"] != art["name"]] + [art]
                _feed(run, ev, "artifact", f"Entregável ({ARTIFACT_KINDS.get(art['kind'], art['kind'])}): {art['name']}"
                      + (f" · {art['note']}" if art["note"] else ""), art["agent"])
            elif typ == "gate":
                _apply_gate(run, ev)
            elif typ == "finding":
                _apply_finding(run, ev)
            elif typ == "decision":
                dec = {"id": ev.get("decision", ""), "title": ev.get("title", ""), "agent": norm_agent(ev.get("agent")),
                       "note": ev.get("note", ""), "ts": ev["ts"]}
                run["decisions"] = [d for d in run["decisions"] if d["id"] != dec["id"]] + [dec]
                _feed(run, ev, "decision", f"Decisão {dec['id']}: {dec['title']}", dec["agent"])
            elif typ == "run.end":
                run["status"] = ev.get("status", "done")
                run["ended"] = ev["ts"]
                run["summary"] = ev.get("summary", "")
                if run["status"] == "done":
                    for st in run["stages"].values():
                        if st["status"] in ("pending", "running"):
                            st["status"] = "done" if st["started"] else "skipped"
                            st["ended"] = st["ended"] or ev["ts"]
                    run["current_stage"] = None
                else:
                    cur = run["current_stage"]
                    if cur:
                        run["stages"][cur]["status"] = "failed" if run["status"] == "failed" else "pending"
                label = {"done": "concluída", "failed": "encerrada com falha", "cancelled": "cancelada"}.get(
                    run["status"], run["status"])
                _feed(run, ev, "run", f"Missão {label}" + (f": {run['summary']}" if run["summary"] else ""),
                      "coordinator", "done" if run["status"] == "done" else "failed")
        except (KeyError, ValueError, TypeError):  # evento malformado não derruba o painel
            continue
    return runs


def health(run: dict[str, Any]) -> dict[str, Any]:
    """Índice de saúde 0–100: gates reprovados, achados abertos e tarefas travadas descontam pontos."""
    score = 100
    reasons = []
    for g in run["gates"].values():
        if g["status"] == "fail":
            score -= 15
            reasons.append(f"gate {g['label']} reprovado")
        elif g["status"] == "warn":
            score -= 5
            reasons.append(f"gate {g['label']} com avisos")
    weight = {"critica": 25, "alta": 12, "media": 4, "baixa": 1}
    for f in run["findings"].values():
        if f["status"] == "aberto":
            score -= weight[f["severity"]]
            if f["severity"] in ("critica", "alta"):
                reasons.append(f"achado {f['id']} ({SEVERITY_LABEL[f['severity']].lower()}) aberto")
    for t in run["tasks"].values():
        if t["status"] == "blocked":
            score -= 6
            reasons.append(f"tarefa {t['id']} bloqueada")
        elif t["status"] == "failed":
            score -= 10
            reasons.append(f"tarefa {t['id']} falhou")
    if run["status"] == "failed":
        score -= 20
    score = max(0, min(100, score))
    label = "Saudável" if score >= 80 else "Atenção" if score >= 55 else "Em risco"
    return {"score": score, "label": label, "reasons": reasons[:6]}


def _agent_view(run: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [run["tasks"][i] for i in run["task_order"]]
    out = []
    priority = {"running": 0, "review": 1, "blocked": 2, "failed": 3, "queued": 4, "done": 5}
    for meta in AGENTS:
        mine = [t for t in tasks if t["agent"] == meta["key"]]
        current = [t for t in mine if t["status"] != "done"]
        cur = None
        if current:
            best = min(priority[t["status"]] for t in current)
            cur = max((t for t in current if priority[t["status"]] == best), key=lambda t: t["updated"])
        done = [t for t in mine if t["status"] == "done"]
        busy_ms = 0
        for t in mine:
            s, e = parse_ts(t["started"]), parse_ts(t["ended"] or run["ended"] or run["updated"])
            if s and e and e > s:
                busy_ms += int((e - s).total_seconds() * 1000)
        status = cur["status"] if cur else ("done" if done else "idle")
        view = {**meta, "status": status, "task_id": cur["id"] if cur else None,
                "task_title": cur["title"] if cur else (done[-1]["title"] if done else ""),
                "since": (cur["started"] or cur["updated"]) if cur else (done[-1]["ended"] if done else None),
                "done": len(done), "total": len(mine), "busy_ms": busy_ms,
                "artifacts": sum(1 for a in run["artifacts"] if a["agent"] == meta["key"]),
                "findings": sum(1 for f in run["findings"].values() if f["agent"] == meta["key"])}
        if meta["key"] == "coordinator" and not cur:
            stage = run["current_stage"]
            view["status"] = "running" if run["status"] == "active" else ("done" if run["status"] == "done" else "idle")
            view["task_title"] = (f"Conduzindo: {STAGE_LABEL[stage]}" if run["status"] == "active" and stage else
                                  "Aguardando" if run["status"] == "active" else (run["summary"] or "Missão encerrada"))
            view["since"] = run["stages"][stage]["started"] if stage else run["started"]
        out.append(view)
    return out


def _attention(run: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for t in (run["tasks"][i] for i in run["task_order"]):
        if t["status"] in ("blocked", "failed"):
            out.append({"kind": "task", "id": t["id"], "status": t["status"], "agent": t["agent"],
                        "text": t["title"] + (f" — {t['note']}" if t["note"] else "")})
    for key in run["gate_order"]:
        g = run["gates"][key]
        if g["status"] == "fail":
            out.append({"kind": "gate", "id": key, "status": "failed", "agent": "coordinator",
                        "text": f"Gate {g['label']} reprovado" + (f" ({g['value']})" if g["value"] else "")})
    for fid in run["finding_order"]:
        f = run["findings"][fid]
        if f["status"] == "aberto" and f["severity"] in ("critica", "alta"):
            out.append({"kind": "finding", "id": fid, "status": "failed", "agent": f["agent"],
                        "text": f"{SEVERITY_LABEL[f['severity']]}: {f['title']}"})
    return out


def public_run(run: dict[str, Any], feed_limit: int = 160) -> dict[str, Any]:
    tasks = [run["tasks"][i] for i in run["task_order"]]
    counts = {s: sum(1 for t in tasks if t["status"] == s) for s in TASK_STATUSES}
    stages = [run["stages"][k] for k in STAGE_KEYS]
    done_stages = sum(1 for s in stages if s["status"] in ("done", "skipped"))
    running = 0.5 if any(s["status"] == "running" for s in stages) else 0
    progress = 1.0 if run["status"] == "done" else round((done_stages + running) / len(stages), 3)
    status_of = {t["id"]: t["status"] for t in tasks}
    pub_tasks = []
    for t in tasks:
        item = {k: v for k, v in t.items() if k != "hook_id"}
        item["waiting_on"] = [d for d in t.get("after", []) if status_of.get(d) != "done"]
        pub_tasks.append(item)
    findings = [run["findings"][i] for i in run["finding_order"]]
    sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (f["status"] != "aberto", sev_rank[f["severity"]], f["created"]))
    fcount = {s: sum(1 for f in findings if f["severity"] == s and f["status"] == "aberto") for s in SEVERITIES}
    gate_rank = {k: i for i, (k, _) in enumerate(GATES)}
    gates = sorted((run["gates"][k] for k in run["gate_order"]), key=lambda g: gate_rank.get(g["key"], 99))
    agents = _agent_view(run)
    return {
        **{k: run[k] for k in ("id", "title", "mode", "mode_label", "project", "host", "platforms", "stack", "status",
                               "started", "ended", "summary", "current_stage", "updated")},
        "stages": stages,
        "tasks": pub_tasks,
        "agents": agents,
        "feed": run["feed"][-feed_limit:][::-1],
        "counts": counts,
        "progress": progress,
        "artifacts": run["artifacts"][::-1],
        "decisions": run["decisions"],
        "gates": gates,
        "findings": findings,
        "finding_counts": {**fcount, "fixed": sum(1 for f in findings if f["status"] == "corrigido"),
                           "accepted": sum(1 for f in findings if f["status"] == "aceito"),
                           "total": len(findings)},
        "health": health(run),
        "attention": _attention(run),
        "squads": [{**s, "active": sum(1 for a in agents if a["squad"] == s["key"] and a["status"] in ("running", "review")),
                    "involved": sum(1 for a in agents if a["squad"] == s["key"] and a["total"])} for s in SQUADS],
        "involved": sum(1 for a in agents if a["key"] != "coordinator" and a["total"]),
    }


def summary_run(run: dict[str, Any]) -> dict[str, Any]:
    pub = public_run(run, feed_limit=0)
    out = {k: pub[k] for k in ("id", "title", "mode", "mode_label", "project", "host", "platforms", "status", "started",
                               "ended", "counts", "progress", "updated", "summary", "involved")}
    out["health"] = pub["health"]["score"]
    out["artifacts"] = len(pub["artifacts"])
    out["findings"] = pub["finding_counts"]["total"]
    return out


def stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    finished = [r for r in runs if r["status"] != "active"]
    done = [r for r in finished if r["status"] == "done"]
    durations = []
    for r in finished:
        s, e = parse_ts(r["started"]), parse_ts(r["ended"])
        if s and e:
            durations.append((e - s).total_seconds())
    agent_tasks: dict[str, int] = {}
    tasks_done = 0
    for r in runs:
        for t in r["tasks"].values():
            agent_tasks[t["agent"]] = agent_tasks.get(t["agent"], 0) + 1
            tasks_done += t["status"] == "done"
    return {
        "runs": len(runs), "active": sum(1 for r in runs if r["status"] == "active"), "done": len(done),
        "success_rate": round(len(done) / len(finished), 3) if finished else None,
        "avg_duration_s": round(sum(durations) / len(durations)) if durations else None,
        "tasks_done": tasks_done,
        "by_mode": {m: sum(1 for r in runs if r["mode"] == m) for m in MODES},
        "top_agents": sorted(([k, v] for k, v in agent_tasks.items() if k != "coordinator"), key=lambda x: -x[1])[:8],
        "artifacts": sum(len(r["artifacts"]) for r in runs),
        "findings_fixed": sum(1 for r in runs for f in r["findings"].values() if f["status"] == "corrigido"),
    }


def build_state(events: list[dict[str, Any]] | None = None, run_id: str | None = None,
                now: datetime | None = None) -> dict[str, Any]:
    events = read_events() if events is None else events
    runs = fold(events)
    ordered = sorted(runs.values(), key=lambda r: r["started"], reverse=True)
    selected = None
    if run_id and run_id in runs:
        selected = runs[run_id]
    elif ordered:
        active = [r for r in ordered if r["status"] == "active"]
        selected = max(active, key=lambda r: r["updated"]) if active else ordered[0]
    return {
        "app": APP, "schema": SCHEMA, "now": iso(now or utc_now()),
        "agents_meta": AGENTS, "squads_meta": SQUADS,
        "stages_meta": [{"key": k, "label": label} for k, label in STAGES],
        "gates_meta": [{"key": k, "label": label} for k, label in GATES],
        "kinds": ARTIFACT_KINDS, "modes": MODES, "severities": SEVERITY_LABEL,
        "runs": [summary_run(r) for r in ordered[:60]],
        "stats": stats(list(runs.values())),
        "run": public_run(selected) if selected else None,
    }


# ---------------------------------------------------------------- relatório

def report_markdown(state: dict[str, Any]) -> str:
    run = state.get("run")
    if not run:
        return "# Master Develops\n\nNenhuma missão registrada ainda.\n"
    name = {a["key"]: a["name"] for a in state["agents_meta"]}
    status = {"active": "Em andamento", "done": "Concluída", "failed": "Falhou", "cancelled": "Cancelada"}
    tstatus = {"queued": "Na fila", "running": "Em execução", "review": "Em revisão", "done": "Concluída",
               "blocked": "Bloqueada", "failed": "Falhou"}
    gstatus = {"pass": "✅ aprovado", "fail": "❌ reprovado", "warn": "⚠️ avisos", "skip": "— não se aplica",
               "running": "⏳ em execução"}
    s, e = parse_ts(run["started"]), parse_ts(run["ended"] or state["now"])
    mins = int((e - s).total_seconds() // 60) if s and e else 0
    h = run["health"]
    lines = [
        f"# {run['title']}", "",
        f"- **Modo:** {run['mode_label']}  ",
        f"- **Status:** {status.get(run['status'], run['status'])} · progresso {int(run['progress'] * 100)}%  ",
        f"- **Saúde:** {h['score']}/100 ({h['label']})  ",
    ]
    if run["project"]:
        lines.append(f"- **Projeto:** {run['project']}  ")
    if run["platforms"]:
        lines.append(f"- **Plataformas:** {', '.join(run['platforms'])}  ")
    if run["stack"]:
        lines.append(f"- **Stack:** {run['stack']}  ")
    lines += [f"- **Início:** {run['started']} · **Duração:** {mins // 60}h{mins % 60:02d}min  ",
              f"- **Especialistas envolvidos:** {run['involved']}", ""]
    if run["summary"]:
        lines += ["## Resultado", "", run["summary"], ""]
    lines += ["## Etapas", "", "| Etapa | Status | Nota |", "|---|---|---|"]
    sl = {"done": "concluída", "running": "em andamento", "pending": "pendente", "failed": "interrompida",
          "skipped": "não se aplicou"}
    for st in run["stages"]:
        lines.append(f"| {st['label']} | {sl.get(st['status'], st['status'])} | {st['note']} |")
    lines += ["", "## Tarefas", "", "| ID | Agente | Tarefa | Status | Nota |", "|---|---|---|---|---|"]
    for t in run["tasks"]:
        lines.append(f"| {t['id']} | {name.get(t['agent'], t['agent'])} | {t['title']} | {tstatus[t['status']]} | {t['note']} |")
    if run["gates"]:
        lines += ["", "## Gates de qualidade", "", "| Gate | Resultado | Valor | Nota |", "|---|---|---|---|"]
        for g in run["gates"]:
            lines.append(f"| {g['label']} | {gstatus[g['status']]} | {g['value']} | {g['note']} |")
    if run["findings"]:
        lines += ["", "## Achados de revisão", "", "| ID | Severidade | Achado | Onde | Status |", "|---|---|---|---|---|"]
        for f in run["findings"]:
            lines.append(f"| {f['id']} | {SEVERITY_LABEL[f['severity']]} | {f['title']} | {f['where']} | {f['status']} |")
    if run["decisions"]:
        lines += ["", "## Decisões (ADRs)", ""]
        lines += [f"- **{d['id']}** — {d['title']} ({name.get(d['agent'], d['agent'])})" for d in run["decisions"]]
    if run["artifacts"]:
        lines += ["", "## Entregáveis", ""]
        lines += [f"- `{a['name']}` — {ARTIFACT_KINDS.get(a['kind'], a['kind'])}, {name.get(a['agent'], a['agent'])}"
                  for a in reversed(run["artifacts"])]
    if h["reasons"]:
        lines += ["", "## Pontos de atenção", ""] + [f"- {r}" for r in h["reasons"]]
    lines += ["", f"_Relatório gerado pelo painel Master Develops em {state['now']}._", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- hooks do Claude Code

def handle_hook(raw: str) -> None:
    """Recebe o JSON de PreToolUse/PostToolUse (ferramenta Task/Agent). Nunca falha."""
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return
    if data.get("tool_name") not in ("Task", "Agent"):
        return
    tool_input = data.get("tool_input") or {}
    agent = norm_agent(tool_input.get("subagent_type"))
    if agent not in AGENT_KEYS or agent == "coordinator":
        return
    event_name = data.get("hook_event_name", "")
    if event_name not in ("PreToolUse", "PostToolUse"):
        return
    desc = clean(tool_input.get("description") or "Tarefa delegada", 160)
    hook_id = data.get("tool_use_id") or hashlib.sha256(
        f"{data.get('session_id')}|{agent}|{desc}".encode("utf-8")).hexdigest()[:16]
    events = read_events()
    rid = active_run_id(events)
    if not rid:
        if event_name != "PreToolUse":
            return
        now = utc_now()
        rid = new_run_id(now)
        cwd = data.get("cwd") or ""
        append({"type": "run.start", "run": rid, "mode": "livre", "title": "Sessão sem missão declarada",
                "project": clean(Path(cwd).name if cwd else "", 80), "host": "claude"}, now)
    status = "running" if event_name == "PreToolUse" else "done"
    response = data.get("tool_response")
    if status == "done" and isinstance(response, dict) and response.get("is_error"):
        status = "failed"
    append({"type": "task", "run": rid, "agent": agent, "status": status, "title": desc,
            "source": "hook", "hook_id": hook_id})


# ---------------------------------------------------------------- servidor

class BoardHandler(BaseHTTPRequestHandler):
    server_version = "MasterDevelopsBoard/1"

    def log_message(self, fmt: str, *args: Any) -> None:  # silencioso
        return

    def handle(self) -> None:
        try:
            super().handle()
        except (ConnectionError, TimeoutError):  # navegador fechou a aba no meio da conversa
            pass

    def _cors(self) -> None:
        # Só o próprio painel (mesma origem) ou o arquivo local (origem "null") podem ler a API.
        if self.headers.get("Origin") == "null":
            self.send_header("Access-Control-Allow-Origin", "null")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, code: int = 200) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        run = (qs.get("run") or [None])[0]
        if url.path in ("/", "/index.html", "/painel"):
            html = render_panel({"mode": "live"})
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                       {"Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"})
        elif url.path == "/api/health":
            self._json({"app": APP, "ok": True, "pid": os.getpid()})
        elif url.path == "/api/state":
            self._json(build_state(run_id=run))
        elif url.path == "/api/demo":
            self._json(demo_frames())
        elif url.path == "/api/report.md":
            state = build_state(run_id=run)
            name = (state["run"]["id"] if state["run"] else "missao") + ".md"
            self._send(200, report_markdown(state).encode("utf-8"), "text/markdown; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="relatorio-{name}"'})
        elif url.path == "/api/stream":
            self._stream(run)
        else:
            self._json({"error": "não encontrado"}, 404)

    def _stream(self, run: str | None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()
        last_sig = None
        last_sent = 0.0
        path = events_file()
        try:
            while True:
                try:
                    st = path.stat()
                    sig = (st.st_mtime_ns, st.st_size)
                except FileNotFoundError:
                    sig = None
                now = time.monotonic()
                if sig != last_sig or now - last_sent > 10:
                    payload = json.dumps(build_state(run_id=run), ensure_ascii=False)
                    self.wfile.write(f"event: state\ndata: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_sig, last_sent = sig, now
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return


def render_panel(config: dict[str, Any]) -> str:
    html = PANEL_FILE.read_text(encoding="utf-8")
    blob = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    return html.replace("/*__MASTERDEV_CONFIG__*/null", blob, 1)


def is_up(port: int, timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == APP
    except Exception:  # noqa: BLE001
        return False


def known_port() -> int:
    env = os.environ.get("MASTERDEV_BOARD_PORT")
    if env and env.isdigit():
        return int(env)
    try:
        return int(json.loads(server_file().read_text(encoding="utf-8")).get("port", DEFAULT_PORT))
    except Exception:  # noqa: BLE001
        return DEFAULT_PORT


def serve(port: int, open_browser: bool) -> int:
    httpd = None
    for candidate in range(port, port + 10):
        if is_up(candidate, 0.3):
            print(f"Painel já está no ar: http://127.0.0.1:{candidate}")
            if open_browser:
                webbrowser.open(f"http://127.0.0.1:{candidate}")
            return 0
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), BoardHandler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        print("Não encontrei uma porta livre para o painel.", file=sys.stderr)
        return 1
    httpd.daemon_threads = True
    server_file().write_text(json.dumps({"port": port, "pid": os.getpid(), "started": iso(utc_now())}),
                             encoding="utf-8")
    url = f"http://127.0.0.1:{port}"
    print(f"Painel de produção no ar: {url}  (Ctrl+C para parar)", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def ensure(open_browser: bool, port: int | None = None) -> int:
    port = port or known_port()
    if is_up(port):
        url = f"http://127.0.0.1:{port}"
    else:
        log = open(board_dir() / "server.log", "a", encoding="utf-8")
        cmd = [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(port)]
        kwargs: dict[str, Any] = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL, "close_fds": True}
        if os.name == "nt":
            pyw = Path(sys.executable).with_name("pythonw.exe")
            if pyw.exists():
                cmd[0] = str(pyw)
            kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)  # noqa: S603
        deadline = time.time() + 8
        url = None
        while time.time() < deadline:
            time.sleep(0.25)
            p = known_port()
            if is_up(p, 0.4):
                url = f"http://127.0.0.1:{p}"
                break
        if not url:
            print("O painel não respondeu. Veja " + str(board_dir() / "server.log"), file=sys.stderr)
            return 1
    print(f"Painel de produção: {url}")
    if open_browser:
        webbrowser.open(url)
    return 0


def stop() -> int:
    try:
        info = json.loads(server_file().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print("Painel não está registrado como em execução.")
        return 0
    port, pid = info.get("port", DEFAULT_PORT), info.get("pid")
    if pid and is_up(port):
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError as exc:
            print(f"Não consegui parar o processo {pid}: {exc}", file=sys.stderr)
            return 1
    server_file().unlink(missing_ok=True)
    print("Painel parado.")
    return 0


# ---------------------------------------------------------------- demonstração (dados fictícios)

DEMO_SCRIPT: list[tuple[int, dict[str, Any]]] = [
    (0, {"type": "run.start", "mode": "construir", "title": "App de agendamento para clínicas (web + mobile)",
         "project": "agenda-clinica", "host": "claude", "platforms": ["web", "ios", "android"],
         "stack": "Next.js · Expo · PostgreSQL"}),
    (6, {"type": "stage", "stage": "descoberta"}),
    (8, {"type": "task", "task": "T1", "agent": "product-manager", "status": "running",
         "title": "Problema, MVP e critérios de aceite"}),
    (9, {"type": "task", "task": "T2", "agent": "ux-ui-designer", "status": "queued",
         "title": "Jornada de agendamento e telas", "after": ["T1"]}),
    (10, {"type": "task", "task": "T3", "agent": "data-engineer", "status": "running",
          "title": "Mapear os dados do app e o plano de eventos"}),
    (22, {"type": "note", "agent": "coordinator", "text": "3 memórias do projeto recuperadas (convenções de pastas e de testes)"}),
    (36, {"type": "task", "task": "T1", "status": "done", "note": "MVP: agendar, remarcar e lembrete; pagamento fica fora"}),
    (38, {"type": "task", "task": "T2", "status": "running"}),
    (52, {"type": "task", "task": "T3", "status": "done", "note": "9 entidades, 14 eventos, 3 dados pessoais classificados"}),
    (53, {"type": "artifact", "name": "docs/dicionario-de-dados.md", "kind": "dados", "agent": "data-engineer", "task": "T3"}),
    (55, {"type": "stage", "stage": "arquitetura"}),
    (56, {"type": "task", "task": "T4", "agent": "software-architect", "status": "running",
          "title": "Stack, módulos e contratos da API"}),
    (58, {"type": "task", "task": "T5", "agent": "database-engineer", "status": "queued",
          "title": "Esquema e migrations iniciais", "after": ["T4"]}),
    (60, {"type": "task", "task": "T6", "agent": "security-engineer", "status": "running",
          "title": "Modelagem de ameaças e LGPD"}),
    (80, {"type": "decision", "decision": "ADR-1", "title": "Monólito modular em Next.js com API REST",
          "agent": "software-architect"}),
    (84, {"type": "decision", "decision": "ADR-2", "title": "Expo (React Native) para iOS e Android",
          "agent": "software-architect"}),
    (90, {"type": "task", "task": "T2", "status": "done", "note": "11 telas, 5 estados cada; tokens claro/escuro"}),
    (92, {"type": "artifact", "name": "docs/telas-e-estados.md", "kind": "design", "agent": "ux-ui-designer", "task": "T2"}),
    (95, {"type": "task", "task": "T4", "status": "done", "note": "OpenAPI com 18 rotas"}),
    (96, {"type": "artifact", "name": "docs/api/openapi.yaml", "kind": "doc", "agent": "software-architect", "task": "T4"}),
    (97, {"type": "task", "task": "T5", "status": "running"}),
    (100, {"type": "task", "task": "T6", "status": "done", "note": "7 ameaças mapeadas; consentimento para lembretes"}),
    (104, {"type": "stage", "stage": "plano", "note": "12 tarefas, 11 especialistas"}),
    (106, {"type": "task", "task": "T7", "agent": "backend-engineer", "status": "queued",
           "title": "API de agenda, profissionais e pacientes", "after": ["T5"]}),
    (107, {"type": "task", "task": "T8", "agent": "frontend-engineer", "status": "queued",
           "title": "Painel web da clínica", "after": ["T4"]}),
    (108, {"type": "task", "task": "T9", "agent": "mobile-engineer", "status": "queued",
           "title": "App do paciente (Expo)", "after": ["T4"]}),
    (109, {"type": "task", "task": "T10", "agent": "devops-sre-engineer", "status": "queued",
           "title": "CI, ambientes e deploy de preview"}),
    (110, {"type": "task", "task": "T11", "agent": "data-scientist", "status": "queued",
           "title": "Faltas (no-show): métrica e linha de base"}),
    (112, {"type": "stage", "stage": "construcao"}),
    (114, {"type": "task", "task": "T8", "status": "running"}),
    (115, {"type": "task", "task": "T9", "status": "running"}),
    (116, {"type": "task", "task": "T10", "status": "running"}),
    (125, {"type": "task", "task": "T5", "status": "done", "note": "6 tabelas, 2 índices compostos, migrations reversíveis"}),
    (126, {"type": "artifact", "name": "db/migrations/001_init.sql", "kind": "dados", "agent": "database-engineer", "task": "T5"}),
    (127, {"type": "task", "task": "T7", "status": "running"}),
    (150, {"type": "task", "task": "T10", "status": "done", "note": "GitHub Actions: build, lint e testes; preview por PR"}),
    (151, {"type": "artifact", "name": ".github/workflows/ci.yml", "kind": "infra", "agent": "devops-sre-engineer", "task": "T10"}),
    (152, {"type": "gate", "gate": "build", "status": "pass", "agent": "devops-sre-engineer"}),
    (160, {"type": "task", "task": "T11", "status": "running"}),
    (175, {"type": "task", "task": "T9", "status": "blocked", "note": "aguardando: login por SMS ou por e-mail?"}),
    (178, {"type": "note", "agent": "coordinator", "text": "Pergunta ao operador: o paciente entra com SMS ou e-mail?"}),
    (196, {"type": "task", "task": "T9", "status": "running", "note": "operador confirmou: e-mail com link mágico"}),
    (210, {"type": "task", "task": "T7", "status": "review", "note": "18 rotas; agendamento idempotente"}),
    (212, {"type": "artifact", "name": "src/api/agenda/route.ts", "kind": "codigo", "agent": "backend-engineer", "task": "T7"}),
    (220, {"type": "task", "task": "T8", "status": "done", "note": "agenda semanal, filtros e estados vazios"}),
    (221, {"type": "artifact", "name": "apps/web/app/agenda/page.tsx", "kind": "codigo", "agent": "frontend-engineer", "task": "T8"}),
    (230, {"type": "task", "task": "T11", "status": "done", "note": "lembrete 24h antes supera o modelo; ML adiado"}),
    (238, {"type": "task", "task": "T7", "status": "done"}),
    (250, {"type": "task", "task": "T9", "status": "done", "note": "agendar, remarcar e notificações push"}),
    (251, {"type": "artifact", "name": "apps/mobile/app/(tabs)/agenda.tsx", "kind": "codigo", "agent": "mobile-engineer", "task": "T9"}),
    (252, {"type": "stage", "stage": "qualidade"}),
    (254, {"type": "task", "task": "T12", "agent": "qa-test-engineer", "status": "running",
           "title": "Testes de unidade, API e E2E dos fluxos críticos"}),
    (256, {"type": "task", "task": "T13", "agent": "performance-engineer", "status": "running",
           "title": "Web Vitals e tempo de resposta da agenda"}),
    (258, {"type": "gate", "gate": "lint", "status": "pass"}),
    (259, {"type": "gate", "gate": "tipos", "status": "pass"}),
    (270, {"type": "gate", "gate": "testes", "status": "running", "agent": "qa-test-engineer"}),
    (290, {"type": "gate", "gate": "testes", "status": "fail", "value": "131/134", "agent": "qa-test-engineer",
           "note": "3 falhas de fuso horário"}),
    (296, {"type": "task", "task": "T14", "agent": "backend-engineer", "status": "running",
           "title": "Corrigir fuso horário no agendamento", "after": ["T12"]}),
    (316, {"type": "task", "task": "T14", "status": "done", "note": "datas em UTC + fuso da clínica; teste de regressão"}),
    (320, {"type": "gate", "gate": "testes", "status": "pass", "value": "134/134", "agent": "qa-test-engineer"}),
    (322, {"type": "gate", "gate": "e2e", "status": "pass", "value": "12/12", "agent": "qa-test-engineer"}),
    (323, {"type": "artifact", "name": "e2e/agendamento.spec.ts", "kind": "teste", "agent": "qa-test-engineer", "task": "T12"}),
    (326, {"type": "task", "task": "T13", "status": "done", "note": "LCP 1,8 s; p95 da API 120 ms"}),
    (327, {"type": "gate", "gate": "performance", "status": "pass", "value": "LCP 1,8 s", "agent": "performance-engineer"}),
    (330, {"type": "gate", "gate": "acessibilidade", "status": "warn", "value": "2 avisos",
           "note": "contraste em 2 botões secundários"}),
    (332, {"type": "task", "task": "T12", "status": "done", "note": "146 testes automatizados"}),
    (334, {"type": "gate", "gate": "seguranca", "status": "pass", "value": "0 altas", "agent": "security-engineer"}),
    (336, {"type": "stage", "stage": "revisao"}),
    (338, {"type": "task", "task": "T15", "agent": "code-correctness-reviewer", "status": "running",
           "title": "Revisão independente: agenda, auth e migrations"}),
    (339, {"type": "task", "task": "T16", "agent": "code-maintainability-reviewer", "status": "running",
           "title": "Revisão de simplicidade e organização"}),
    (356, {"type": "finding", "finding": "F1", "severity": "alta", "agent": "code-correctness-reviewer",
           "title": "Remarcação não confere se o horário ainda está livre", "where": "src/api/agenda/remarcar.ts:41"}),
    (362, {"type": "finding", "finding": "F2", "severity": "media", "agent": "code-maintainability-reviewer",
           "title": "Dois clientes HTTP duplicados no app", "where": "apps/mobile/lib/api.ts:12"}),
    (366, {"type": "finding", "finding": "F3", "severity": "baixa", "agent": "code-maintainability-reviewer",
           "title": "Nome genérico 'data' em 6 funções utilitárias", "where": "src/lib/datas.ts"}),
    (370, {"type": "task", "task": "T16", "status": "done", "note": "3 achados"}),
    (372, {"type": "task", "task": "T17", "agent": "backend-engineer", "status": "running",
           "title": "Corrigir F1 com transação e restrição única", "after": ["T15"]}),
    (386, {"type": "task", "task": "T17", "status": "done", "note": "teste de concorrência adicionado"}),
    (387, {"type": "finding", "finding": "F1", "status": "corrigido", "agent": "backend-engineer"}),
    (388, {"type": "finding", "finding": "F2", "status": "corrigido", "agent": "mobile-engineer"}),
    (390, {"type": "task", "task": "T15", "status": "done", "note": "1 achado alto, corrigido e coberto por teste"}),
    (394, {"type": "stage", "stage": "entrega"}),
    (396, {"type": "task", "task": "T18", "agent": "technical-writer", "status": "running",
           "title": "README, guia de implantação e changelog"}),
    (412, {"type": "task", "task": "T18", "status": "done"}),
    (413, {"type": "artifact", "name": "README.md", "kind": "doc", "agent": "technical-writer", "task": "T18"}),
    (418, {"type": "run.end", "status": "done", "summary": "Web + app mobile, 18 rotas, 146 testes passando, 2 ADRs"}),
]


def demo_events(stop_at: float = 1.0, base: datetime | None = None, run_id: str | None = None,
                scale: float = 1.0) -> list[dict[str, Any]]:
    total = DEMO_SCRIPT[-1][0]
    limit = total * stop_at
    base = base or utc_now() - timedelta(seconds=int(limit * scale))
    rid = run_id or new_run_id(base)
    out = []
    for offset, ev in DEMO_SCRIPT:
        if offset > limit:
            break
        out.append({"v": SCHEMA, "ts": iso(base + timedelta(seconds=offset * scale)), "run": rid, **ev})
    return out


def demo_frames(count: int = 24) -> list[dict[str, Any]]:
    """Estados prontos de uma missão simulada (o painel usa quando está sem servidor)."""
    base = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
    full = demo_events(1.0, base=base, run_id="demo", scale=6)
    total = DEMO_SCRIPT[-1][0] * 6
    frames = []
    for i in range(1, count + 1):
        cut = base + timedelta(seconds=total * i / count)
        evs = [e for e in full if parse_ts(e["ts"]) <= cut]
        frames.append(build_state(evs, now=cut))
    return frames


def run_demo(live: bool, speed: float) -> int:
    if not live:
        with open(events_file(), "a", encoding="utf-8") as fh:
            for ev in demo_events(0.62):
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        print("Missão de demonstração registrada (parada na etapa de qualidade). Abra o painel para ver.")
        return 0
    rid = new_run_id(utc_now())
    print("Reproduzindo uma missão simulada no painel (Ctrl+C para interromper)...", flush=True)
    last = 0
    try:
        for offset, ev in DEMO_SCRIPT:
            time.sleep(max(0.0, (offset - last) / max(speed, 0.1)))
            last = offset
            append({"run": rid, **ev})
            label = ev.get("task") or ev.get("stage") or ev.get("gate") or ev.get("finding") or ev.get("decision") or ""
            print(f"  {ev['type']:<9} {label} {ev.get('status', '')}", flush=True)
    except KeyboardInterrupt:
        append({"type": "run.end", "run": rid, "status": "cancelled", "summary": "demonstração interrompida"})
    return 0


# ---------------------------------------------------------------- exportação estática

def export_html(dest: Path, port: int | None = None) -> Path:
    """Gera o painel como arquivo único: vai para o servidor local se estiver no ar; senão, foto + demonstração."""
    cfg = {"mode": "file", "server": f"http://127.0.0.1:{port or known_port()}", "demo": demo_frames(),
           "snapshot": build_state()}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_panel(cfg), encoding="utf-8")
    return dest


def prune(keep: int) -> int:
    events = read_events()
    runs = fold(events)
    ordered = sorted(runs.values(), key=lambda r: r["started"], reverse=True)
    keep_ids = {r["id"] for r in ordered[:keep]} | {r["id"] for r in ordered if r["status"] == "active"}
    kept = [e for e in events if e.get("run") in keep_ids]
    tmp = events_file().with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept), encoding="utf-8")
    os.replace(tmp, events_file())
    print(f"Mantidas {len(keep_ids)} missões; {len(events) - len(kept)} eventos removidos.")
    return 0


def auto_prune() -> None:
    try:
        if events_file().stat().st_size > MAX_EVENTS_BYTES:
            prune(40)
    except OSError:
        pass


# ---------------------------------------------------------------- CLI

def _csv(raw: str) -> list[str]:
    return [clean(p, 24) for p in re.split(r"[,\s]+", raw or "") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="team_board.py", description="Painel de produção da equipe Master Develops")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="Inicia uma missão (uma ativação da equipe).")
    p.add_argument("--mode", required=True, help="construir | evoluir | revisar | depurar")
    p.add_argument("--title", required=True)
    p.add_argument("--project", default="", help="nome ou pasta do projeto (só o nome é guardado)")
    p.add_argument("--host", default="", help="claude | codex")
    p.add_argument("--platforms", default="", help="ex.: web,ios,android,desktop,api")
    p.add_argument("--stack", default="", help="stack principal, em poucas palavras")

    p = sub.add_parser("stage", help="Marca a etapa atual da missão.")
    p.add_argument("stage", help=", ".join(STAGE_KEYS))
    p.add_argument("--done", action="store_true", help="marca a etapa como concluída sem abrir a próxima")
    p.add_argument("--note", default="")
    p.add_argument("--run")

    p = sub.add_parser("task", help="Cria ou atualiza a tarefa de um agente.")
    p.add_argument("task_id", help="identificador curto, ex.: T1")
    p.add_argument("--agent", help="ex.: backend-engineer (ou coordinator)")
    p.add_argument("--status", default="running", help=", ".join(TASK_STATUSES))
    p.add_argument("--title", default="")
    p.add_argument("--note", default="")
    p.add_argument("--after", default="", help="dependências, ex.: T1,T2")
    p.add_argument("--run")

    p = sub.add_parser("artifact", help="Registra um entregável (arquivo, documento, design...).")
    p.add_argument("name", help="caminho relativo ou nome do entregável")
    p.add_argument("--kind", default="codigo", help=", ".join(ARTIFACT_KINDS))
    p.add_argument("--agent", default="coordinator")
    p.add_argument("--task", default="")
    p.add_argument("--note", default="")
    p.add_argument("--run")

    p = sub.add_parser("gate", help="Registra o resultado de uma verificação (build, testes, lint...).")
    p.add_argument("gate", help=", ".join(GATE_LABEL))
    p.add_argument("--status", required=True, help=", ".join(GATE_STATUSES))
    p.add_argument("--value", default="", help="ex.: 134/134, 87%%, LCP 1,8 s")
    p.add_argument("--agent", default="coordinator")
    p.add_argument("--note", default="")
    p.add_argument("--run")

    p = sub.add_parser("finding", help="Registra ou atualiza um achado de revisão.")
    p.add_argument("finding_id", help="identificador curto, ex.: F1")
    p.add_argument("--severity", default="", help=", ".join(SEVERITIES))
    p.add_argument("--title", default="")
    p.add_argument("--where", default="", help="arquivo:linha")
    p.add_argument("--status", default="", help=", ".join(FINDING_STATUSES))
    p.add_argument("--agent", default="")
    p.add_argument("--note", default="")
    p.add_argument("--run")

    p = sub.add_parser("decision", help="Registra uma decisão de arquitetura (ADR).")
    p.add_argument("decision_id", help="ex.: ADR-1")
    p.add_argument("--title", required=True)
    p.add_argument("--agent", default="software-architect")
    p.add_argument("--note", default="")
    p.add_argument("--run")

    p = sub.add_parser("note", help="Registra um aviso no feed da missão.")
    p.add_argument("text")
    p.add_argument("--agent", default="coordinator")
    p.add_argument("--run")

    p = sub.add_parser("finish", help="Encerra a missão.")
    p.add_argument("--status", default="done", choices=["done", "failed", "cancelled"])
    p.add_argument("--summary", default="")
    p.add_argument("--run")

    p = sub.add_parser("hook", help="Entrada para os hooks do Claude Code (lê JSON do stdin).")
    p.add_argument("--app", default="masterdev", help="marcador do instalador (ignorado)")
    p = sub.add_parser("serve", help="Sobe o painel em primeiro plano.")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--open", action="store_true")
    p = sub.add_parser("ensure", help="Garante o painel no ar (em segundo plano) e mostra o endereço.")
    p.add_argument("--open", action="store_true")
    p.add_argument("--port", type=int, default=None)
    sub.add_parser("stop", help="Para o painel em segundo plano.")
    p = sub.add_parser("status", help="Mostra a missão ativa em texto.")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("report", help="Relatório da missão em Markdown.")
    p.add_argument("dest", nargs="?", default=None, help="arquivo de saída (padrão: imprime na tela)")
    p.add_argument("--run")
    p = sub.add_parser("demo", help="Registra uma missão simulada.")
    p.add_argument("--live", action="store_true", help="reproduz ao vivo, evento a evento")
    p.add_argument("--speed", type=float, default=4.0, help="velocidade da reprodução ao vivo (padrão 4x)")
    p = sub.add_parser("export", help="Gera o painel como um arquivo HTML único.")
    p.add_argument("dest", nargs="?", default=None)
    p = sub.add_parser("prune", help="Mantém só as missões mais recentes.")
    p.add_argument("--keep", type=int, default=30)

    args = ap.parse_args(argv)

    if args.cmd == "hook":
        try:
            handle_hook(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001  hook nunca pode atrapalhar o agente
            pass
        return 0

    try:
        if args.cmd == "start":
            auto_prune()
            now = utc_now()
            rid = new_run_id(now)
            project = args.project
            if project and (os.sep in project or "/" in project):
                project = Path(project).name
            host = args.host.strip().lower()
            if not host:
                host = "codex" if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_SANDBOX") else "claude"
            ev = {"type": "run.start", "run": rid, "mode": norm_mode(args.mode), "title": clean(args.title, 160),
                  "project": clean(project, 80), "host": clean(host, 20)}
            if args.platforms:
                ev["platforms"] = [p.lower() for p in _csv(args.platforms)][:8]
            if args.stack:
                ev["stack"] = clean(args.stack, 80)
            append(ev, now)
            print(rid)
        elif args.cmd == "stage":
            ev = {"type": "stage", "run": resolve_run(args.run), "stage": norm_stage(args.stage), "note": clean(args.note)}
            if args.done:
                ev["status"] = "done"
            append(ev)
        elif args.cmd == "task":
            ev = {"type": "task", "run": resolve_run(args.run), "task": clean(args.task_id, 24),
                  "status": norm_status(args.status), "source": "coordinator"}
            if args.agent:
                ev["agent"] = check_agent(args.agent)
            if args.title:
                ev["title"] = clean(args.title, 160)
            if args.note:
                ev["note"] = clean(args.note)
            if args.after:
                ev["after"] = _csv(args.after)
            append(ev)
        elif args.cmd == "artifact":
            ev = {"type": "artifact", "run": resolve_run(args.run), "name": short_path(args.name),
                  "kind": norm_kind(args.kind), "agent": check_agent(args.agent)}
            if args.task:
                ev["task"] = clean(args.task, 24)
            if args.note:
                ev["note"] = clean(args.note)
            append(ev)
        elif args.cmd == "gate":
            ev = {"type": "gate", "run": resolve_run(args.run), "gate": norm_gate(args.gate),
                  "status": norm_gate_status(args.status), "agent": check_agent(args.agent)}
            if args.value:
                ev["value"] = clean(args.value, 40)
            if args.note:
                ev["note"] = clean(args.note)
            append(ev)
        elif args.cmd == "finding":
            ev = {"type": "finding", "run": resolve_run(args.run), "finding": clean(args.finding_id, 24)}
            if args.severity:
                ev["severity"] = norm_severity(args.severity)
            if args.status:
                ev["status"] = norm_finding_status(args.status)
            if args.agent:
                ev["agent"] = check_agent(args.agent)
            if args.title:
                ev["title"] = clean(args.title, 160)
            if args.where:
                ev["where"] = short_path(args.where)
            if args.note:
                ev["note"] = clean(args.note)
            append(ev)
        elif args.cmd == "decision":
            append({"type": "decision", "run": resolve_run(args.run), "decision": clean(args.decision_id, 24),
                    "title": clean(args.title, 160), "agent": check_agent(args.agent), "note": clean(args.note)})
        elif args.cmd == "note":
            append({"type": "note", "run": resolve_run(args.run), "agent": norm_agent(args.agent),
                    "text": clean(args.text)})
        elif args.cmd == "finish":
            append({"type": "run.end", "run": resolve_run(args.run), "status": args.status,
                    "summary": clean(args.summary, 200)})
        elif args.cmd == "serve":
            return serve(args.port or known_port(), args.open)
        elif args.cmd == "ensure":
            return ensure(args.open, args.port)
        elif args.cmd == "stop":
            return stop()
        elif args.cmd == "status":
            state = build_state()
            if args.json:
                print(json.dumps(state["run"], ensure_ascii=False, indent=2))
                return 0
            run = state["run"]
            if not run:
                print("Nenhuma missão registrada ainda.")
                return 0
            h = run["health"]
            print(f"{run['title']}  [{run['mode_label']}]  status={run['status']}  "
                  f"progresso={int(run['progress'] * 100)}%  saúde={h['score']} ({h['label']})")
            print(f"Etapa atual: {STAGE_LABEL.get(run['current_stage'] or '', '—')}")
            for a in run["agents"]:
                if a["status"] != "idle":
                    print(f"  {a['name']:<26} {a['status']:<8} {a['task_title']}")
            for item in run["attention"]:
                print(f"  ! {item['text']}")
        elif args.cmd == "report":
            text = report_markdown(build_state(run_id=args.run))
            if args.dest:
                Path(args.dest).write_text(text, encoding="utf-8")
                print(args.dest)
            else:
                print(text)
        elif args.cmd == "demo":
            return run_demo(args.live, args.speed)
        elif args.cmd == "export":
            dest = Path(args.dest) if args.dest else app_home() / "painel.html"
            print(export_html(dest))
        elif args.cmd == "prune":
            return prune(args.keep)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
