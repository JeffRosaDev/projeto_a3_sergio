"""Regressão visual/funcional opcional: pip install playwright; playwright install chromium.

Uso: python scripts/check_browser.py --url http://localhost:8502
Aceita Streamlit Cloud (iframe) e instalação local; só cria dados fictícios por sessão.
"""

import argparse
import json
import re
from pathlib import Path
import sqlite3
import time

from playwright.sync_api import sync_playwright, expect


def application(page, url):
    """Espera o app, incluindo o iframe usado pelo Streamlit Community Cloud."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        for frame in page.frames:
            if frame.get_by_role(
                "button", name="Iniciar simulação", exact=True
            ).count():
                return frame
        page.wait_for_timeout(500)
    raise AssertionError("O aplicativo atualizado não ficou disponível em 60 s.")


def seconds(app):
    """Lê o relógio exibido em mm:ss, inclusive acima de uma hora."""
    value = app.locator('[data-testid="stMetricValue"]').first.inner_text()
    minutes, remainder = value.split(":")
    return int(minutes) * 60 + int(remainder)


def run(url, output):
    """Verifica avanço real, estabilidade de campos, comandos, SQL e mobile."""
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        browser = p.chromium.launch(
            headless=True, **({"executable_path": str(edge)} if edge.exists() else {})
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        app = application(page, url)
        expect(app.locator('[data-testid="stMetricValue"]').first).to_have_text("00:00")
        page.wait_for_timeout(2200)
        assert seconds(app) == 0, "Sessão pausada avançou."
        app.get_by_role("button", name="Adicionar cenário", exact=True).click()
        expect(app.locator('[data-testid="stMetricValue"]').nth(1)).to_have_text("7")
        assert (
            app.locator(".ticket").first.evaluate(
                "el => getComputedStyle(el).animationName"
            )
            == "none"
        )
        app.get_by_role("button", name="Iniciar simulação", exact=True).click()
        expect(
            app.get_by_role("button", name="Pausar simulação", exact=True)
        ).to_be_visible(timeout=15000)
        expect(app.locator('[data-testid="stMetricValue"]').first).not_to_have_text(
            "00:00", timeout=15000
        )
        first = seconds(app)
        assert first >= 5, f"Relógio não iniciou: {first}"
        page.wait_for_timeout(1600)
        assert seconds(app) > first, "O relógio deixou de progredir."

        app.get_by_role("tab", name="Laboratório", exact=True).click()
        page.wait_for_timeout(300)
        expect(app.locator('[data-testid="stApp"]')).to_have_attribute(
            "data-test-script-state", "notRunning", timeout=15000
        )
        field = app.get_by_role("spinbutton", name="Simples", exact=True)
        field.fill("75")
        field.evaluate("el => window.draftField = el")
        before_edit = seconds(app)
        page.wait_for_timeout(2400)
        assert field.input_value() == "75", "Rascunho foi perdido durante reprodução."
        assert field.evaluate(
            "el => el === window.draftField && el === document.activeElement"
        ), "Campo perdeu identidade/foco."
        assert seconds(app) > before_edit, "Navegar congelou o relógio."
        app.get_by_role("button", name="Aplicar parâmetros", exact=True).click()
        expect(
            app.get_by_text("Parâmetros aplicados e registrados.", exact=True)
        ).to_be_visible()
        app.get_by_role("button", name="Pausar simulação", exact=True).click()
        stopped = seconds(app)
        page.wait_for_timeout(2300)
        assert seconds(app) == stopped, "Pausa da reprodução não congelou o relógio."
        page.screenshot(path=str(output / "laboratorio.png"))

        app.get_by_role("button", name="Pausar cozinha", exact=True).click()
        expect(
            app.get_by_role("button", name="Retomar cozinha", exact=True)
        ).to_be_visible()
        app.get_by_role("button", name="+60 segundos", exact=True).click()
        target = stopped + 60
        expect(app.locator('[data-testid="stMetricValue"]').first).to_have_text(
            f"{target // 60:02}:{target % 60:02}"
        )
        app.get_by_role(
            "spinbutton", name="Novo tempo restante do preparo atual (s)", exact=True
        ).fill("2")
        app.get_by_role("button", name="Ajustar preparo atual", exact=True).click()
        expect(
            app.get_by_text("Tempo restante ajustado e auditado.", exact=True)
        ).to_be_visible()
        app.get_by_role("button", name="Retomar cozinha", exact=True).click()
        expect(
            app.get_by_role("button", name="Pausar cozinha", exact=True)
        ).to_be_visible()
        app.get_by_role("button", name="+60 segundos", exact=True).click()
        expect(app.locator('[data-testid="stMetricValue"]').nth(2)).not_to_have_text(
            "0"
        )
        app.get_by_role("button", name="Cancelar pedido", exact=True).click()
        expect(app.get_by_text("Cancelamento registrado.", exact=True)).to_be_visible()

        app.get_by_role("textbox", name="Identificador (opcional)", exact=True).fill(
            "PED-0001"
        )
        app.get_by_role("button", name="Adicionar à fila", exact=True).click()
        expect(
            app.get_by_text(
                "Não foi possível: Esse ID já foi usado nesta sessão.", exact=True
            )
        ).to_be_visible()
        expect(
            app.get_by_role("textbox", name="Identificador (opcional)", exact=True)
        ).to_have_value("PED-0001")
        app.get_by_role("tab", name="Operação ao vivo", exact=True).click()
        page.screenshot(path=str(output / "operacao.png"))
        app.get_by_role("tab", name="Logs e auditoria", exact=True).click()
        with page.expect_download() as download:
            app.get_by_role(
                "button", name="Baixar histórico completo · SQL", exact=True
            ).click()
        sql_path = output / "logs.sql"
        download.value.save_as(sql_path)
        with sqlite3.connect(":memory:") as connection:
            connection.executescript(sql_path.read_text(encoding="utf-8"))
            types = {
                r[0]
                for r in connection.execute(
                    "SELECT DISTINCT event_type FROM queue_events"
                )
            }
            assert {
                "ENQUEUED",
                "SERVICE_STARTED",
                "PREPARATION_COMPLETED",
                "CANCELLED",
            } <= types
            actions = {
                r[0]
                for r in connection.execute(
                    "SELECT DISTINCT action FROM simulation_actions"
                )
            }
            assert {
                "CONFIG_CHANGED",
                "STATION_PAUSE",
                "STATION_RESUME",
                "PREPARATION_ADJUSTED",
            } <= actions
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM queue_events WHERE event_type='ENQUEUED'"
                ).fetchone()[0]
                == 7
            )

        app.get_by_role("textbox", name="Buscar ID ou detalhe", exact=True).fill(
            "PLAYBACK_STARTED"
        )
        app.get_by_role("textbox", name="Buscar ID ou detalhe", exact=True).press(
            "Enter"
        )
        expect(app.get_by_text(re.compile(r"^1 de \d+ registros\."))).to_be_visible(
            timeout=15000
        )
        with page.expect_download() as download:
            app.get_by_role(
                "button", name="Exportar auditoria filtrada · JSON", exact=True
            ).click()
        json_path = output / "auditoria.json"
        download.value.save_as(json_path)
        filtered = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(filtered) == 1 and filtered[0]["operation"] == "PLAYBACK_STARTED"
        page.screenshot(path=str(output / "auditoria.png"))

        mobile = browser.new_page(
            viewport={"width": 390, "height": 844}, is_mobile=True
        )
        mobile_app = application(mobile, url)
        expect(mobile_app.locator('[data-testid="stMetricValue"]').first).to_have_text(
            "00:00"
        )
        mobile.wait_for_timeout(1200)
        mobile.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert mobile_app.locator('[data-testid="stException"]').count() == 0
        assert app.locator('[data-testid="stException"]').count() == 0
        assert not page_errors, page_errors

        app.get_by_text("Nova sessão", exact=True).click()
        expect(
            app.get_by_role("button", name="Iniciar nova sessão", exact=True)
        ).to_be_disabled()
        app.get_by_text("Confirmo iniciar outra sessão", exact=True).click()
        app.get_by_role("button", name="Iniciar nova sessão", exact=True).click()
        expect(app.locator('[data-testid="stMetricValue"]').first).to_have_text("00:00")
        expect(app.locator('[data-testid="stMetricValue"]').nth(1)).to_have_text("0")
        expect(
            app.get_by_role("button", name="Iniciar simulação", exact=True)
        ).to_be_visible()
        report = {
            "url": url,
            "status": "passed",
            "first_auto_second": first,
            "draft_kept_focus": True,
            "sql_roundtrip": True,
            "isolated_mobile_session": True,
            "browser_errors": page_errors,
        }
        (output / "result.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report), flush=True)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8502")
    parser.add_argument("--output", type=Path, default=Path("tmp/browser-regression"))
    args = parser.parse_args()
    run(args.url, args.output)
