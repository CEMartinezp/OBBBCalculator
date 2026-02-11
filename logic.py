import math
from typing import Literal

def calculate_ot_premium(
    ot_amount: float,
    multiplier: float,
    amount_type: Literal["total", "premium", "unknown"] = "total"
) -> float:
    """
    Calcula la porción de prima (premium) del pago por overtime que es deducible como QOC.

    Parámetros:
    - ot_amount: Monto total o prima ingresado por el usuario (dólares).
    - multiplier: Factor de pago (debe ser 1.5 o 2.0).
    - amount_type:
        "total"    → monto ingresado incluye base regular + prima
        "premium"  → monto ingresado es SOLO la prima extra
        "unknown"  → se asume "total" (enfoque conservador)

    Retorna:
    - La porción de prima deducible (redondeada hacia abajo al dólar entero más cercano)
    - 0.0 si no hay prima o los valores son inválidos

    Ejemplos:
    - 300 @ 1.5 "total"   → 100.0 (porque prima = 300 × 0.5 / 1.5 = 100)
    - 100 @ 1.5 "premium" → 100.0
    - 400 @ 2.0 "total"   → 100.0 (prima = 400 × 1 / 2 = 200? wait → 400 × 1/2 = 200? No: (2-1)/2 = 0.5 → 400×0.5=200)
    """
    if ot_amount <= 0:
        return 0.0

    if multiplier <= 1.0:
        return 0.0  # No hay prima si no hay incremento

    # Restringir a los valores esperados (más seguro)
    if multiplier not in (1.5, 2.0):
        # Podrías raise ValueError, pero retornamos 0 para no romper la UI
        return 0.0

    if amount_type == "premium":
        premium = ot_amount
    elif amount_type in ("total", "unknown"):
        premium = ot_amount * (multiplier - 1) / multiplier
    else:
        raise ValueError(f"Tipo de monto inválido: {amount_type!r}. Usa 'total', 'premium' o 'unknown'.")

    # Redondeo conservador (floor) para seguridad fiscal
    return max(0.0, math.floor(premium))


def apply_phaseout(
    magi: float,
    max_value: float,
    phase_start: float,
    phase_range: float = 100000.0
) -> float:
    """
    Aplica una reducción lineal (phase-out) típica del IRS cuando el MAGI supera cierto umbral.

    Parámetros:
    - magi: Modified Adjusted Gross Income estimado
    - max_value: Valor máximo de la deducción permitida
    - phase_start: Nivel de MAGI donde comienza la reducción
    - phase_range: Rango de ingresos durante el cual la deducción se reduce a cero (default: $100,000)

    Retorna:
    - Valor de la deducción después de phase-out (redondeado hacia abajo)

    Ejemplo:
    - max_value=12500, phase_start=150000, phase_range=100000
      → Si MAGI = 175000 → reducción 25% → 9375
      → Si MAGI >= 250000 → 0
    """
    if magi <= phase_start:
        return math.floor(max_value)

    if phase_range <= 0:
        return 0.0  # Evita división por cero

    if magi >= phase_start + phase_range:
        return 0.0

    reduction_ratio = (magi - phase_start) / phase_range
    allowed = max_value * (1 - reduction_ratio)

    return max(0.0, math.floor(allowed))