"""Gera a capa e as capturas de tela do README (assets/ e docs/images/).

Sobe o painel real numa pasta temporária, registra missões fictícias e fotografa cada visão (escuro,
claro, celular, painel lateral, ajuda), um GIF da atualização ao vivo e a saída do instalador.
Nada usa dados reais: tudo vem da missão simulada do próprio team_board.py.

Requer: pip install playwright pillow   (usa o Chrome/Edge instalado; ou: python -m playwright install chromium)
Uso:    python scripts/screenshots.py
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
SCRIPTS = ROOT / "masterdev" / "skills" / "masterdev" / "scripts"
TEAM = ROOT / "masterdev" / "skills" / "masterdev" / "assets" / "team.json"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def browser(pw):
    for channel in ("chrome", "msedge", None):
        try:
            return pw.chromium.launch(channel=channel, headless=True) if channel else pw.chromium.launch(headless=True)
        except Exception:  # noqa: BLE001
            continue
    raise SystemExit("Nenhum Chromium disponível. Instale o Chrome ou rode: python -m playwright install chromium")


def write_events(tb, events):
    tb.events_file().write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")


def history_events(tb):
    now = tb.utc_now()
    out = []

    def run(offset_min, mode, title, project, platforms, steps, summary, status="done"):
        base = now - timedelta(minutes=offset_min)
        rid = tb.new_run_id(base)
        out.append({"v": 1, "ts": tb.iso(base), "type": "run.start", "run": rid, "mode": mode, "title": title,
                    "project": project, "host": "claude", "platforms": platforms})
        t = base
        for ev in steps:
            t += timedelta(minutes=3)
            out.append({"v": 1, "ts": tb.iso(t), "run": rid, **ev})
        out.append({"v": 1, "ts": tb.iso(t + timedelta(minutes=4)), "type": "run.end", "run": rid,
                    "status": status, "summary": summary})

    run(26 * 60, "revisar", "Revisão do PR de login social", "portal-cliente", ["web"], [
        {"type": "task", "task": "T1", "agent": "code-correctness-reviewer", "status": "done", "title": "Corretude do fluxo OAuth"},
        {"type": "task", "task": "T2", "agent": "security-engineer", "status": "done", "title": "Sessão e tokens"},
        {"type": "finding", "finding": "F1", "severity": "alta", "agent": "security-engineer", "title": "state do OAuth não validado"},
        {"type": "task", "task": "T3", "agent": "code-maintainability-reviewer", "status": "done", "title": "Organização do módulo de auth"},
    ], "3 achados, 1 alto, com evidências")
    run(50 * 60, "depurar", "Lista vazia ao voltar do segundo plano", "app-pedidos", ["android"], [
        {"type": "task", "task": "T1", "agent": "mobile-engineer", "status": "done", "title": "Reproduzir e localizar causa raiz"},
        {"type": "task", "task": "T2", "agent": "qa-test-engineer", "status": "done", "title": "Teste de regressão"},
        {"type": "gate", "gate": "testes", "status": "pass", "value": "88/88"},
    ], "Causa raiz: estado perdido no ciclo de vida; corrigido e testado")
    run(75 * 60, "evoluir", "Exportação de relatórios em CSV", "backoffice", ["web", "api"], [
        {"type": "task", "task": "T1", "agent": "backend-engineer", "status": "done", "title": "Endpoint paginado"},
        {"type": "task", "task": "T2", "agent": "frontend-engineer", "status": "done", "title": "Botão e estados"},
        {"type": "artifact", "name": "src/api/relatorios/export.ts", "kind": "codigo", "agent": "backend-engineer"},
    ], "Exportação entregue com 12 testes")
    run(110 * 60, "construir", "API de notificações push", "notifica", ["api"], [
        {"type": "task", "task": "T1", "agent": "software-architect", "status": "done", "title": "Contratos e filas"},
        {"type": "task", "task": "T2", "agent": "devops-sre-engineer", "status": "blocked", "title": "Credenciais do provedor de push"},
    ], "Aguardando credenciais do ambiente de testes", "cancelled")
    return out


def installer_output() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        env = {k: v for k, v in os.environ.items() if k not in ("CODEX_HOME", "MASTERDEV_HOME")}
        env.update({"HOME": tmp, "USERPROFILE": tmp, "MDV_NO_OPEN": "1", "MDV_NO_SERVER": "1", "NO_COLOR": "1"})
        r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "install.py")], env=env,
                           capture_output=True, text=True, encoding="utf-8")
        text = r.stdout
        for variant in {tmp, str(Path(tmp).resolve())}:
            text = text.replace(variant + os.sep, "~/").replace(variant, "~")
        text = text.replace("\\", "/")
        text = text.replace("Painel de produção: http://127.0.0.1:47841",
                            "Painel de produção: http://127.0.0.1:47841  (aberto no navegador)")
        return text.strip("\n")


def terminal_html(text: str) -> str:
    def color(line: str) -> str:
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = re.sub(r"^(\s*)✓", r'\1<b style="color:#4ade80">✓</b>', safe)
        safe = re.sub(r"^(\s*)&gt;", r'\1<b style="color:#38bdf8">&gt;</b>', safe)
        safe = re.sub(r"^(\s*)!", r'\1<b style="color:#fbbf24">!</b>', safe)
        safe = safe.replace("Master Develops", '<b style="color:#a5b4fc">Master Develops</b>', 1)
        safe = safe.replace("Pronto.", '<b style="color:#4ade80">Pronto.</b>')
        return safe
    body = "\n".join(color(line) for line in text.splitlines())
    cmd = "irm https://raw.githubusercontent.com/carlos-dataengineer/master-develops-software-app/main/install.ps1 | iex"
    return f"""<!doctype html><meta charset=utf-8><body style="margin:0;background:#0b1020;padding:28px">
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.5);overflow:hidden;max-width:1100px">
<div style="display:flex;gap:7px;padding:11px 14px;background:#111a2e;border-bottom:1px solid #1e293b">
<i style="width:11px;height:11px;border-radius:50%;background:#ef4444"></i><i style="width:11px;height:11px;border-radius:50%;background:#f59e0b"></i><i style="width:11px;height:11px;border-radius:50%;background:#22c55e"></i>
<span style="margin-left:10px;color:#64748b;font:12px Segoe UI,system-ui">PowerShell</span></div>
<pre style="margin:0;padding:18px 20px;color:#cbd5e1;font:13px/1.6 Consolas,ui-monospace,monospace;white-space:pre-wrap"><span style="color:#64748b">PS&gt;</span> {cmd}
  <b style="color:#38bdf8">&gt;</b> Baixando carlos-dataengineer/master-develops-software-app (main)
{body}</pre></div></body>"""


def cover_html() -> str:
    team = json.loads(TEAM.read_text(encoding="utf-8"))
    squads = {s["key"]: s for s in team["squads"]}
    cols = []
    for sq in team["squads"]:
        members = [a for a in team["agents"] if a["squad"] == sq["key"]]
        chips = "".join(f'<div class="m"><span style="background:{a["color"]}">{a["short"]}</span>{a["name"]}</div>' for a in members)
        cols.append(f'<div class="sq"><h3><i style="background:{sq["color"]}"></i>{sq["name"]}</h3>{chips}</div>')
    _ = squads
    return """<!doctype html><meta charset=utf-8><style>
