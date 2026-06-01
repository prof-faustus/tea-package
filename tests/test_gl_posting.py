"""Stage-2 GL integration (TEST-INT): posting through the library, tax, reports.

Proves: monetary events post only through python-accounting (REQ-DATA-0022);
the library computes tax (REQ-DATA-0220); the trial balance balances
(REQ-DATA-0240); a receipt assigned to an invoice clears the receivable
(REQ-DATA-0211/0212). Skips cleanly when the GL DB/library is unavailable.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("python_accounting")
pytest.importorskip("sqlalchemy")

from python_accounting.models import Base  # noqa: E402
from python_accounting.reports import TrialBalance  # noqa: E402
from tea.gl.engine import make_engine, session_for  # noqa: E402
from tea.gl.service import GLService, AccountType  # noqa: E402


def _engine_or_skip():
    try:
        eng = make_engine()
        Base.metadata.create_all(eng)
        with eng.connect() as c:
            c.exec_driver_sql("SELECT 1")
        return eng
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"GL database unavailable: {e}")


def _chart(gl: GLService):
    return {
        "receivable": gl.account("Trade Debtors", AccountType.RECEIVABLE),
        "revenue": gl.account("Sales", AccountType.OPERATING_REVENUE),
        "bank": gl.account("Bank BSV", AccountType.BANK),
        "taxctl": gl.account("VAT Control", AccountType.CONTROL),
    }


def test_client_invoice_library_tax_and_balanced_trial_balance():
    eng = _engine_or_skip()
    with session_for(eng) as s:
        gl = GLService.bootstrap_entity(s, "ACME-INT-A", "EUR")
        acc = _chart(gl)
        vat = gl.tax("VAT20", "VAT20", 20, acc["taxctl"])
        inv = gl.post_client_invoice(
            client_account=acc["receivable"],
            lines=[{"account": acc["revenue"], "amount": 100, "quantity": 1, "tax": vat}],
            narration="INV-1",
        )
        # library-computed gross = net 100 + 20% tax = 120 (REQ-DATA-0220)
        assert Decimal(inv.amount) == Decimal("120")
        tb = TrialBalance(s)
        assert tb.balances["debit"] == abs(tb.balances["credit"]), tb.balances
        assert tb.balances["debit"] == Decimal("120")


def test_receipt_assignment_clears_receivable():
    eng = _engine_or_skip()
    with session_for(eng) as s:
        gl = GLService.bootstrap_entity(s, "ACME-INT-B", "EUR")
        acc = _chart(gl)
        inv = gl.post_client_invoice(
            client_account=acc["receivable"],
            lines=[{"account": acc["revenue"], "amount": 200, "quantity": 1, "tax": None}],
            narration="INV-2",
        )
        assert Decimal(inv.amount) == Decimal("200")
        # receivable carries the open balance before settlement
        assert Decimal(gl.account_balance(acc["receivable"])) == Decimal("200")
        receipt = gl.post_client_receipt(
            client_account=acc["receivable"], bank_account=acc["bank"],
            amount=200, narration="RC-2",
        )
        gl.assign(clearing_txn=receipt, cleared_txn=inv, amount=200)
        # after settlement the receivable is cleared (REQ-DATA-0212)
        assert Decimal(gl.account_balance(acc["receivable"])) == Decimal("0")
        tb = TrialBalance(s)
        assert tb.balances["debit"] == abs(tb.balances["credit"]), tb.balances
