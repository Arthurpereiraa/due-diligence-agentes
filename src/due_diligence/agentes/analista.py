"""Agente analista: aplica as regras de risco ao dossiê (determinístico; ver risco.py)."""

from __future__ import annotations

from datetime import date
from typing import Any

from due_diligence.risco import AnaliseRisco, analisar


class Analista:
    def __init__(self, hoje: date) -> None:
        self.hoje = hoje

    def analisar(self, dossie: dict[str, Any]) -> AnaliseRisco:
        return analisar(dossie, self.hoje)
