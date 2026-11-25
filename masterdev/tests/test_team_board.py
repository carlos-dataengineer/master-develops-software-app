"""Testes do painel de produção (team_board.py). Somente biblioteca padrão."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "masterdev" / "scripts"
SCRIPT = SCRIPTS / "team_board.py"
sys.path.insert(0, str(SCRIPTS))
import team_board as tb  # noqa: E402


class BoardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.copy()
        self.env["MASTERDEV_HOME"] = self.tmp.name
        self.env.pop("MASTERDEV_RUN", None)
        self.env.pop("MASTERDEV_BOARD_HOME", None)
        self._old = os.environ.get("MASTERDEV_HOME")
        os.environ["MASTERDEV_HOME"] = self.tmp.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("MASTERDEV_HOME", None)
        else:
            os.environ["MASTERDEV_HOME"] = self._old
        self.tmp.cleanup()

    def cli(self, *args, stdin=None, expected=0):
        r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), *args], env=self.env, input=stdin,
                           capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(r.returncode, expected, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
        return r.stdout.strip()

    def events_raw(self):
        return (Path(self.tmp.name) / "board" / "events.jsonl").read_text(encoding="utf-8")


class TeamTests(unittest.TestCase):
    def test_team_has_16_specialists_in_squads(self):
        agents = [a for a in tb.AGENTS if a["key"] != "coordinator"]
        self.assertEqual(len(agents), 18)
        squads = {s["key"] for s in tb.SQUADS}
        self.assertTrue(all(a["squad"] in squads for a in agents))
        self.assertEqual(len({a["short"] for a in tb.AGENTS}), len(tb.AGENTS), "siglas repetidas")


class MissionFlowTests(BoardCase):
    def test_full_mission(self):
        rid = self.cli("start", "--mode", "construir", "--title", "App de tarefas", "--project", "/x/meu-app",
                       "--host", "claude", "--platforms", "web, ios,android", "--stack", "Next.js + Postgres")
        self.assertTrue(rid.startswith("r"))
        self.cli("stage", "descoberta")
        self.cli("task", "T1", "--agent", "product-manager", "--status", "running", "--title", "MVP")
        self.cli("task", "T2", "--agent", "ux_ui_designer", "--status", "queued", "--title", "Telas", "--after", "T1")
        run = tb.build_state()["run"]
        self.assertEqual(run["id"], rid)
        self.assertEqual(run["project"], "meu-app")  # só o nome da pasta
        self.assertEqual(run["platforms"], ["web", "ios", "android"])
        self.assertEqual(run["stack"], "Next.js + Postgres")
        agents = {a["key"]: a for a in run["agents"]}
        self.assertEqual(agents["product-manager"]["status"], "running")
        self.assertEqual(agents["ux-ui-designer"]["status"], "queued")
        self.assertEqual(agents["code-correctness-reviewer"]["status"], "idle")
        t2 = next(t for t in run["tasks"] if t["id"] == "T2")
        self.assertEqual(t2["after"], ["T1"])
        self.assertEqual(t2["waiting_on"], ["T1"])

        self.cli("task", "T1", "--status", "done")
        self.assertEqual(next(t for t in tb.build_state()["run"]["tasks"] if t["id"] == "T2")["waiting_on"], [])

        self.cli("stage", "construcao")  # pula arquitetura e plano
        stages = {s["key"]: s["status"] for s in tb.build_state()["run"]["stages"]}
        self.assertEqual(stages["descoberta"], "done")
        self.assertEqual(stages["arquitetura"], "skipped")
        self.assertEqual(stages["construcao"], "running")

        self.cli("artifact", "C:/Users/fulano/projetos/meu-app/src/app/page.tsx", "--kind", "code",
                 "--agent", "frontend-engineer", "--task", "T3")
        self.cli("decision", "ADR-1", "--title", "Monólito modular")
        self.cli("gate", "tests", "--status", "fail", "--value", "10/12")
        run = tb.build_state()["run"]
        self.assertEqual(run["artifacts"][0]["name"], "src/app/page.tsx")  # caminho absoluto vira relativo curto
        self.assertEqual(run["artifacts"][0]["kind"], "codigo")
        self.assertEqual(run["decisions"][0]["agent"], "software-architect")
        self.assertEqual(run["gates"][0]["key"], "testes")
        self.assertEqual(run["health"]["score"], 85)
        self.assertTrue(any(a["kind"] == "gate" for a in run["attention"]))

        self.cli("gate", "testes", "--status", "pass", "--value", "12/12")
        self.cli("finding", "F1", "--severity", "alta", "--agent", "code-correctness-reviewer",
                 "--title", "Falta autorização", "--where", "src/api/x.ts:10")
        run = tb.build_state()["run"]
        self.assertEqual(len(run["gates"][0]["history"]), 2)
        self.assertEqual(run["health"]["score"], 88)
        self.assertEqual(run["finding_counts"]["alta"], 1)
        self.cli("finding", "F1", "--status", "corrigido")
        run = tb.build_state()["run"]
        self.assertEqual(run["health"]["score"], 100)
        self.assertEqual(run["finding_counts"]["fixed"], 1)
        self.assertEqual(run["findings"][0]["title"], "Falta autorização")

        self.cli("finish", "--summary", "Entregue")
        run = tb.build_state()["run"]
        self.assertEqual(run["status"], "done")
        self.assertEqual(run["progress"], 1.0)
        self.assertTrue(all(s["status"] in ("done", "skipped") for s in run["stages"]))

    def test_attack_and_hardening_phase(self):
        self.cli("start", "--mode", "construir", "--title", "Loja")
        self.cli("stage", "revisao")
        self.cli("stage", "ataque")  # apelido da etapa de ataque e blindagem
        self.cli("task", "T1", "--agent", "offensive_security_tester", "--status", "running", "--title", "Atacar a API")
        self.cli("finding", "V1", "--severity", "critica", "--agent", "offensive-security-tester", "--cwe", "639",
                 "--title", "IDOR em pedidos", "--where", "src/api/pedidos.ts:9")
        self.cli("finding", "F1", "--severity", "baixa", "--agent", "code-maintainability-reviewer", "--title", "Nome vago")
        self.cli("finding", "V2", "--severity", "media", "--kind", "cwe", "--title", "x", expected=2)
        self.cli("finding", "V2", "--severity", "media", "--cwe", "abc", "--title", "x", expected=2)
        self.cli("gate", "ataque", "--status", "fail", "--value", "1 explorável")
        run = tb.build_state()["run"]
        self.assertEqual(run["current_stage"], "seguranca")
        v1 = next(f for f in run["findings"] if f["id"] == "V1")
        self.assertEqual((v1["kind"], v1["cwe"]), ("vulnerabilidade", "CWE-639"))
        self.assertEqual(next(f for f in run["findings"] if f["id"] == "F1")["kind"], "qualidade")
        self.assertEqual(run["finding_counts"]["vulns_open"], 1)
        self.assertTrue(any(a["text"].startswith("Vulnerabilidade") for a in run["attention"]))
        self.assertEqual(run["gates"][0]["key"], "pentest")
        self.cli("finding", "V1", "--status", "corrigido", "--agent", "security-hardening-engineer")
        self.cli("gate", "pentest", "--status", "pass", "--value", "0 exploráveis")
        run = tb.build_state()["run"]
        self.assertEqual(run["finding_counts"]["vulns_open"], 0)
        self.assertEqual(run["health"]["score"], 99)
        self.assertIn("CWE-639", tb.report_markdown(tb.build_state()))

    def test_report_markdown(self):
        self.cli("start", "--mode", "evoluir", "--title", "Exportar CSV")
        self.cli("task", "T1", "--agent", "backend-engineer", "--status", "done", "--title", "Endpoint de exportação")
        self.cli("gate", "testes", "--status", "pass", "--value", "40/40")
        dest = Path(self.tmp.name) / "r.md"
        self.cli("report", str(dest))
        md = dest.read_text(encoding="utf-8")
        self.assertIn("# Exportar CSV", md)
        self.assertIn("Endpoint de exportação", md)
        self.assertIn("40/40", md)

    def test_rejects_unknown_values(self):
        self.cli("start", "--mode", "voar", "--title", "x", expected=2)
        self.cli("start", "--mode", "revisar", "--title", "x")
        self.cli("stage", "dormir", expected=2)
        self.cli("task", "T1", "--agent", "frontend-dev", expected=2)
        self.cli("task", "T1", "--status", "talvez", expected=2)
        self.cli("artifact", "a.txt", "--kind", "planilha", expected=2)
        self.cli("gate", "testes", "--status", "quase", expected=2)
        self.cli("gate", "testes de carga!", "--status", "pass", expected=2)
        self.cli("finding", "F1", "--severity", "enorme", expected=2)

    def test_command_without_active_mission(self):
        self.cli("stage", "descoberta", expected=1)

    def test_secrets_are_not_stored(self):
        self.cli("start", "--mode", "depurar", "--title", "Falha no login")
        self.cli("note", "password=SuperSecreta123 no .env")
        self.cli("task", "T1", "--agent", "coordinator", "--title", "token ghp_abcdefghijklmnopqrstuvwxyz0123")
        self.cli("finding", "F1", "--severity", "critica", "--title", "postgres://app:s3nh4forte@db:5432/app exposto")
        raw = self.events_raw()
        for secret in ("SuperSecreta123", "ghp_abcdefghijklmnopqrstuvwxyz0123", "s3nh4forte"):
            self.assertNotIn(secret, raw)
        self.assertIn("conteúdo omitido", raw)

    def test_malformed_event_does_not_break_state(self):
        self.cli("start", "--mode", "construir", "--title", "Robustez")
        with open(Path(self.tmp.name) / "board" / "events.jsonl", "a", encoding="utf-8") as fh:
            run = tb.build_state()["run"]["id"]
            fh.write(json.dumps({"v": 1, "ts": "2026-01-01T00:00:00Z", "type": "stage", "run": run, "stage": "xpto"}) + "\n")
            fh.write("lixo\n")
        self.assertEqual(tb.build_state()["run"]["title"], "Robustez")


class HookTests(BoardCase):
    def hook(self, event, agent, tool_use_id, description="Revisar autenticação", tool="Agent"):
        payload = {"hook_event_name": event, "tool_name": tool, "tool_use_id": tool_use_id, "cwd": "/p/loja",
                   "session_id": "s1", "tool_input": {"subagent_type": agent, "description": description}}
        return self.cli("hook", "--app", "masterdev", stdin=json.dumps(payload))

    def test_hook_links_to_announced_task_and_advances_stage(self):
        self.cli("start", "--mode", "construir", "--title", "Loja")
        self.cli("stage", "plano")
        self.cli("task", "T1", "--agent", "backend-engineer", "--status", "queued", "--title", "API de pedidos")
        self.hook("PreToolUse", "backend-engineer", "tu_1")
        run = tb.build_state()["run"]
        self.assertEqual(len(run["tasks"]), 1)
        self.assertEqual(run["tasks"][0]["status"], "running")
        self.assertEqual(run["tasks"][0]["title"], "API de pedidos")
        self.assertEqual(run["current_stage"], "construcao")
        self.hook("PostToolUse", "backend-engineer", "tu_1")
        self.assertEqual(tb.build_state()["run"]["tasks"][0]["status"], "done")
        self.hook("PreToolUse", "frontend-engineer", "tu_2", "Tela de checkout")
        self.cli("stage", "revisao")
        self.hook("PreToolUse", "mobile-engineer", "tu_3", "Ajuste tardio")
        self.assertEqual(tb.build_state()["run"]["current_stage"], "revisao")  # hook nunca volta etapa

    def test_hook_creates_session_when_no_mission(self):
        self.hook("PreToolUse", "plugin:qa_test_engineer", "tu_9", "Testes E2E")
        run = tb.build_state()["run"]
        self.assertEqual(run["mode"], "livre")
        self.assertEqual(run["project"], "loja")
        self.assertEqual(run["tasks"][0]["agent"], "qa-test-engineer")

    def test_hook_ignores_other_agents_and_tools(self):
        self.hook("PreToolUse", "general-purpose", "tu_2")
        self.hook("PreToolUse", "data-architect", "tu_4")  # agente de outro pacote
        self.hook("PreToolUse", "backend-engineer", "tu_3", tool="Bash")
        self.cli("hook", stdin="isto não é json")
        self.assertFalse((Path(self.tmp.name) / "board" / "events.jsonl").exists())

    def test_hook_decodes_utf8(self):
        self.hook("PreToolUse", "ux-ui-designer", "tu_4", "Revisão de acessibilidade das telas")
        self.assertEqual(tb.build_state()["run"]["tasks"][0]["title"], "Revisão de acessibilidade das telas")


class ServerAndExportTests(BoardCase):
    def test_http_api_and_cors(self):
        self.cli("start", "--mode", "construir", "--title", "API")
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), tb.BoardHandler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health") as r:
                self.assertEqual(json.load(r)["app"], tb.APP)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state") as r:
                state = json.load(r)
                self.assertEqual(state["run"]["title"], "API")
                self.assertEqual(len(state["agents_meta"]), 19)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/report.md") as r:
                self.assertIn("# API", r.read().decode("utf-8"))
                self.assertIn("attachment", r.headers.get("Content-Disposition"))
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
                html = r.read().decode("utf-8")
                self.assertIn('"mode": "live"', html)
                self.assertNotIn("/*__MASTERDEV_CONFIG__*/", html)
                self.assertIn("default-src 'self'", r.headers.get("Content-Security-Policy"))
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/state", headers={"Origin": "https://exemplo.com"})
            with urllib.request.urlopen(req) as r:
                self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/state", headers={"Origin": "null"})
            with urllib.request.urlopen(req) as r:
                self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "null")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_export_has_demo_and_snapshot(self):
        dest = Path(self.tmp.name) / "painel.html"
        self.cli("export", str(dest))
        html = dest.read_text(encoding="utf-8")
        self.assertIn('"mode": "file"', html)
        self.assertIn("App de agendamento para clínicas", html)  # quadros da demonstração

    def test_demo_frames_progress(self):
        frames = tb.demo_frames(8)
        self.assertEqual(len(frames), 8)
        self.assertLess(frames[0]["run"]["progress"], frames[-1]["run"]["progress"])
        last = frames[-1]["run"]
        self.assertEqual(last["status"], "done")
        self.assertEqual(last["involved"], 18)
        self.assertGreaterEqual(len(last["artifacts"]), 8)
        self.assertEqual(last["finding_counts"]["fixed"], 5)
        self.assertEqual(last["finding_counts"]["vulns"], 3)
        self.assertEqual(last["finding_counts"]["vulns_open"], 0)
        self.assertEqual(next(g for g in last["gates"] if g["key"] == "pentest")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
