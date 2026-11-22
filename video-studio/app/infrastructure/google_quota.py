"""
Qué cuota agotó un 429 de la API de Gemini.

El texto no sirve para saberlo: Google contesta a todo 429 con «please check
your plan and billing details», sea la clave gratuita o de pago. Lo que
distingue es `error.details`: un `QuotaFailure` con la cuota agotada —las del
nivel gratuito llevan `FreeTier` en el id y `free_tier` en la métrica— y su
valor, y un `RetryInfo` con cuánto esperar. Si no vienen, queda el texto
(«limit: 0», «free tier»).
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

#: A dónde mandar a quien cree tener facturación: AI Studio enseña el plan
#: (gratuito o de pago) de cada clave y el proyecto al que pertenece.
KEYS_PAGE = "aistudio.google.com/apikey"


@dataclass(frozen=True)
class Quota:
    free_tier: bool  # la cuota agotada es del nivel gratuito
    zero: bool  # y vale cero: con ese plan el modelo no se puede usar
    name: str  # cuál, tal como la nombra Google («GenerateRequestsPerMinute…»)
    retry: str | None  # cuánto esperar según Google («26s»)
    said: str = ""  # el mensaje de Google, por si no trae cuota: un 429 también es saturación

    def detail(self) -> str:
        """« (cuota X; Google pide esperar 26s)», o lo que dijo Google si no nombra cuota."""
        if self.name:
            parts = [f"cuota {self.name}"]
        else:
            parts = [f"Google dice: «{self.said}»"] if self.said else []
        if self.retry:
            parts.append(f"Google pide esperar {self.retry}")
        return f" ({'; '.join(parts)})" if parts else ""


def read_quota(response: requests.Response) -> Quota:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        error = {}

    violations: list[dict] = []
    retry = None
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        kind = str(detail.get("@type", ""))
        if kind.endswith("QuotaFailure"):
            violations += [v for v in detail.get("violations") or [] if isinstance(v, dict)]
        elif kind.endswith("RetryInfo") and detail.get("retryDelay"):
            retry = str(detail["retryDelay"])

    said = " ".join(str(error.get("message") or response.text or "").split())
    message = said.lower()
    if violations:
        def is_free(v: dict) -> bool:
            return "free" in f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}".lower()

        free = any(is_free(v) for v in violations)
        zero = any(str(v.get("quotaValue")) == "0" for v in violations) or "limit: 0" in message
        first = violations[0]
        name = str(first.get("quotaId") or first.get("quotaMetric") or "")
    else:
        free = "free tier" in message or "free_tier" in message
        zero = "limit: 0" in message
        name = ""
    return Quota(free_tier=free, zero=zero, name=name, retry=retry, said=said[:200])
