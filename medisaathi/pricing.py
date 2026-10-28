
import math
from itertools import product


MIN_SPLIT_SAVINGS = 30.0


def calculate_packs_needed(required_units, pack_size):
    """Calculate the number of whole packs required."""
    if required_units <= 0:
        raise ValueError("Required units must be greater than zero.")
    if pack_size <= 0:
        raise ValueError("Pack size must be greater than zero.")

    return math.ceil(required_units / pack_size)


def calculate_item_cost(required_units, pack_size, pack_price):
    """Calculate the cost of buying enough whole packs."""
    if pack_price < 0:
        raise ValueError("Pack price cannot be negative.")

    packs_needed = calculate_packs_needed(required_units, pack_size)

    return {
        "required_units": required_units,
        "pack_size": pack_size,
        "packs_needed": packs_needed,
        "total_units_purchased": packs_needed * pack_size,
        "pack_price": round(pack_price, 2),
        "total_cost": round(packs_needed * pack_price, 2),
    }


def calculate_delivery_cost(
    basket_subtotal,
    delivery_fee,
    free_delivery_threshold,
):
    """Calculate delivery charges for one pharmacy."""
    if basket_subtotal < 0:
        raise ValueError("Basket subtotal cannot be negative.")
    if delivery_fee < 0:
        raise ValueError("Delivery fee cannot be negative.")
    if free_delivery_threshold < 0:
        raise ValueError("Free-delivery threshold cannot be negative.")

    if basket_subtotal >= free_delivery_threshold:
        return 0.0

    return round(delivery_fee, 2)


def calculate_pharmacy_total(
    basket_subtotal,
    delivery_fee,
    free_delivery_threshold,
):
    """Calculate subtotal, delivery fee and final total."""
    delivery_cost = calculate_delivery_cost(
        basket_subtotal,
        delivery_fee,
        free_delivery_threshold,
    )

    return {
        "basket_subtotal": round(basket_subtotal, 2),
        "delivery_cost": delivery_cost,
        "total_cost": round(basket_subtotal + delivery_cost, 2),
    }


def compare_pharmacies(basket_subtotals, pharmacy_settings):
    """Rank complete single-pharmacy baskets by final cost."""
    results = []

    for pharmacy, subtotal in basket_subtotals.items():
        if pharmacy not in pharmacy_settings:
            continue

        settings = pharmacy_settings[pharmacy]
        total = calculate_pharmacy_total(
            subtotal,
            settings["delivery_fee"],
            settings["free_delivery_threshold"],
        )

        results.append({"pharmacy": pharmacy, **total})

    results.sort(key=lambda item: item["total_cost"])

    return {
        "ranked_pharmacies": results,
        "cheapest": results[0] if results else None,
    }


def _calculate_basket(items, assignments, pharmacy_settings):
    """Calculate item costs and delivery fees for one assignment."""
    subtotals = {}
    item_details = []
    used_pharmacies = set()

    for item, pharmacy in zip(items, assignments):
        if pharmacy not in item.get("prices", {}):
            return None

        price = item["prices"][pharmacy]
        item_cost = calculate_item_cost(
            required_units=item["required_units"],
            pack_size=price["pack_size"],
            pack_price=price["pack_price"],
        )

        subtotals[pharmacy] = (
            subtotals.get(pharmacy, 0) + item_cost["total_cost"]
        )
        used_pharmacies.add(pharmacy)

        item_details.append({
            "catalog_id": item.get("catalog_id"),
            "medicine": item["name"],
            "pharmacy": pharmacy,
            **item_cost,
        })

    pharmacy_totals = {}
    delivery_total = 0.0

    for pharmacy, subtotal in subtotals.items():
        settings = pharmacy_settings[pharmacy]
        result = calculate_pharmacy_total(
            subtotal,
            settings["delivery_fee"],
            settings["free_delivery_threshold"],
        )
        pharmacy_totals[pharmacy] = result
        delivery_total += result["delivery_cost"]

    medicine_subtotal = round(sum(subtotals.values()), 2)

    return {
        "pharmacies_used": sorted(used_pharmacies),
        "items": item_details,
        "pharmacy_totals": pharmacy_totals,
        "medicine_subtotal": medicine_subtotal,
        "delivery_total": round(delivery_total, 2),
        "total_cost": round(medicine_subtotal + delivery_total, 2),
    }


