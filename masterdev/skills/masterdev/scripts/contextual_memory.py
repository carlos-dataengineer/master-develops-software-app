#!/usr/bin/env python3
"""Local, operator-scoped contextual memory for the MasterDevelops skill.

Standard-library only. No network access, telemetry, cloud sync, or model training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1"
MAX_TITLE_CHARS = 200
MAX_CONTENT_CHARS = 12000
VALID_KINDS = {
    "preference", "architecture", "business_rule", "pattern",
    "solution", "routine", "decision", "correction",
}
VALID_SCOPES = {"operator", "project"}
VALID_STATUSES = {"candidate", "accepted", "superseded", "rejected"}
VALID_SOURCES = {"user_explicit", "user_correction", "observed_repeated", "validated_result", "agent_inference"}

# Common credential formats. This is a guardrail, not a complete DLP system.
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|password|passwd|secret|access[_-]?token|refresh[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"(?i)\bauthorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_project_root(raw: str | None = None) -> Path:
    if raw:
        root = Path(raw).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"A pasta do projeto não existe ou não é um diretório: {root}")
        return root

    cwd = Path.cwd().resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def project_identity(root: Path) -> tuple[str, str]:
    normalized = os.path.normcase(str(root.resolve())).casefold()
    key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    name = root.name or "workspace"
    return key, name[:120]


def memory_home() -> Path:
    override = os.environ.get("MASTERDEV_MEMORY_HOME")
    if override:
        return Path(override).expanduser().resolve()

    system = platform.system().lower()
    home = Path.home()
    if system == "windows":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else home / "AppData" / "Local") / "MasterDevelops" / "Memory"
    if system == "darwin":
        return home / "Library" / "Application Support" / "MasterDevelops" / "Memory"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg).expanduser() if xdg else home / ".local" / "share") / "masterdev" / "memory"


def check_memory_location(home: Path, project_root: Path) -> None:
    """Reject memory inside the active workspace to prevent accidental central commits."""
    try:
        home_resolved = home.resolve()
        project_resolved = project_root.resolve()
        home_resolved.relative_to(project_resolved)
    except ValueError:
        return
    except OSError:
        return
    if os.environ.get("MASTERDEV_ALLOW_IN_PROJECT_MEMORY") == "1":
        return
    raise ValueError(
        "O armazenamento de memória está dentro do projeto atual. Por segurança, "
        "use o diretório local do operador (padrão) ou defina "
        "MASTERDEV_ALLOW_IN_PROJECT_MEMORY=1 conscientemente."
    )


def secure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            path.chmod(0o700)
        except OSError:
            pass


def connect(project_root: Path) -> tuple[sqlite3.Connection, str, str, Path]:
    home = memory_home()
    check_memory_location(home, project_root)
    secure_directory(home)
    db_path = home / "masterdev-memory.sqlite3"
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    create_schema(conn)
    if os.name != "nt":
        try:
            db_path.chmod(0o600)
        except OSError:
            pass
    key, name = project_identity(project_root)
    conn.execute(
        "INSERT INTO projects(project_key, project_name, first_seen, last_seen) VALUES(?,?,?,?) "
        "ON CONFLICT(project_key) DO UPDATE SET project_name=excluded.project_name,last_seen=excluded.last_seen",
        (key, name, utc_now(), utc_now()),
    )
    conn.commit()
    return conn, key, name, db_path


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects (
            project_key TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK(scope IN ('operator','project')),
            project_key TEXT NULL REFERENCES projects(project_key) ON DELETE CASCADE,
            project_name TEXT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
            status TEXT NOT NULL CHECK(status IN ('candidate','accepted','superseded','rejected')),
            source TEXT NOT NULL,
            evidence_count INTEGER NOT NULL DEFAULT 1 CHECK(evidence_count >= 1),
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT NULL,
            last_verified_at TEXT NULL,
            CHECK((scope='operator' AND project_key IS NULL) OR (scope='project' AND project_key IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS idx_memories_scope_project_status
            ON memories(scope, project_key, status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
        """
    )
    conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('schema_version',?)", (SCHEMA_VERSION,))
    conn.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('operator_id',?)", (str(uuid.uuid4()),))
    conn.commit()


