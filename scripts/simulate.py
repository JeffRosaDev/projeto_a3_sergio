"""Gera evidências reproduzíveis para a apresentação, sem interface gráfica."""

from dataclasses import replace
import json
from pathlib import Path
from fastfood.domain.enums import OrderComplexity
from fastfood.services.scenarios import create_engine, add_burst, metrics


def run():
    """Compara o mesmo lote com preparo normal, lento e uma interrupção."""
    output = Path(__file__).resolve().parents[1] / "exports"
    output.mkdir(exist_ok=True)
    results = []
    for name in ("Padrão", "Preparo lento", "Pausa de 300s"):
        engine = create_engine()
        try:
            if name == "Preparo lento":
                engine.configure(
                    replace(
                        engine.rules,
                        preparation_times_seconds={
                            c: engine.rules.preparation_seconds_for(c) * 2
                            for c in OrderComplexity
                        },
                    )
                )
            add_burst(engine, 40, seed=42, urgent_percent=60, scenario="Aleatório")
            if name == "Pausa de 300s":
                engine.pause_station(True)
                engine.advance(300)
                engine.pause_station(False)
            engine.advance(20000)
            results.append(
                {"scenario": name, "orders": 40, "seed": 42, **metrics(engine)}
            )
            if name == "Padrão":
                engine.audit_logger.export_sql(output / "logs.sql")
        finally:
            engine.audit_logger.close()
    (output / "cenarios.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    run()