def optimize_basket(
    items,
    pharmacy_settings,
    min_split_savings=MIN_SPLIT_SAVINGS,
):
    """
    Compare the best single-pharmacy basket with a two-pharmacy split.

    Each item contains:
        name
        required_units
        prices: pharmacy -> pack_size and pack_price

    Each pharmacy setting contains delivery_fee and
    free_delivery_threshold.
    """
    if not items:
        raise ValueError("At least one basket item is required.")
    if min_split_savings < 0:
        raise ValueError("Minimum split savings cannot be negative.")

    for item in items:
        if item.get("required_units", 0) <= 0:
            raise ValueError(
                "Every item must have required_units greater than zero."
            )
        if not item.get("name"):
            raise ValueError("Every item must have a name.")
        if not item.get("prices"):
            raise ValueError(
                f"No pharmacy prices supplied for {item.get('name')}."
            )

    available_pharmacies = sorted({
        pharmacy
        for item in items
        for pharmacy in item["prices"]
        if pharmacy in pharmacy_settings
    })

    if not available_pharmacies:
        raise ValueError(
            "No pharmacies have both price data and delivery settings."
        )

    # Find the cheapest complete basket from one pharmacy.
    single_options = []

    for pharmacy in available_pharmacies:
        if all(pharmacy in item["prices"] for item in items):
            result = _calculate_basket(
                items,
                [pharmacy] * len(items),
                pharmacy_settings,
            )
            if result is not None:
                result["type"] = "single"
                result["pharmacy"] = pharmacy
                single_options.append(result)

    single_options.sort(key=lambda result: result["total_cost"])
    best_single = single_options[0] if single_options else None

    # Try every assignment across two different pharmacies.
    best_split = None

    for pharmacy_a, pharmacy_b in product(
        available_pharmacies, repeat=2
    ):
        if pharmacy_a >= pharmacy_b:
            continue

        for assignments in product(
            [pharmacy_a, pharmacy_b], repeat=len(items)
        ):
            if len(set(assignments)) != 2:
                continue

            result = _calculate_basket(
                items,
                assignments,
                pharmacy_settings,
            )

            if result is None:
                continue

            result["type"] = "split"

            if (
                best_split is None
                or result["total_cost"] < best_split["total_cost"]
            ):
                best_split = result

    split_savings = None
    recommend_split = False

    if best_single is not None and best_split is not None:
        split_savings = round(
            best_single["total_cost"] - best_split["total_cost"],
            2,
        )
        recommend_split = split_savings >= min_split_savings

    recommended = best_single

    if recommend_split:
        recommended = best_split

    most_expensive_single = (
        max(single_options, key=lambda result: result["total_cost"])
        if single_options
        else None
    )

    savings_vs_most_expensive = None
    if most_expensive_single is not None and recommended is not None:
        savings_vs_most_expensive = round(
            most_expensive_single["total_cost"]
            - recommended["total_cost"],
            2,
        )

    return {
        "best_single": best_single,
        "best_split": best_split,
        "split_savings": split_savings,
        "minimum_split_savings": round(min_split_savings, 2),
        "recommend_split": recommend_split,
        "recommended": recommended,
        "most_expensive_single": most_expensive_single,
        "savings_vs_most_expensive": savings_vs_most_expensive,
    }


def optimize_catalog_basket(
    medicines,
    price_records,
    pharmacy_settings,
    min_split_savings=MIN_SPLIT_SAVINGS,
):
    """
    Build a basket using catalog IDs and required total units, then
    pass it to the price optimizer.

    medicines:
        [{"catalog_id": "MED001", "total_units": 20, "name": "Dolo 650"}]

    price_records:
        Rows with catalog_id, pharmacy, pack_size and price_inr.
        These can come from the shared price sheet.

    pharmacy_settings:
        Pharmacy names mapped to delivery_fee and
        free_delivery_threshold.

    Medicines without collected pharmacy prices are excluded from
    optimization. Check the returned excluded_medicines list.
    """
    if not medicines:
        raise ValueError("At least one medicine is required.")

    prices_by_catalog = {}

    for record in price_records:
        catalog_id = record.get("catalog_id")
        pharmacy = record.get("pharmacy")

        if not catalog_id or not pharmacy:
            continue
        if pharmacy not in pharmacy_settings:
            continue

        pack_size = int(record["pack_size"])
        pack_price = float(record["price_inr"])

        if pack_size <= 0:
            raise ValueError("Price records must have a positive pack_size.")
        if pack_price < 0:
            raise ValueError("Price records cannot have negative prices.")

        prices_by_catalog.setdefault(catalog_id, {})
        prices_by_catalog[catalog_id][pharmacy] = {
            "pack_size": pack_size,
            "pack_price": pack_price,
        }

    basket_items = []
    excluded_medicines = []

    for medicine in medicines:
        catalog_id = medicine.get("catalog_id")
        total_units = medicine.get("total_units")

        if not catalog_id:
            raise ValueError("Every medicine needs a catalog_id.")
        if total_units is None or total_units <= 0:
            raise ValueError(
                f"Medicine {catalog_id} needs positive total_units."
            )

        available_prices = prices_by_catalog.get(catalog_id, {})

        if not available_prices:
            excluded_medicines.append({
                "catalog_id": catalog_id,
                "name": medicine.get("name", catalog_id),
                "message": (
                    "Reference MRP only, pharmacy prices not available"
                ),
            })
            continue

        basket_items.append({
            "catalog_id": catalog_id,
            "name": medicine.get("name", catalog_id),
            "required_units": total_units,
            "prices": available_prices,
        })

    result = None
    if basket_items:
        result = optimize_basket(
            basket_items,
            pharmacy_settings,
            min_split_savings=min_split_savings,
        )

    return {
        "basket": result,
        "excluded_medicines": excluded_medicines,
    }