def reject_sensitive(text: str) -> None:
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                "O conteúdo parece conter uma credencial ou token. A memória não o armazenou. "
                "Remova segredos e tente novamente com um resumo técnico sanitizado."
            )


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    tags = sorted({part.strip().lower()[:40] for part in raw.split(",") if part.strip()})
    return tags[:20]


def memory_scope_params(scope: str, project_key: str) -> tuple[str, str | None]:
    if scope == "operator":
        return "operator", None
    if scope == "project":
        return "project", project_key
    raise ValueError("Escopo inválido. Use operator ou project.")


def cmd_status(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, key, name, db_path = connect(root)
    try:
        global_count = conn.execute("SELECT COUNT(*) FROM memories WHERE scope='operator' AND status='accepted'").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM memories WHERE scope='project' AND project_key=? AND status='accepted'", (key,)).fetchone()[0]
        candidate_count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE status='candidate' AND (scope='operator' OR project_key=?)", (key,)
        ).fetchone()[0]
        operator_id = conn.execute("SELECT value FROM metadata WHERE key='operator_id'").fetchone()[0]
        print(json.dumps({
            "status": "ready", "operator_id": operator_id[:8], "database": str(db_path),
            "project": name, "project_key": key, "operator_memories": global_count,
            "project_memories": project_count, "pending_candidates": candidate_count,
            "storage": "local_only", "network": "not_used", "schema_version": SCHEMA_VERSION,
        }, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, key, name, _ = connect(root)
    try:
        scope, project_key = memory_scope_params(args.scope, key)
        title = args.title.strip()
        content = args.content.strip()
        if not title or len(title) > MAX_TITLE_CHARS:
            raise ValueError(f"O título deve ter entre 1 e {MAX_TITLE_CHARS} caracteres.")
        if not content or len(content) > MAX_CONTENT_CHARS:
            raise ValueError(f"O conteúdo deve ter entre 1 e {MAX_CONTENT_CHARS} caracteres.")
        if args.kind not in VALID_KINDS:
            raise ValueError(f"Tipo inválido: {args.kind}")
        if args.status not in VALID_STATUSES:
            raise ValueError(f"Status inválido: {args.status}")
        if args.source not in VALID_SOURCES:
            raise ValueError(f"Origem inválida: {args.source}")
        reject_sensitive(title + "\n" + content)
        tags = parse_tags(args.tags)
        now = utc_now()
        query = "SELECT * FROM memories WHERE scope=? AND kind=? AND lower(title)=lower(?) AND "
        params: list[Any] = [scope, args.kind, title]
        if project_key is None:
            query += "project_key IS NULL ORDER BY updated_at DESC LIMIT 1"
        else:
            query += "project_key=? ORDER BY updated_at DESC LIMIT 1"
            params.append(project_key)
        existing = conn.execute(query, params).fetchone()
        if existing and existing["content"].strip().casefold() == content.casefold():
            merged_tags = sorted(set(json.loads(existing["tags_json"])) | set(tags))
            new_status = "accepted" if args.status == "accepted" else existing["status"]
            conn.execute(
                "UPDATE memories SET evidence_count=evidence_count+?, confidence=MAX(confidence,?), "
                "status=?, tags_json=?, updated_at=?, last_verified_at=CASE WHEN ?='validated_result' THEN ? ELSE last_verified_at END "
                "WHERE id=?",
                (max(1, args.evidence), args.confidence, new_status, json.dumps(merged_tags, ensure_ascii=False), now,
                 args.source, now, existing["id"]),
            )
            memory_id = existing["id"]
            action = "reinforced"
        else:
            memory_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO memories(id,scope,project_key,project_name,kind,title,content,confidence,status,source,"
                "evidence_count,tags_json,created_at,updated_at,last_verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (memory_id, scope, project_key, name if project_key else None, args.kind, title, content,
                 args.confidence, args.status, args.source, max(1, args.evidence),
                 json.dumps(tags, ensure_ascii=False), now, now, now if args.source == "validated_result" else None),
            )
            action = "created"
        conn.commit()
        print(json.dumps({"result": action, "id": memory_id, "scope": scope,
                          "project": name if project_key else None, "status": args.status}, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, key, name, _ = connect(root)
    try:
        rows = conn.execute(
            "SELECT * FROM memories WHERE status='accepted' AND (scope='operator' OR (scope='project' AND project_key=?)) "
            "ORDER BY CASE WHEN scope='project' THEN 0 ELSE 1 END, confidence DESC, evidence_count DESC, updated_at DESC",
            (key,),
        ).fetchall()
        query_terms = [t.casefold() for t in re.findall(r"[\wÀ-ÿ-]+", args.query or "") if len(t) > 2]
        scored = []
        for row in rows:
            haystack = " ".join([row["title"], row["content"], " ".join(json.loads(row["tags_json"]))]).casefold()
            score = sum(1 for term in query_terms if term in haystack)
            if not query_terms or score > 0:
                recency_boost = 0.05 if row["scope"] == "project" else 0.0
                scored.append((score + recency_boost, row))
        scored.sort(key=lambda item: (item[0], item[1]["confidence"], item[1]["evidence_count"], item[1]["updated_at"]), reverse=True)
        results = []
        for _, row in scored[:max(1, min(args.limit, 30))]:
            results.append({
                "id": row["id"], "scope": row["scope"], "project": row["project_name"],
                "kind": row["kind"], "title": row["title"], "content": row["content"],
                "confidence": row["confidence"], "evidence_count": row["evidence_count"],
                "source": row["source"], "tags": json.loads(row["tags_json"]),
                "updated_at": row["updated_at"],
            })
            conn.execute("UPDATE memories SET last_used_at=? WHERE id=?", (utc_now(), row["id"]))
        conn.commit()
        print(json.dumps({"project": name, "query": args.query or "", "memories": results}, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, key, name, _ = connect(root)
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if args.scope == "operator":
            clauses.append("scope='operator'")
        elif args.scope == "project":
            clauses.append("scope='project' AND project_key=?")
            params.append(key)
        else:
            clauses.append("(scope='operator' OR (scope='project' AND project_key=?))")
            params.append(key)
        if args.include_candidates:
            clauses.append("status IN ('accepted','candidate')")
        else:
            clauses.append("status='accepted'")
        rows = conn.execute("SELECT * FROM memories WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC", params).fetchall()
        out = [{"id": r["id"], "scope": r["scope"], "project": r["project_name"], "kind": r["kind"],
                "title": r["title"], "status": r["status"], "confidence": r["confidence"],
                "evidence_count": r["evidence_count"], "updated_at": r["updated_at"]} for r in rows]
        print(json.dumps({"project": name, "memories": out}, ensure_ascii=False, indent=2))
    finally:
        conn.close()
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, key, _, _ = connect(root)
    status = "accepted" if args.action == "confirm" else "rejected"
    try:
        cur = conn.execute(
            "UPDATE memories SET status=?, updated_at=?, last_verified_at=? WHERE id=? AND "
            "(scope='operator' OR project_key=?)",
            (status, utc_now(), utc_now() if status == "accepted" else None, args.memory_id, key),
        )
        conn.commit()
        if cur.rowcount != 1:
            print("Não encontrado na memória do operador ou do projeto atual.", file=sys.stderr)
            return 2
        print(json.dumps({"id": args.memory_id, "status": status}, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ValueError("A exclusão exige --yes para evitar remoção acidental.")
    root = resolve_project_root(args.project_root)
    conn, key, _, _ = connect(root)
    try:
        cur = conn.execute(
            "DELETE FROM memories WHERE id=? AND (scope='operator' OR project_key=?)",
            (args.memory_id, key),
        )
        conn.commit()
        if cur.rowcount != 1:
            print("Não encontrado na memória do operador ou do projeto atual.", file=sys.stderr)
            return 2
        print(json.dumps({"deleted": args.memory_id}, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def cmd_forget_project(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ValueError("A exclusão de contexto exige --yes para evitar remoção acidental.")
    root = resolve_project_root(args.project_root)
    conn, key, name, _ = connect(root)
    try:
        cur = conn.execute("DELETE FROM memories WHERE scope='project' AND project_key=?", (key,))
        conn.commit()
        print(json.dumps({"project": name, "deleted_memories": cur.rowcount}, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    conn, _, _, _ = connect(root)
    destination = Path(args.output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        rows = conn.execute("SELECT * FROM memories ORDER BY scope, project_key, updated_at").fetchall()
        data = {
            "format": "masterdev-contextual-memory-export",
            "schema_version": SCHEMA_VERSION,
            "exported_at": utc_now(),
            "note": "Exportação local solicitada pelo operador; contém conhecimento contextual. Proteja o arquivo.",
            "memories": [{
                "id": r["id"], "scope": r["scope"], "project_key": r["project_key"],
                "project_name": r["project_name"], "kind": r["kind"], "title": r["title"],
                "content": r["content"], "confidence": r["confidence"], "status": r["status"],
                "source": r["source"], "evidence_count": r["evidence_count"],
                "tags": json.loads(r["tags_json"]), "created_at": r["created_at"],
                "updated_at": r["updated_at"], "last_verified_at": r["last_verified_at"],
            } for r in rows],
        }
        destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.name != "nt":
            try:
                destination.chmod(0o600)
            except OSError:
                pass
        print(json.dumps({"exported": len(rows), "path": str(destination)}, ensure_ascii=False))
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Memória contextual local do MasterDevelops (sem rede e sem treinamento do modelo).")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_project_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--project-root", help="Raiz do projeto; por padrão usa a raiz Git ou diretório atual.")

    p = sub.add_parser("status", help="Inicializa/mostra estado do armazenamento local.")
    add_project_arg(p); p.set_defaults(func=cmd_status)

    p = sub.add_parser("remember", help="Registra uma memória contextual.")
    add_project_arg(p)
    p.add_argument("--scope", choices=sorted(VALID_SCOPES), required=True)
    p.add_argument("--kind", choices=sorted(VALID_KINDS), required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--status", choices=["candidate", "accepted"], default="candidate")
    p.add_argument("--source", choices=sorted(VALID_SOURCES), default="agent_inference")
    p.add_argument("--confidence", type=float, default=0.65)
    p.add_argument("--evidence", type=int, default=1)
    p.add_argument("--tags", default="")
    p.set_defaults(func=cmd_remember)

    p = sub.add_parser("recall", help="Recupera memórias aceitas do operador e do projeto atual.")
    add_project_arg(p); p.add_argument("--query", default=""); p.add_argument("--limit", type=int, default=8)
    p.set_defaults(func=cmd_recall)

    p = sub.add_parser("list", help="Lista memórias do operador e/ou projeto atual.")
    add_project_arg(p); p.add_argument("--scope", choices=["all", "operator", "project"], default="all")
    p.add_argument("--include-candidates", action="store_true"); p.set_defaults(func=cmd_list)

    p = sub.add_parser("confirm", help="Aprova uma memória candidata.")
    add_project_arg(p); p.add_argument("memory_id"); p.set_defaults(func=cmd_decide, action="confirm")
    p = sub.add_parser("reject", help="Rejeita uma memória candidata.")
    add_project_arg(p); p.add_argument("memory_id"); p.set_defaults(func=cmd_decide, action="reject")

    p = sub.add_parser("forget", help="Apaga uma memória específica do contexto atual.")
    add_project_arg(p); p.add_argument("memory_id"); p.add_argument("--yes", action="store_true"); p.set_defaults(func=cmd_forget)
    p = sub.add_parser("forget-project", help="Apaga todas as memórias do projeto atual, não as globais.")
    add_project_arg(p); p.add_argument("--yes", action="store_true"); p.set_defaults(func=cmd_forget_project)

    p = sub.add_parser("export", help="Exporta todas as memórias para JSON local.")
    add_project_arg(p); p.add_argument("--output", required=True); p.set_defaults(func=cmd_export)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if hasattr(args, "confidence") and not (0 <= args.confidence <= 1):
            raise ValueError("--confidence deve estar entre 0 e 1.")
        if hasattr(args, "evidence") and args.evidence < 1:
            raise ValueError("--evidence deve ser >= 1.")
        return int(args.func(args))
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
