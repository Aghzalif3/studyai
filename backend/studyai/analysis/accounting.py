"""Outils comptables déterministes : les calculs sont refaits par Python, pas par l'IA."""
from __future__ import annotations

import ast
import operator
import re
from typing import Any

# Classes du PCMN belge
PCMN_CLASSES = {
    "1": "Fonds propres, provisions et dettes à plus d'un an",
    "2": "Frais d'établissement, actifs immobilisés et créances à plus d'un an",
    "3": "Stocks et commandes en cours d'exécution",
    "4": "Créances et dettes à un an au plus",
    "5": "Placements de trésorerie et valeurs disponibles",
    "6": "Charges",
    "7": "Produits",
}

BELGIAN_VAT_RATES = (0.0, 0.06, 0.12, 0.21)

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_eval(expr: str) -> float:
    """Évalue une expression arithmétique (nombres, + - * / ** parenthèses, %), sans rien exécuter d'autre."""
    e = expr.strip().replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    e = re.sub(r"(?<=\d) (?=\d{3}\b)", "", e)  # 1 250 -> 1250
    e = re.sub(r"(\d),(\d)", r"\1.\2", e)  # virgule décimale
    e = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", e)
    e = e.replace("€", "")
    tree = ast.parse(e, mode="eval")

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            if isinstance(node.op, ast.Pow):
                exp = ev(node.right)
                if abs(exp) > 100:
                    raise ValueError("exposant trop grand")
                return _OPS[ast.Pow](ev(node.left), exp)
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"Expression non autorisée : {expr}")

    return ev(tree)


def close(a: float, b: float, tol: float = 0.011) -> bool:
    return abs(a - b) <= max(tol, abs(b) * 1e-6)


