// Synthetic dashboard data, shaped like the future GET /api/dashboard?month=YYYY-MM
// response (#19). Amounts are decimal strings in EUR; expenses in recentTransactions are
// negative. Totals, savingsRate and category sums are precomputed here, exactly as the API
// will send them, so React never does arithmetic on money.

export const FIXTURE_MONTHS = ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]

export const DASHBOARD_FIXTURES = {
  "2026-07": {
    "month": "2026-07",
    "currency": "EUR",
    "availableMonths": [
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11"
    ],
    "summary": {
      "income": "2800.00",
      "expenses": "1814.90",
      "net": "985.10",
      "savingsRate": "35.2"
    },
    "trend": [
      {
        "month": "2026-07",
        "income": "2800.00",
        "expenses": "1814.90"
      },
      {
        "month": "2026-08",
        "income": "3250.00",
        "expenses": "1687.85"
      },
      {
        "month": "2026-09",
        "income": "2800.00",
        "expenses": "1785.59"
      },
      {
        "month": "2026-10",
        "income": "3100.00",
        "expenses": "1640.05"
      },
      {
        "month": "2026-11",
        "income": "3180.00",
        "expenses": "1733.60"
      }
    ],
    "categories": [
      {
        "id": "cat-housing",
        "name": "Housing",
        "total": "950.00"
      },
      {
        "id": "cat-groceries",
        "name": "Groceries",
        "total": "362.85"
      },
      {
        "id": "cat-transport",
        "name": "Transport",
        "total": "173.00"
      },
      {
        "id": "cat-utilities",
        "name": "Utilities",
        "total": "109.20"
      },
      {
        "id": "cat-entertainment",
        "name": "Entertainment",
        "total": "109.00"
      },
      {
        "id": "cat-dining",
        "name": "Dining out",
        "total": "91.10"
      },
      {
        "id": "cat-health",
        "name": "Health",
        "total": "19.75"
      }
    ],
    "recentTransactions": [
      {
        "id": "txn-2026-07-27-dining",
        "date": "2026-07-27",
        "description": "Lunch with friends",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-52.60"
      },
      {
        "id": "txn-2026-07-25-groceries",
        "date": "2026-07-25",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-105.40"
      },
      {
        "id": "txn-2026-07-22-health",
        "date": "2026-07-22",
        "description": "Pharmacy",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-19.75"
      },
      {
        "id": "txn-2026-07-20-entertainment",
        "date": "2026-07-20",
        "description": "Cinema",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-24.00"
      },
      {
        "id": "txn-2026-07-19-entertainment",
        "date": "2026-07-19",
        "description": "Concert tickets",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-85.00"
      },
      {
        "id": "txn-2026-07-18-groceries",
        "date": "2026-07-18",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-78.90"
      },
      {
        "id": "txn-2026-07-15-utilities",
        "date": "2026-07-15",
        "description": "Internet",
        "category": {
          "id": "cat-utilities",
          "name": "Utilities"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-35.00"
      },
      {
        "id": "txn-2026-07-14-transport",
        "date": "2026-07-14",
        "description": "Weekend trip train tickets",
        "category": {
          "id": "cat-transport",
          "name": "Transport"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-128.00"
      },
      {
        "id": "txn-2026-07-13-dining",
        "date": "2026-07-13",
        "description": "Pizza night",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-38.50"
      },
      {
        "id": "txn-2026-07-11-groceries",
        "date": "2026-07-11",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-92.15"
      }
    ]
  },
  "2026-08": {
    "month": "2026-08",
    "currency": "EUR",
    "availableMonths": [
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11"
    ],
    "summary": {
      "income": "3250.00",
      "expenses": "1687.85",
      "net": "1562.15",
      "savingsRate": "48.1"
    },
    "trend": [
      {
        "month": "2026-07",
        "income": "2800.00",
        "expenses": "1814.90"
      },
      {
        "month": "2026-08",
        "income": "3250.00",
        "expenses": "1687.85"
      },
      {
        "month": "2026-09",
        "income": "2800.00",
        "expenses": "1785.59"
      },
      {
        "month": "2026-10",
        "income": "3100.00",
        "expenses": "1640.05"
      },
      {
        "month": "2026-11",
        "income": "3180.00",
        "expenses": "1733.60"
      }
    ],
    "categories": [
      {
        "id": "cat-housing",
        "name": "Housing",
        "total": "950.00"
      },
      {
        "id": "cat-groceries",
        "name": "Groceries",
        "total": "352.40"
      },
      {
        "id": "cat-dining",
        "name": "Dining out",
        "total": "187.50"
      },
      {
        "id": "cat-utilities",
        "name": "Utilities",
        "total": "109.20"
      },
      {
        "id": "cat-transport",
        "name": "Transport",
        "total": "45.00"
      },
      {
        "id": "cat-entertainment",
        "name": "Entertainment",
        "total": "24.00"
      },
      {
        "id": "cat-health",
        "name": "Health",
        "total": "19.75"
      }
    ],
    "recentTransactions": [
      {
        "id": "txn-2026-08-27-dining",
        "date": "2026-08-27",
        "description": "Lunch with friends",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-52.60"
      },
      {
        "id": "txn-2026-08-25-groceries",
        "date": "2026-08-25",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-94.95"
      },
      {
        "id": "txn-2026-08-22-health",
        "date": "2026-08-22",
        "description": "Pharmacy",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-19.75"
      },
      {
        "id": "txn-2026-08-20-entertainment",
        "date": "2026-08-20",
        "description": "Cinema",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-24.00"
      },
      {
        "id": "txn-2026-08-18-groceries",
        "date": "2026-08-18",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-78.90"
      },
      {
        "id": "txn-2026-08-16-dining",
        "date": "2026-08-16",
        "description": "Beach holiday dinner",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-96.40"
      },
      {
        "id": "txn-2026-08-15-utilities",
        "date": "2026-08-15",
        "description": "Internet",
        "category": {
          "id": "cat-utilities",
          "name": "Utilities"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-35.00"
      },
      {
        "id": "txn-2026-08-13-dining",
        "date": "2026-08-13",
        "description": "Pizza night",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-38.50"
      },
      {
        "id": "txn-2026-08-11-groceries",
        "date": "2026-08-11",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-92.15"
      },
      {
        "id": "txn-2026-08-09-income",
        "date": "2026-08-09",
        "description": "Freelance website",
        "category": {
          "id": "cat-income",
          "name": "Income"
        },
        "account": {
          "id": "acc-sav",
          "name": "Savings"
        },
        "amount": "450.00"
      }
    ]
  },
  "2026-09": {
    "month": "2026-09",
    "currency": "EUR",
    "availableMonths": [
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11"
    ],
    "summary": {
      "income": "2800.00",
      "expenses": "1785.59",
      "net": "1014.41",
      "savingsRate": "36.2"
    },
    "trend": [
      {
        "month": "2026-07",
        "income": "2800.00",
        "expenses": "1814.90"
      },
      {
        "month": "2026-08",
        "income": "3250.00",
        "expenses": "1687.85"
      },
      {
        "month": "2026-09",
        "income": "2800.00",
        "expenses": "1785.59"
      },
      {
        "month": "2026-10",
        "income": "3100.00",
        "expenses": "1640.05"
      },
      {
        "month": "2026-11",
        "income": "3180.00",
        "expenses": "1733.60"
      }
    ],
    "categories": [
      {
        "id": "cat-housing",
        "name": "Housing",
        "total": "950.00"
      },
      {
        "id": "cat-groceries",
        "name": "Groceries",
        "total": "361.55"
      },
      {
        "id": "cat-health",
        "name": "Health",
        "total": "139.75"
      },
      {
        "id": "cat-utilities",
        "name": "Utilities",
        "total": "109.20"
      },
      {
        "id": "cat-dining",
        "name": "Dining out",
        "total": "91.10"
      },
      {
        "id": "cat-entertainment",
        "name": "Entertainment",
        "total": "88.99"
      },
      {
        "id": "cat-transport",
        "name": "Transport",
        "total": "45.00"
      }
    ],
    "recentTransactions": [
      {
        "id": "txn-2026-09-27-dining",
        "date": "2026-09-27",
        "description": "Lunch with friends",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-52.60"
      },
      {
        "id": "txn-2026-09-25-groceries",
        "date": "2026-09-25",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-104.10"
      },
      {
        "id": "txn-2026-09-22-health",
        "date": "2026-09-22",
        "description": "Pharmacy",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-19.75"
      },
      {
        "id": "txn-2026-09-21-health",
        "date": "2026-09-21",
        "description": "Dentist",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-120.00"
      },
      {
        "id": "txn-2026-09-20-entertainment",
        "date": "2026-09-20",
        "description": "Cinema",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-24.00"
      },
      {
        "id": "txn-2026-09-18-groceries",
        "date": "2026-09-18",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-78.90"
      },
      {
        "id": "txn-2026-09-15-utilities",
        "date": "2026-09-15",
        "description": "Internet",
        "category": {
          "id": "cat-utilities",
          "name": "Utilities"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-35.00"
      },
      {
        "id": "txn-2026-09-13-dining",
        "date": "2026-09-13",
        "description": "Pizza night",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-38.50"
      },
      {
        "id": "txn-2026-09-11-groceries",
        "date": "2026-09-11",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-92.15"
      },
      {
        "id": "txn-2026-09-08-transport",
        "date": "2026-09-08",
        "description": "Monthly bus pass",
        "category": {
          "id": "cat-transport",
          "name": "Transport"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-45.00"
      }
    ]
  },
  "2026-10": {
    "month": "2026-10",
    "currency": "EUR",
    "availableMonths": [
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11"
    ],
    "summary": {
      "income": "3100.00",
      "expenses": "1640.05",
      "net": "1459.95",
      "savingsRate": "47.1"
    },
    "trend": [
      {
        "month": "2026-07",
        "income": "2800.00",
        "expenses": "1814.90"
      },
      {
        "month": "2026-08",
        "income": "3250.00",
        "expenses": "1687.85"
      },
      {
        "month": "2026-09",
        "income": "2800.00",
        "expenses": "1785.59"
      },
      {
        "month": "2026-10",
        "income": "3100.00",
        "expenses": "1640.05"
      },
      {
        "month": "2026-11",
        "income": "3180.00",
        "expenses": "1733.60"
      }
    ],
    "categories": [
      {
        "id": "cat-housing",
        "name": "Housing",
        "total": "950.00"
      },
      {
        "id": "cat-groceries",
        "name": "Groceries",
        "total": "368.20"
      },
      {
        "id": "cat-utilities",
        "name": "Utilities",
        "total": "109.20"
      },
      {
        "id": "cat-dining",
        "name": "Dining out",
        "total": "91.10"
      },
      {
        "id": "cat-transport",
        "name": "Transport",
        "total": "77.80"
      },
      {
        "id": "cat-entertainment",
        "name": "Entertainment",
        "total": "24.00"
      },
      {
        "id": "cat-health",
        "name": "Health",
        "total": "19.75"
      }
    ],
    "recentTransactions": [
      {
        "id": "txn-2026-10-27-dining",
        "date": "2026-10-27",
        "description": "Lunch with friends",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-52.60"
      },
      {
        "id": "txn-2026-10-25-groceries",
        "date": "2026-10-25",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-110.75"
      },
      {
        "id": "txn-2026-10-24-transport",
        "date": "2026-10-24",
        "description": "Car share",
        "category": {
          "id": "cat-transport",
          "name": "Transport"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-32.80"
      },
      {
        "id": "txn-2026-10-22-health",
        "date": "2026-10-22",
        "description": "Pharmacy",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-19.75"
      },
      {
        "id": "txn-2026-10-20-entertainment",
        "date": "2026-10-20",
        "description": "Cinema",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-24.00"
      },
      {
        "id": "txn-2026-10-18-groceries",
        "date": "2026-10-18",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-78.90"
      },
      {
        "id": "txn-2026-10-15-utilities",
        "date": "2026-10-15",
        "description": "Internet",
        "category": {
          "id": "cat-utilities",
          "name": "Utilities"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-35.00"
      },
      {
        "id": "txn-2026-10-13-dining",
        "date": "2026-10-13",
        "description": "Pizza night",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-38.50"
      },
      {
        "id": "txn-2026-10-11-groceries",
        "date": "2026-10-11",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-92.15"
      },
      {
        "id": "txn-2026-10-10-income",
        "date": "2026-10-10",
        "description": "Freelance logo design",
        "category": {
          "id": "cat-income",
          "name": "Income"
        },
        "account": {
          "id": "acc-sav",
          "name": "Savings"
        },
        "amount": "300.00"
      }
    ]
  },
  "2026-11": {
    "month": "2026-11",
    "currency": "EUR",
    "availableMonths": [
      "2026-07",
      "2026-08",
      "2026-09",
      "2026-10",
      "2026-11"
    ],
    "summary": {
      "income": "3180.00",
      "expenses": "1733.60",
      "net": "1446.40",
      "savingsRate": "45.5"
    },
    "trend": [
      {
        "month": "2026-07",
        "income": "2800.00",
        "expenses": "1814.90"
      },
      {
        "month": "2026-08",
        "income": "3250.00",
        "expenses": "1687.85"
      },
      {
        "month": "2026-09",
        "income": "2800.00",
        "expenses": "1785.59"
      },
      {
        "month": "2026-10",
        "income": "3100.00",
        "expenses": "1640.05"
      },
      {
        "month": "2026-11",
        "income": "3180.00",
        "expenses": "1733.60"
      }
    ],
    "categories": [
      {
        "id": "cat-housing",
        "name": "Housing",
        "total": "950.00"
      },
      {
        "id": "cat-groceries",
        "name": "Groceries",
        "total": "355.55"
      },
      {
        "id": "cat-entertainment",
        "name": "Entertainment",
        "total": "163.00"
      },
      {
        "id": "cat-utilities",
        "name": "Utilities",
        "total": "109.20"
      },
      {
        "id": "cat-dining",
        "name": "Dining out",
        "total": "91.10"
      },
      {
        "id": "cat-transport",
        "name": "Transport",
        "total": "45.00"
      },
      {
        "id": "cat-health",
        "name": "Health",
        "total": "19.75"
      }
    ],
    "recentTransactions": [
      {
        "id": "txn-2026-11-27-dining",
        "date": "2026-11-27",
        "description": "Lunch with friends",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-52.60"
      },
      {
        "id": "txn-2026-11-25-groceries",
        "date": "2026-11-25",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-98.10"
      },
      {
        "id": "txn-2026-11-22-health",
        "date": "2026-11-22",
        "description": "Pharmacy",
        "category": {
          "id": "cat-health",
          "name": "Health"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-19.75"
      },
      {
        "id": "txn-2026-11-20-entertainment",
        "date": "2026-11-20",
        "description": "Cinema",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-24.00"
      },
      {
        "id": "txn-2026-11-18-groceries",
        "date": "2026-11-18",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-78.90"
      },
      {
        "id": "txn-2026-11-15-utilities",
        "date": "2026-11-15",
        "description": "Internet",
        "category": {
          "id": "cat-utilities",
          "name": "Utilities"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-35.00"
      },
      {
        "id": "txn-2026-11-13-dining",
        "date": "2026-11-13",
        "description": "Pizza night",
        "category": {
          "id": "cat-dining",
          "name": "Dining out"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-38.50"
      },
      {
        "id": "txn-2026-11-11-groceries",
        "date": "2026-11-11",
        "description": "Supermarket",
        "category": {
          "id": "cat-groceries",
          "name": "Groceries"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-92.15"
      },
      {
        "id": "txn-2026-11-09-entertainment",
        "date": "2026-11-09",
        "description": "Winter jacket",
        "category": {
          "id": "cat-entertainment",
          "name": "Entertainment"
        },
        "account": {
          "id": "acc-cc",
          "name": "Credit card"
        },
        "amount": "-139.00"
      },
      {
        "id": "txn-2026-11-08-transport",
        "date": "2026-11-08",
        "description": "Monthly bus pass",
        "category": {
          "id": "cat-transport",
          "name": "Transport"
        },
        "account": {
          "id": "acc-chk",
          "name": "Checking"
        },
        "amount": "-45.00"
      }
    ]
  }
}

export function emptyDashboard(month) {
  return {
    month,
    currency: 'EUR',
    availableMonths: FIXTURE_MONTHS,
    summary: { income: '0.00', expenses: '0.00', net: '0.00', savingsRate: null },
    trend: [],
    categories: [],
    recentTransactions: [],
  }
}
