"""Static configuration: menu, seasonality, price experiment, paths.

All numbers here describe the *simulated* cafe. They are assumptions, not
observations of a real business, and are documented as such in the README.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "menuiq.db"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
MARTS_DIR = ROOT / "bi_marts"
SQL_DIR = ROOT / "sql"

SEED = 42
START_DATE = "2025-01-01"
END_DATE = "2025-12-31"
BASE_DAILY_ORDERS = 150
MONTHLY_GROWTH = 0.006  # organic growth per month

# name, category, price (INR), unit food cost (INR), base popularity weight
MENU = [
    ("Filter Coffee", "Coffee", 60, 18, 14),
    ("Cappuccino", "Coffee", 140, 34, 9),
    ("Cold Coffee", "Coffee", 160, 42, 8),
    ("Latte", "Coffee", 150, 36, 5),
    ("Espresso", "Coffee", 100, 22, 2),
    ("Masala Chai", "Tea", 40, 9, 18),
    ("Ginger Tea", "Tea", 45, 10, 6),
    ("Green Tea", "Tea", 70, 12, 2),
    ("Iced Lemon Tea", "Tea", 90, 20, 5),
    ("Fresh Lime Soda", "Cold Drinks", 70, 14, 5),
    ("Mango Shake", "Cold Drinks", 140, 52, 4),
    ("Oreo Shake", "Cold Drinks", 170, 62, 4),
    ("Cold Brew", "Cold Drinks", 180, 38, 1.5),
    ("Samosa", "Snacks", 25, 10, 12),
    ("Veg Puff", "Snacks", 35, 16, 7),
    ("Maggi", "Snacks", 80, 22, 8),
    ("French Fries", "Snacks", 110, 30, 6),
    ("Paneer Sandwich", "Snacks", 120, 46, 5),
    ("Veg Burger", "Snacks", 130, 50, 4),
    ("Veg Biryani", "Meals", 180, 78, 4),
    ("Chicken Biryani", "Meals", 240, 110, 4),
    ("Paneer Wrap", "Meals", 150, 58, 3),
    ("Chicken Wrap", "Meals", 170, 70, 2),
    ("Brownie", "Desserts", 110, 34, 3),
    ("Choco Lava", "Desserts", 140, 44, 2),
    ("Cookie", "Desserts", 50, 16, 4),
]

# Items often bought together (first item -> companions).
COMPANIONS = {
    "Masala Chai": ["Samosa", "Veg Puff", "Cookie"],
    "Ginger Tea": ["Samosa", "Veg Puff"],
    "Filter Coffee": ["Veg Puff", "Cookie"],
    "Cappuccino": ["Brownie", "Cookie", "Paneer Sandwich"],
    "Latte": ["Brownie", "Cookie"],
    "Cold Coffee": ["French Fries", "Veg Burger"],
    "Oreo Shake": ["French Fries", "Veg Burger"],
    "Maggi": ["Masala Chai", "Fresh Lime Soda"],
    "Veg Biryani": ["Fresh Lime Soda", "Masala Chai"],
    "Chicken Biryani": ["Fresh Lime Soda", "Cold Coffee"],
    "Paneer Wrap": ["Iced Lemon Tea", "French Fries"],
    "Chicken Wrap": ["Iced Lemon Tea", "French Fries"],
}

# Category demand multiplier by calendar month (1..12).
SEASONALITY = {
    "Coffee": [1.15, 1.10, 1.00, 0.90, 0.85, 0.95, 1.05, 1.05, 1.05, 1.05, 1.10, 1.20],
    "Tea": [1.20, 1.10, 0.95, 0.85, 0.80, 1.00, 1.15, 1.15, 1.10, 1.05, 1.10, 1.20],
    "Cold Drinks": [0.60, 0.75, 1.20, 1.60, 1.70, 1.20, 0.80, 0.80, 0.90, 0.90, 0.70, 0.60],
    "Snacks": [1.00, 1.00, 1.00, 0.95, 0.95, 1.05, 1.15, 1.15, 1.05, 1.00, 1.00, 1.00],
    "Meals": [1.00] * 12,
    "Desserts": [1.00, 1.05, 1.00, 0.95, 0.95, 0.95, 1.00, 1.00, 1.05, 1.15, 1.10, 1.10],
}
# Mango Shake is a summer item.
ITEM_SEASON_OVERRIDE = {"Mango Shake": [0.0, 0.2, 1.5, 2.5, 2.5, 1.2, 0.3, 0.1, 0.0, 0.0, 0.0, 0.0]}

# Hour-of-day order share (open 8:00-22:00 -> hours 8..21).
HOUR_WEIGHTS = {
    8: 5,
    9: 9,
    10: 8,
    11: 6,
    12: 9,
    13: 10,
    14: 6,
    15: 6,
    16: 9,
    17: 11,
    18: 10,
    19: 7,
    20: 5,
    21: 3,
}
# Category affinity by daypart: (hours, multiplier).
DAYPART_AFFINITY = {
    "Coffee": [((8, 9, 10, 11), 1.5), ((16, 17, 18), 1.1)],
    "Tea": [((8, 9, 10), 1.3), ((16, 17, 18, 19), 1.5)],
    "Cold Drinks": [((13, 14, 15), 1.3)],
    "Snacks": [((16, 17, 18, 19, 20), 1.4)],
    "Meals": [((12, 13, 14, 20, 21), 2.0)],
    "Desserts": [((19, 20, 21), 1.4)],
}

DOW_FACTOR = [0.92, 0.92, 0.95, 1.00, 1.08, 1.28, 1.25]  # Mon..Sun

# Festival / event days: date -> demand multiplier.
EVENT_DAYS = {
    "2025-01-14": 1.35,
    "2025-03-14": 1.30,
    "2025-04-06": 1.25,
    "2025-08-15": 1.40,
    "2025-08-27": 0.70,
    "2025-10-02": 0.65,
    "2025-10-20": 0.60,
    "2025-12-25": 1.30,
    "2025-12-31": 1.50,
}

# A controlled price change on 2025-07-01 with a *known* true elasticity.
# The pricing module tries to recover these without being told them.
PRICE_CHANGE_DATE = "2025-07-01"


@dataclass(frozen=True)
class PriceChange:
    item: str
    new_price: int
    true_elasticity: float


PRICE_CHANGES = [
    PriceChange("Masala Chai", 44, -0.5),
    PriceChange("Cappuccino", 154, -1.2),
    PriceChange("Brownie", 121, -1.6),
    PriceChange("Veg Puff", 39, -0.9),
]

CHANNELS = ["Dine-in", "Takeaway", "Delivery"]
CHANNEL_P = [0.55, 0.30, 0.15]
PAYMENTS = ["UPI", "Cash", "Card"]
PAYMENT_P = [0.62, 0.23, 0.15]

# Forecast settings.
FORECAST_HORIZON_DAYS = 7
CV_FOLDS = 4
CV_FOLD_DAYS = 28
