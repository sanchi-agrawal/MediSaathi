
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parent / "data"

MEDICINES_FILE = DATA_DIR / "medicines.csv"
PHARMACIES_FILE = DATA_DIR / "pharmacies.csv"
PRICES_FILE = DATA_DIR / "pharmacy_prices.csv"

REQUIRED_PRICE_COLUMNS = {
    "catalog_id",
    "brand",
    "pack_size",
    "pharmacy",
    "price_inr",
    "collected_on",
    "pincode",
    "screenshot_link",
}


def load_medicines():
    """Load the medicine catalog."""
    return pd.read_csv(MEDICINES_FILE).fillna("")


def load_pharmacy_settings():
    """Load delivery fees and free-delivery thresholds."""
    df = pd.read_csv(PHARMACIES_FILE)

    required = {
        "pharmacy",
        "delivery_fee",
        "free_delivery_threshold",
    }
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"pharmacies.csv is missing columns: {sorted(missing)}"
        )

    settings = {}

    for _, row in df.iterrows():
        settings[row["pharmacy"]] = {
            "delivery_fee": float(row["delivery_fee"]),
            "free_delivery_threshold": float(
                row["free_delivery_threshold"]
            ),
        }

    return settings


def load_pharmacy_prices():
    """Load collected prices without inventing missing values."""
    df = pd.read_csv(PRICES_FILE)

    missing = REQUIRED_PRICE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"pharmacy_prices.csv is missing columns: "
            f"{sorted(missing)}"
        )

    if df.empty:
        return []

    # Do not use rows that lack essential price information.
    essential = ["catalog_id", "pack_size", "pharmacy", "price_inr"]
    df = df.dropna(subset=essential)

    df = df[
        (df["catalog_id"].astype(str).str.strip() != "")
        & (df["pharmacy"].astype(str).str.strip() != "")
    ]

    df["pack_size"] = pd.to_numeric(df["pack_size"], errors="coerce")
    df["price_inr"] = pd.to_numeric(df["price_inr"], errors="coerce")

    df = df.dropna(subset=["pack_size", "price_inr"])
    df = df[(df["pack_size"] > 0) & (df["price_inr"] >= 0)]

    return df.to_dict(orient="records")
