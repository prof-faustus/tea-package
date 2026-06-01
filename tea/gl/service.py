"""GL service: chart setup + posting through python-accounting (REQ-DATA-0210..0214).

Every monetary event posts as a balanced library transaction subtype; the Package
captures the returned transaction id for the lineage spine (REQ-DATA-0023) and
reads the library's computed amounts/balances (REQ-DATA-0202/0254). It never posts
to gl tables directly.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from python_accounting.models import Entity, Currency, Account, Tax, LineItem
from python_accounting.transactions import (
    ClientInvoice, ClientReceipt, SupplierBill, SupplierPayment, JournalEntry,
)
from python_accounting.models import Assignment

AccountType = Account.AccountType


class GLService:
    """Thin orchestration over a python-accounting session (entity-scoped)."""

    def __init__(self, session, entity: Entity, currency: Currency):
        self.session = session
        self.entity = entity
        self.currency = currency

    # ---- bootstrap a scoped entity with its reporting currency ----
    @classmethod
    def bootstrap_entity(cls, session, name: str, currency_code: str = "EUR") -> "GLService":
        entity = Entity(name=name)
        session.add(entity)
        session.commit()
        session.entity = entity                      # scope all queries to this entity
        currency = Currency(name=currency_code, code=currency_code, entity_id=entity.id)
        session.add(currency)
        session.commit()
        entity.currency_id = currency.id
        session.commit()
        return cls(session, entity, currency)

    # ---- chart of accounts ----
    def account(self, name: str, account_type) -> Account:
        acc = Account(name=name, account_type=account_type,
                      currency_id=self.currency.id, entity_id=self.entity.id)
        self.session.add(acc)
        self.session.commit()
        return acc

    def tax(self, name: str, code: str, rate, control_account: Account) -> Tax:
        t = Tax(name=name, code=code, rate=Decimal(str(rate)),
                account_id=control_account.id, entity_id=self.entity.id)
        self.session.add(t)
        self.session.commit()
        return t

    # ---- posting ----
    def post_client_invoice(self, *, client_account: Account, lines: list[dict],
                            narration: str, date: datetime | None = None):
        """ClientInvoice: debit receivable, credit revenue (+ tax control). REQ-DATA-0211.

        `lines` = [{"account": revenue_account, "amount": int_minor_or_decimal,
                    "quantity": 1, "tax": Tax|None}]
        Returns the posted library transaction (with .id and library-computed .amount).
        """
        inv = ClientInvoice(narration=narration, account_id=client_account.id,
                            transaction_date=date or datetime.now(),
                            currency_id=self.currency.id, entity_id=self.entity.id)
        self.session.add(inv)
        self.session.flush()
        for ln in lines:
            li = LineItem(narration=ln.get("narration", narration),
                          account_id=ln["account"].id,
                          amount=Decimal(str(ln["amount"])),
                          quantity=Decimal(str(ln.get("quantity", 1))),
                          tax_id=(ln["tax"].id if ln.get("tax") else None),
                          entity_id=self.entity.id)
            self.session.add(li)
            self.session.flush()
            inv.line_items.add(li)
        self.session.add(inv)
        self.session.flush()
        inv.post(self.session)
        self.session.commit()
        return inv

    def post_client_receipt(self, *, client_account: Account, bank_account: Account,
                            amount, narration: str, date: datetime | None = None):
        """ClientReceipt: debit bank, credit receivable. REQ-DATA-0211 settlement leg."""
        rc = ClientReceipt(narration=narration, account_id=client_account.id,
                           transaction_date=date or datetime.now(),
                           currency_id=self.currency.id, entity_id=self.entity.id)
        self.session.add(rc)
        self.session.flush()
        li = LineItem(narration=narration, account_id=bank_account.id,
                      amount=Decimal(str(amount)), quantity=Decimal(1),
                      entity_id=self.entity.id)
        self.session.add(li)
        self.session.flush()
        rc.line_items.add(li)
        self.session.add(rc)
        self.session.flush()
        rc.post(self.session)
        self.session.commit()
        return rc

    def assign(self, *, clearing_txn, cleared_txn, amount):
        """Clear a receivable: assign a receipt to its invoice (REQ-DATA-0212)."""
        a = Assignment(assignment_date=datetime.now(),
                       transaction_id=clearing_txn.id,
                       assigned_id=cleared_txn.id,
                       assigned_type=cleared_txn.__class__.__name__,
                       assigned_no=cleared_txn.transaction_no,
                       entity_id=self.entity.id,
                       amount=Decimal(str(amount)))
        self.session.add(a)
        self.session.commit()
        return a

    # ---- reads (library is authoritative) ----
    def account_balance(self, account: Account, end_date: datetime | None = None) -> Decimal:
        return account.closing_balance(self.session, end_date or datetime.now())
