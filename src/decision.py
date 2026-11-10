def break_even(p_wholesale, r, C):
    """B_t = P^w_t (1 + r) + C : the price needed just to repay loan + transport."""
    return p_wholesale * (1 + r) + C


def decide(L, M, U, B, m_bar, beta=3.0, breakdown=False, stale=False):
    """Return (signal, reason, show_median) following Section 3.5 of the plan."""
    # --- RED checks come first: any one of them is enough ---
    if stale:
        return "RED", "Price bulletin missing or out of date", False
    if breakdown:
        return "RED", "Dambulla -> Colombo price link has broken down", False
    if U - L > beta * m_bar:
        return "RED", "Forecast too uncertain to trust", False
    if M < B:
        return "RED", "Expected price is below your break-even", False
    # --- Otherwise GREEN or AMBER ---
    if L >= B:
        return "GREEN", "Even a bad day (5th percentile) covers loan + transport", True
    return "AMBER", "Likely profit, but a loss is possible - use own cash or buy less", True


if __name__ == "__main__":
    B = break_even(p_wholesale=90, r=0.003, C=8)   # 90 Rs/kg, 0.3% interest, 8 Rs/kg transport
    print(f"Break-even price B = Rs. {B:.2f}/kg\n")

    tests = [   # (name,                 L,   M,   U,   breakdown, stale, expected)
        ("Safe day",                   105, 120, 135, False, False, "GREEN"),
        ("Risky but positive",          92, 110, 128, False, False, "AMBER"),
        ("Expected loss",               80,  95, 112, False, False, "RED"),
        ("Breakdown overrides Green",  105, 120, 135, True,  False, "RED"),
        ("Too uncertain",              100, 140, 190, False, False, "RED"),
        ("Stale bulletin",             105, 120, 135, False, True,  "RED"),
    ]
    passed = 0
    for name, L, M, U, bd, st, expected in tests:
        signal, reason, show = decide(L, M, U, B, m_bar=25, breakdown=bd, stale=st)
        ok = signal == expected
        passed += ok
        median_txt = f"median Rs.{M}" if show else "median hidden"
        print(f"{'✅' if ok else '❌'} {name:<26} {signal:<6} | {median_txt:<15} | {reason}")
    print(f"\n{passed}/{len(tests)} tests passed")