*{box-sizing:border-box}body{margin:0;width:1600px;height:720px;font-family:Inter,"Segoe UI",system-ui,sans-serif;color:#e7ecf6;
background:radial-gradient(900px 500px at 10% 0%,rgba(124,140,255,.35),transparent 60%),radial-gradient(800px 500px at 100% 100%,rgba(56,189,248,.22),transparent 60%),#080b13;overflow:hidden;position:relative}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:40px 40px}
.left{position:absolute;left:80px;top:90px;width:600px}
.logo{display:flex;align-items:center;gap:16px}
h1{font-size:64px;line-height:1.02;margin:34px 0 18px;letter-spacing:-1.5px}
h1 em{font-style:normal;background:linear-gradient(90deg,#a5b4fc,#38bdf8);-webkit-background-clip:text;color:transparent}
p{font-size:22px;line-height:1.45;color:#a3b0c6;margin:0}
.tags{display:flex;gap:10px;margin-top:30px;flex-wrap:wrap}
.tags span{border:1px solid #2a3550;background:rgba(17,23,37,.8);border-radius:99px;padding:7px 14px;font-size:15px;color:#cbd5e1}
.right{position:absolute;right:70px;top:70px;width:780px;display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.sq{background:rgba(17,23,37,.82);border:1px solid #243049;border-radius:16px;padding:14px 14px 10px;box-shadow:0 20px 50px rgba(0,0,0,.35)}
.sq h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.5px;color:#93a3bd;display:flex;align-items:center;gap:8px}
.sq h3 i{width:10px;height:10px;border-radius:3px;display:inline-block}
.m{display:flex;align-items:center;gap:10px;font-size:15px;padding:6px 0}
.m span{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font:700 11px ui-monospace,Consolas,monospace;color:#fff}
.bar{position:absolute;left:80px;bottom:70px;display:flex;gap:10px;align-items:center;font:14px ui-monospace,Consolas,monospace;color:#7d8aa3}
.bar b{color:#4ade80}
</style><body><div class="grid"></div>
<div class="left"><div class="logo"><svg width="64" height="64" viewBox="0 0 32 32"><rect x="2" y="2" width="28" height="28" rx="8" fill="#7c8cff"/><path d="M12 11 7 16l5 5M20 11l5 5-5 5M17.5 9l-3 14" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
<div style="font-size:26px;font-weight:700">Master Develops</div></div>
<h1>Uma equipe completa para criar <em>softwares e apps</em></h1>
<p>18 especialistas de IA no Claude Code e no Codex — do produto ao ataque e blindagem de segurança — com painel de produção em tempo real.</p>
<div class="tags"><span>/masterdev</span><span>$masterdev</span><span>Web · iOS · Android · API</span><span>Dados & IA</span></div></div>
<div class="right">""" + "".join(cols) + """</div>
<div class="bar"><b>●</b> Painel ao vivo em 127.0.0.1:47841 · sem telemetria · MIT</div></body>"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Instale o Playwright: pip install playwright")
    OUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MASTERDEV_HOME"] = tmp
        sys.path.insert(0, str(SCRIPTS))
        import team_board as tb

        past = history_events(tb)
        write_events(tb, past + tb.demo_events(0.875, scale=4))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), tb.BoardHandler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{port}/"

        with sync_playwright() as pw:
            b = browser(pw)
            cov = b.new_context(viewport={"width": 1600, "height": 720}, device_scale_factor=1)
            cp = cov.new_page()
            cp.set_content(cover_html())
            cp.wait_for_timeout(300)
            (ROOT / "assets").mkdir(exist_ok=True)
            cp.screenshot(path=str(ROOT / "assets" / "cover.png"))
            print("  ✓ assets/cover.png")

            ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
            page = ctx.new_page()

            def shot(name, view="overview", theme="dark", full=False, key=None, wait=900, extra=""):
                page.goto(f"{url}?view={view}&theme={theme}{extra}")
                page.wait_for_selector(".mission", timeout=10000)
                if key:
                    page.keyboard.press(key)
                page.wait_for_timeout(wait)
                page.screenshot(path=str(OUT / name), full_page=full)
                print("  ✓", name)

            shot("painel-visao-geral.png", full=True)
            shot("painel-tarefas.png", "tasks")
            shot("painel-linha-do-tempo.png", "timeline")
            shot("painel-qualidade.png", "quality")
            shot("painel-entregaveis.png", "deliverables")
            shot("painel-historico.png", "history")
            shot("painel-tema-claro.png", theme="light")
            shot("painel-especialista.png", extra="&agent=backend-engineer", wait=1400)
            shot("painel-atalhos.png", key="?")

            mob = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
            mp = mob.new_page()
            mp.goto(f"{url}?view=overview&theme=dark")
            mp.wait_for_selector(".mission")
            mp.wait_for_timeout(800)
            mp.screenshot(path=str(OUT / "painel-celular.png"))
            print("  ✓ painel-celular.png")

            # GIF: a missão avançando pelo caminho real (arquivo → SSE → navegador)
            try:
                from PIL import Image
            except ImportError:
                Image = None
                print("  ! Pillow ausente: GIF não gerado (pip install pillow)")
            if Image is not None:
                gctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                gp = gctx.new_page()
                total = tb.DEMO_SCRIPT[-1][0]
                base = tb.utc_now() - timedelta(seconds=total * 4)
                rid = "rdemo-gif"
                frames = []
                cuts = [0.03, 0.12, 0.22, 0.3, 0.4, 0.5, 0.6, 0.66, 0.72, 0.78, 0.86, 0.93, 1.0]
                for i, cut in enumerate(cuts):
                    write_events(tb, past + tb.demo_events(cut, base=base, run_id=rid, scale=4))
                    if i == 0:
                        gp.goto(f"{url}?view=overview&theme=dark")
                        gp.wait_for_selector(".mission")
                    gp.wait_for_timeout(1300)
                    png = gp.screenshot(clip={"x": 0, "y": 0, "width": 1440, "height": 900})
                    frames.append(Image.open(io.BytesIO(png)).convert("RGB").resize((960, 600), Image.LANCZOS))
                pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f in frames]
                durations = [1100] * (len(pal) - 1) + [3200]
                pal[0].save(OUT / "painel-ao-vivo.gif", save_all=True, append_images=pal[1:], duration=durations,
                            loop=0, optimize=True)
                print("  ✓ painel-ao-vivo.gif")

            term = b.new_context(viewport={"width": 1156, "height": 600}, device_scale_factor=1.5)
            tp = term.new_page()
            tp.set_content(terminal_html(installer_output()))
            box = tp.locator("body > div").bounding_box()
            tp.screenshot(path=str(OUT / "instalacao.png"),
                          clip={"x": 0, "y": 0, "width": 1156, "height": box["y"] + box["height"] + 28})
            print("  ✓ instalacao.png")
            b.close()
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
