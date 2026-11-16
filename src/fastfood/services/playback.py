"""Relógio da reprodução: independente dos redraws e dos widgets do Streamlit."""

from dataclasses import dataclass
from math import isfinite

from fastfood.services.scenarios import add_burst


@dataclass
class PlaybackClock:
    """Acumula frações entre atualizações sem contar o mesmo intervalo duas vezes."""

    anchor: float | None = None  # Último segundo real já consumido pela reprodução.

    def reset(self, now: float) -> None:
        """Começa outra janela ao iniciar, pausar ou mudar velocidade/chegadas."""
        self.anchor = now

    def consume(self, now: float, speed: int) -> int:
        """Converte segundos reais inteiros em simulados; limita recuperação a 5 s."""
        if not isfinite(now):
            raise ValueError("O relógio real precisa ser finito.")
        if (
            isinstance(speed, bool)
            or not isinstance(speed, int)
            or speed not in (1, 5, 15, 30, 60)
        ):
            raise ValueError("Velocidade de reprodução inválida.")
        if self.anchor is None or now < self.anchor:
            self.reset(now)
            return 0
        elapsed = now - self.anchor
        whole_seconds = int(elapsed)
        if not whole_seconds:
            # Um clique/atualização antecipado NÃO descarta o tempo acumulado.
            return 0
        self.anchor += whole_seconds
        # Uma aba suspensa não gera minutos de produção/chegadas de uma só vez.
        return min(whole_seconds, 5) * speed


def advance_playback(
    engine,
    seconds: int,
    *,
    arrivals: bool,
    interval: int,
    seed: int,
    urgent_percent: int,
) -> None:
    """Avança um ciclo atômico e insere chegadas exatamente nas fronteiras."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        raise ValueError("O avanço da reprodução precisa ser inteiro não negativo.")
    if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
        raise ValueError("O intervalo entre chegadas precisa ser positivo.")
    with engine._atomic():
        remaining = (
            seconds  # Salta para chegada ou destino; não percorre segundos vazios.
        )
        while remaining:
            step = (
                min(remaining, interval - engine.current_time % interval)
                if arrivals
                else remaining
            )
            engine.advance(step)
            remaining -= step
            if arrivals and engine.current_time % interval == 0:
                add_burst(
                    engine, 1, seed + engine.current_time, urgent_percent, "Aleatório"
                )
