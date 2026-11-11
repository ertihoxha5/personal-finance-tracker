"""Domain enums.

Only AccountType is here for now, pulled forward from task #10 so the Account
class (#07) can use the real type. #10 adds Category, Kind and Frequency to this
module; keep the AccountType values below unchanged.
"""

from enum import Enum


class AccountType(Enum):
    CASH = "cash"
    BANK = "bank"
    CARD = "card"
    SAVINGS = "savings"
