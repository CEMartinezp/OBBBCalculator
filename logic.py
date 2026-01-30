def calculate_ot_premium(total_ot, multiplier):
    """
    Calculates the premium portion of overtime pay.
    Example: $150 OT at 1.5x → $50 premium
    """
    if multiplier <= 1:
        return 0.0
    return total_ot * (multiplier - 1) / multiplier


def apply_phaseout(magi, max_value, phase_start):
    """
    Applies IRS-style phase-out based on MAGI.
    """
    if magi <= phase_start:
        return max_value

    reduction = min(1.0, (magi - phase_start) / 100000)
    return max(0, max_value * (1 - reduction))