def verify_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recalcule chaque étape ; ajoute `check` = ok | erreur | non_verifiable."""
    out = []
    for s in steps:
        s = dict(s)
        expr = (s.get("expression") or "").strip()
        if not expr:
            s["check"] = "non_verifiable"
        else:
            try:
                value = safe_eval(expr)
                s["computed"] = round(value, 4)
                s["check"] = "ok" if close(value, float(s.get("result") or 0)) else "erreur"
            except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
                s["check"] = "non_verifiable"
        out.append(s)
    return out


def verify_entry(entry: dict[str, Any]) -> dict[str, Any]:
    entry = dict(entry)
    lines = entry.get("lines") or []
    debit = round(sum(float(l.get("debit") or 0) for l in lines), 2)
    credit = round(sum(float(l.get("credit") or 0) for l in lines), 2)
    problems = []
    if not close(debit, credit):
        problems.append(f"Écriture déséquilibrée : débit {debit:.2f} ≠ crédit {credit:.2f}")
    for l in lines:
        acc = re.sub(r"\D", "", str(l.get("account") or ""))
        if not acc or acc[0] not in PCMN_CLASSES:
            problems.append(f"Compte « {l.get('account')} » hors des classes 1 à 7 du PCMN")
        if float(l.get("debit") or 0) and float(l.get("credit") or 0):
            problems.append(f"Le compte {l.get('account')} est à la fois au débit et au crédit")
    entry.update(total_debit=debit, total_credit=credit, balanced=close(debit, credit), problems=problems)
    return entry


def verify_exercise(ex: dict[str, Any]) -> dict[str, Any]:
    ex = dict(ex)
    ex["steps"] = verify_steps(ex.get("steps") or [])
    ex["journal_entries"] = [verify_entry(e) for e in ex.get("journal_entries") or []]
    errors = sum(1 for s in ex["steps"] if s["check"] == "erreur")
    errors += sum(1 for e in ex["journal_entries"] if e["problems"])
    ex["verification"] = {
        "errors": errors,
        "checked_steps": sum(1 for s in ex["steps"] if s["check"] != "non_verifiable"),
        "status": "ok" if errors == 0 else "a_verifier",
    }
    return ex


# --- calculatrices (page « Outils compta ») ------------------------------------

def r2(x: float) -> float:
    return round(x + 0.0, 2)


def invoice(gross: float, discount_rate: float = 0.0, rebate_rate: float = 0.0,
            cash_discount_rate: float = 0.0, vat_rate: float = 0.21, transport: float = 0.0) -> dict:
    """Facture belge : brut → remise → rabais → net → escompte → base TVA → TVA → total.

    En Belgique, la TVA se calcule sur le prix diminué de l'escompte (même si le client ne le prend pas).
    """
    steps = []
    discount = r2(gross * discount_rate)
    after_discount = r2(gross - discount)
    steps.append({"label": "Remise", "expression": f"{gross} × {discount_rate:.4g}", "value": discount})
    rebate = r2(after_discount * rebate_rate)
    net = r2(after_discount - rebate)
    steps.append({"label": "Rabais", "expression": f"{after_discount} × {rebate_rate:.4g}", "value": rebate})
    steps.append({"label": "Prix net", "expression": f"{gross} − {discount} − {rebate}", "value": net})
    cash_discount = r2(net * cash_discount_rate)
    steps.append({"label": "Escompte", "expression": f"{net} × {cash_discount_rate:.4g}", "value": cash_discount})
    base = r2(net - cash_discount + transport)
    steps.append({"label": "Base imposable", "expression": f"{net} − {cash_discount} + {transport}", "value": base})
    vat = r2(base * vat_rate)
    steps.append({"label": f"TVA {vat_rate * 100:g} %", "expression": f"{base} × {vat_rate:.4g}", "value": vat})
    total = r2(net + transport + vat)
    steps.append({"label": "Total à payer (sans escompte)", "expression": f"{net} + {transport} + {vat}", "value": total})
    total_with_cd = r2(total - cash_discount)
    steps.append({"label": "Total si escompte pris", "expression": f"{total} − {cash_discount}", "value": total_with_cd})
    return {"steps": steps, "net": net, "base": base, "vat": vat, "total": total, "total_with_cash_discount": total_with_cd}


def vat_from_ttc(ttc: float, vat_rate: float = 0.21) -> dict:
    ht = r2(ttc / (1 + vat_rate))
    return {"ht": ht, "vat": r2(ttc - ht), "ttc": r2(ttc)}


def depreciation(cost: float, years: int, method: str = "lineaire", residual: float = 0.0,
                 coefficient: float = 2.0, first_year_prorata: float = 1.0) -> dict:
    """Plan d'amortissement.

    - linéaire : (valeur d'acquisition − valeur résiduelle) / durée, première annuité au prorata ;
    - dégressif : taux linéaire × coefficient (plafonné à 40 %), appliqué à la valeur nette comptable,
      avec passage au linéaire dès que celui-ci devient plus élevé.
    """
    if years <= 0:
        raise ValueError("La durée doit être positive")
    if not 0 < first_year_prorata <= 1:
        raise ValueError("Le prorata de la première année doit être entre 0 et 1")
    base = cost - residual
    linear_rate = 1 / years
    rate = min(linear_rate * coefficient, 0.40) if method == "degressif" else linear_rate
    rows = []
    remaining = base
    periods = years + (1 if first_year_prorata < 1 else 0)
    for y in range(1, periods + 1):
        if remaining <= 0.004:
            break
        if method == "degressif":
            years_left = max(years - (y - 1), 1)
            annuity = max(remaining * rate, remaining / years_left)
        else:
            annuity = base * linear_rate
        if y == 1:
            annuity *= first_year_prorata
        if y == periods:
            annuity = remaining  # dernière annuité : le solde
        annuity = r2(min(annuity, remaining))
        remaining = r2(remaining - annuity)
        cumulated = r2(base - remaining)
        rows.append({"year": y, "annuity": annuity, "cumulated": cumulated, "book_value": r2(cost - cumulated)})
    return {"method": method, "rate": rate, "rows": rows}


def simple_interest(capital: float, annual_rate: float, days: int, day_basis: int = 365) -> dict:
    value = r2(capital * annual_rate * days / day_basis)
    return {"interest": value, "expression": f"{capital} × {annual_rate:.4g} × {days} / {day_basis}",
            "total": r2(capital + value)}


def compound_interest(capital: float, annual_rate: float, years: float) -> dict:
    final = r2(capital * (1 + annual_rate) ** years)
    return {"final": final, "interest": r2(final - capital), "expression": f"{capital} × (1 + {annual_rate:.4g})^{years:g}"}
