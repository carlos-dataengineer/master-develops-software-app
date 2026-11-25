"""Integration tests for the local Contextual Learning Engine (stdlib only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "masterdev" / "scripts" / "contextual_memory.py"


class ContextualMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.memory_home = self.base / "operator-memory"
        self.project_a = self.base / "project-a"
        self.project_b = self.base / "project-b"
        self.project_a.mkdir()
        self.project_b.mkdir()
        self.env = os.environ.copy()
        self.env["MASTERDEV_MEMORY_HOME"] = str(self.memory_home)
        self.env.pop("MASTERDEV_ALLOW_IN_PROJECT_MEMORY", None)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, project=None, expected=0):
        cmd = [sys.executable, str(SCRIPT), *args]
        if project is not None:
            cmd += ["--project-root", str(project)]
        result = subprocess.run(cmd, cwd=str(project or self.project_a), env=self.env,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, expected, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
        return result

    def remember(self, scope, title, content, project=None, status="accepted", source="user_explicit"):
        result = self.run_cli("remember", "--scope", scope, "--kind", "pattern",
                              "--title", title, "--content", content,
                              "--status", status, "--source", source,
                              "--confidence", "0.9", project=project)
        return json.loads(result.stdout)["id"]

    def recall(self, query, project):
        return json.loads(self.run_cli("recall", "--query", query, project=project).stdout)["memories"]

    def test_operator_memory_shared_but_project_memory_isolated(self):
        self.remember("operator", "Prefer SQL", "Use SQL for simple declarative transformations.", self.project_a)
        self.remember("project", "Source grain A", "Project A source has one row per account.", self.project_a)

        recalled_a = self.recall("SQL account", self.project_a)
        recalled_b = self.recall("SQL account", self.project_b)

        self.assertTrue(any(x["title"] == "Prefer SQL" for x in recalled_a))
        self.assertTrue(any(x["title"] == "Source grain A" for x in recalled_a))
        self.assertTrue(any(x["title"] == "Prefer SQL" for x in recalled_b))
        self.assertFalse(any(x["title"] == "Source grain A" for x in recalled_b))

    def test_candidate_is_not_recalled_until_confirmed(self):
        memory_id = self.remember("project", "Possible convention", "Maybe prefer one notebook per layer.",
                                  self.project_a, status="candidate", source="agent_inference")
        self.assertFalse(any(x["title"] == "Possible convention" for x in self.recall("notebook layer", self.project_a)))
        self.run_cli("confirm", memory_id, project=self.project_a)
        self.assertTrue(any(x["title"] == "Possible convention" for x in self.recall("notebook layer", self.project_a)))

    def test_sensitive_credential_is_rejected(self):
        self.run_cli("remember", "--scope", "project", "--kind", "solution", "--title", "Unsafe",
                     "--content", "api_key=abcDEF1234567890", "--status", "accepted",
                     project=self.project_a, expected=2)

    def test_forget_project_does_not_delete_operator_memory(self):
        self.remember("operator", "Global preference", "Prefer concise diffs.", self.project_a)
        self.remember("project", "Project detail", "Use a specific source contract.", self.project_a)
        self.run_cli("forget-project", "--yes", project=self.project_a)
        memories = self.recall("preference contract", self.project_a)
        self.assertTrue(any(x["title"] == "Global preference" for x in memories))
        self.assertFalse(any(x["title"] == "Project detail" for x in memories))

    def test_export_does_not_include_absolute_project_paths(self):
        self.remember("project", "Project note", "A sanitized project decision.", self.project_a)
        destination = self.base / "backup.json"
        self.run_cli("export", "--output", str(destination), project=self.project_a)
        payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "masterdev-contextual-memory-export")
        self.assertTrue(any(item["title"] == "Project note" for item in payload["memories"]))
        self.assertNotIn(str(self.project_a), destination.read_text(encoding="utf-8"))

    def test_memory_store_inside_project_is_blocked(self):
        self.env["MASTERDEV_MEMORY_HOME"] = str(self.project_a / ".local-memory")
        self.run_cli("status", project=self.project_a, expected=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
