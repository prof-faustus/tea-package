"""Introspect the installed python-accounting library (no assumptions about API).

Prints the import name, version, and the public constructs the Package binds to
(REQ-DATA-0252): Entity, Currency, Account, LineItem, Tax, Transaction subtypes,
Assignment, Balance, ReportingPeriod, report builders, and the config/session
surface. Used to pin Stage-2 integration against the real contract.
"""
from __future__ import annotations

import importlib
import pkgutil

WANT = [
    "Entity", "Currency", "Account", "LineItem", "Tax", "Transaction",
    "ClientInvoice", "SupplierBill", "ClientReceipt", "SupplierPayment",
    "CashSale", "CashPurchase", "JournalEntry", "CreditNote", "DebitNote",
    "ContraEntry", "Assignment", "Balance", "ReportingPeriod", "Config",
    "Account", "IncomeStatement", "BalanceSheet", "CashflowStatement",
    "TrialBalance", "AgingSchedule",
]


def main() -> int:
    mod = None
    for name in ("python_accounting", "accounting"):
        try:
            mod = importlib.import_module(name)
            print(f"IMPORT_OK module={name} version={getattr(mod, '__version__', '?')}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"IMPORT_FAIL {name}: {e}")
    if mod is None:
        return 1

    print("FILE", getattr(mod, "__file__", "?"))
    print("TOP_LEVEL_NAMES", sorted(n for n in dir(mod) if n[:1].isupper()))

    # submodules
    if hasattr(mod, "__path__"):
        subs = sorted(m.name for m in pkgutil.iter_modules(mod.__path__))
        print("SUBMODULES", subs)

    # resolve each wanted construct anywhere in the package
    found = {}
    for w in WANT:
        if hasattr(mod, w):
            found[w] = name
    print("FOUND_TOP", sorted(found))

    # try common submodules for models/reports
    for sub in ("models", "transactions", "reports", "config", "database",
                "models.transactions", "reports.financial_statement"):
        full = f"{name}.{sub}"
        try:
            sm = importlib.import_module(full)
            names = sorted(n for n in dir(sm) if n[:1].isupper())
            print(f"SUB {full}: {names[:40]}")
        except Exception as e:  # noqa: BLE001
            print(f"SUB {full}: -- ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
