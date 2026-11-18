import pytest

from studyai.analysis import accounting as acc


@pytest.mark.parametrize("expr,expected", [
    ("1000 * 0.21", 210), ("1 250 × 21%", 262.5), ("(1500 - 150) * 0,98", 1323), ("2^3", 8), ("-5 + 10 / 4", -2.5),
])
def test_safe_eval(expr, expected):
    assert acc.safe_eval(expr) == pytest.approx(expected)


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "a + 1", "9**999999"])
def test_safe_eval_rejects(expr):
    with pytest.raises((ValueError, SyntaxError)):
        acc.safe_eval(expr)


def test_invoice_belgian_order():
    # Brut 1000, remise 10 %, escompte 2 %, TVA 21 % (TVA sur la base diminuée de l'escompte)
    r = acc.invoice(1000, discount_rate=0.10, cash_discount_rate=0.02, vat_rate=0.21)
    assert r["net"] == 900
    assert r["base"] == 882
    assert r["vat"] == pytest.approx(185.22)
    assert r["total"] == pytest.approx(1085.22)
    assert r["total_with_cash_discount"] == pytest.approx(1067.22)


def test_vat_from_ttc():
    assert acc.vat_from_ttc(121) == {"ht": 100.0, "vat": 21.0, "ttc": 121.0}


def test_linear_depreciation_with_prorata():
    r = acc.depreciation(10000, 5, first_year_prorata=0.5)
    annuities = [row["annuity"] for row in r["rows"]]
    assert annuities == [1000, 2000, 2000, 2000, 2000, 1000]
    assert r["rows"][-1]["book_value"] == 0


def test_degressive_switches_to_linear():
    r = acc.depreciation(10000, 5, method="degressif")
    annuities = [row["annuity"] for row in r["rows"]]
    assert r["rate"] == 0.4
    assert annuities[0] == 4000
    assert annuities[1] == 2400
    assert sum(annuities) == pytest.approx(10000)
    assert annuities[-1] == annuities[-2]  # passage au linéaire en fin de plan


def test_interest():
    assert acc.simple_interest(10000, 0.05, 73)["interest"] == 100.0
    assert acc.compound_interest(1000, 0.10, 2)["final"] == 1210.0


def test_verify_steps_flags_wrong_result():
    steps = acc.verify_steps([
        {"explanation": "TVA", "expression": "1000 * 0.21", "result": 210},
        {"explanation": "Total", "expression": "1000 + 210", "result": 1200},
        {"explanation": "texte", "expression": "", "result": 0},
    ])
    assert [s["check"] for s in steps] == ["ok", "erreur", "non_verifiable"]
    assert steps[1]["computed"] == 1210


def test_verify_entry():
    good = acc.verify_entry({"label": "Achat", "lines": [
        {"account": "604", "account_name": "Achats", "debit": 1000, "credit": 0},
        {"account": "411", "account_name": "TVA à récupérer", "debit": 210, "credit": 0},
        {"account": "440", "account_name": "Fournisseurs", "debit": 0, "credit": 1210},
    ]})
    assert good["balanced"] and not good["problems"]
    bad = acc.verify_entry({"label": "x", "lines": [
        {"account": "604", "account_name": "", "debit": 1000, "credit": 0},
        {"account": "940", "account_name": "", "debit": 0, "credit": 900},
    ]})
    assert not bad["balanced"]
    assert len(bad["problems"]) == 2


def test_verify_exercise_status():
    ex = acc.verify_exercise({"steps": [{"expression": "2*3", "result": 6}], "journal_entries": []})
    assert ex["verification"]["status"] == "ok"
