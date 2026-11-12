"""Accounts and transactions routes, backed by the Ledger through the SQLite repository (#18).

Every route returns plain JSON. Amounts are decimal strings, totals are calculated here and
never in React, and a transaction uses the domain's CSV_COLUMNS names (snake_case) with
integer ids. Errors are raised as FinanceError and become {code, message, field}
(see pft.api.main).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pft.api.store import LedgerStore, get_store
from pft.domain.account import Account
from pft.domain.category import AccountType, Category, Kind
from pft.domain.exceptions import InvalidTransferError
from pft.domain.factory import TransactionFactory
from pft.domain.money import DEFAULT_CURRENCY, Money
from pft.domain.transaction import Transaction
from pft.services.ledger import Ledger

router = APIRouter(prefix="/api", tags=["accounts"])
Store = Annotated[LedgerStore, Depends(get_store)]


class NewAccount(BaseModel):
    name: str
    type: str
    opening_balance: str
    currency: str = DEFAULT_CURRENCY


class RenameAccount(BaseModel):
    name: str


class NewTransaction(BaseModel):
    kind: str
    account_id: int
    amount: str
    date: str
    category: str = Category.OTHER.value
    note: str = ""


class TransactionEdit(BaseModel):
    kind: str
    amount: str
    date: str
    category: str | None = None
    note: str = ""


def account_dto(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "type": account.type.value,
        "opening_balance": str(account.opening_balance.amount),
        "currency": account.opening_balance.currency,
        "balance": str(account.balance.amount),
        "transaction_count": len(account),
    }


def transaction_dto(transaction: Transaction) -> dict[str, Any]:
    row: dict[str, Any] = dict(transaction.to_row())
    row["id"] = transaction.id
    row["account_id"] = transaction.account_id
    row["transfer_id"] = row["transfer_id"] or None
    row["direction"] = row["direction"] or None
    return row


def _transaction(ledger: Ledger, account_id: int, tx_id: int) -> Transaction:
    found = ledger.account(account_id).get(tx_id)
    assert isinstance(found, Transaction)  # only Transaction objects are ever stored
    return found


@router.get("/accounts")
def list_accounts(store: Store) -> list[dict[str, Any]]:
    return store.read(lambda ledger: [account_dto(a) for a in ledger.accounts])


@router.get("/net-worth")
def net_worth(store: Store) -> dict[str, Any]:
    def build(ledger: Ledger) -> dict[str, Any]:
        total = ledger.net_worth
        return {
            "currency": total.currency,
            "net_worth": str(total.amount),
            "account_count": len(ledger.accounts),
        }

    return store.read(build)


@router.post("/accounts", status_code=201)
def create_account(body: NewAccount, store: Store) -> dict[str, Any]:
    def create(ledger: Ledger) -> dict[str, Any]:
        account = ledger.open_account(
            body.name,
            AccountType.from_text(body.type),
            Money.of(body.opening_balance, body.currency),
        )
        return account_dto(account)

    return store.write(create)


@router.patch("/accounts/{account_id}")
def rename_account(account_id: int, body: RenameAccount, store: Store) -> dict[str, Any]:
    def rename(ledger: Ledger) -> dict[str, Any]:
        account = ledger.account(account_id)
        account.rename(body.name)
        return account_dto(account)

    return store.write(rename)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, store: Store) -> dict[str, int]:
    def delete(ledger: Ledger) -> dict[str, int]:
        ledger.close_account(account_id)
        return {"id": account_id}

    return store.write(delete)


@router.get("/accounts/{account_id}/transactions")
def list_transactions(account_id: int, store: Store) -> list[dict[str, Any]]:
    def build(ledger: Ledger) -> list[dict[str, Any]]:
        found = [t for t in ledger.account(account_id) if isinstance(t, Transaction)]
        newest_first = sorted(found, key=lambda t: (t.date, t.id), reverse=True)
        return [transaction_dto(t) for t in newest_first]

    return store.read(build)


@router.post("/transactions", status_code=201)
def create_transaction(body: NewTransaction, store: Store) -> dict[str, Any]:
    def create(ledger: Ledger) -> dict[str, Any]:
        ledger.account(body.account_id)  # an unknown account is reported before anything else
        transaction = TransactionFactory.from_input(
            body.kind,
            body.amount,
            body.category,
            body.date,
            body.account_id,
            body.note,
            transaction_id=ledger.next_transaction_id(),
        )
        ledger.add_transaction(body.account_id, transaction)
        return transaction_dto(transaction)

    return store.write(create)


@router.put("/accounts/{account_id}/transactions/{tx_id}")
def edit_transaction(
    account_id: int, tx_id: int, body: TransactionEdit, store: Store
) -> dict[str, Any]:
    def edit(ledger: Ledger) -> dict[str, Any]:
        current = _transaction(ledger, account_id, tx_id)
        if current.kind is Kind.TRANSFER:
            raise InvalidTransferError(
                "a transfer is edited as a linked pair, which is not available yet", field="kind"
            )
        updated = TransactionFactory.from_input(
            body.kind,
            body.amount,
            body.category or current.category.value,
            body.date,
            account_id,
            body.note,
            transaction_id=tx_id,
            currency=current.amount.currency,
        )
        ledger.account(account_id).replace(tx_id, updated)
        return transaction_dto(updated)

    return store.write(edit)


@router.delete("/accounts/{account_id}/transactions/{tx_id}")
def delete_transaction(account_id: int, tx_id: int, store: Store) -> dict[str, int]:
    def delete(ledger: Ledger) -> dict[str, int]:
        ledger.remove_transaction(account_id, tx_id)
        return {"id": tx_id}

    return store.write(delete)
