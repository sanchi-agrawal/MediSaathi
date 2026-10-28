
"""Find lower-priced alternatives with matching medicine details."""

from pricing import calculate_item_cost


SWITCHING_DISCLAIMER = (
    "Ask your doctor or pharmacist before switching."
)


def find_cheaper_alternatives(
    selected_medicine,
    selected_unit_price,
    catalog,
    price_records,
):
    """Find alternatives with the same salt, strength and form.

    Only alternatives with a lower unit price are returned.
    This function does not recommend changing a prescribed medicine.
    """
    if not isinstance(selected_medicine, dict):
        raise TypeError("selected_medicine must be a dictionary")

    if not isinstance(catalog, list):
        raise TypeError("catalog must be a list")

    if not isinstance(price_records, list):
        raise TypeError("price_records must be a list")

    if selected_unit_price < 0:
        raise ValueError("selected_unit_price cannot be negative")

    required_fields = ("salt", "strength", "form")
    selected_details = {}

    for field in required_fields:
        value = selected_medicine.get(field)
        if not value:
            return []

        selected_details[field] = str(value).strip().casefold()

    alternatives = []

    for item in catalog:
        if not isinstance(item, dict):
            continue

        if item.get("catalog_id") == selected_medicine.get("catalog_id"):
            continue

        if any(
            not item.get(field)
            or str(item[field]).strip().casefold()
            != selected_details[field]
            for field in required_fields
        ):
            continue

        matching_prices = [
            record
            for record in price_records
            if record.get("catalog_id") == item.get("catalog_id")
            and record.get("pack_size")
            and record.get("price_inr") is not None
        ]

        if not matching_prices:
            continue

        pack_size = int(item.get("pack_size", 0))
        if pack_size <= 0:
            continue

        for record in matching_prices:
            pack_price = float(record["price_inr"])
            if pack_price < 0:
                continue

            unit_price = pack_price / int(record.get("pack_size", pack_size))

            if unit_price >= selected_unit_price:
                continue

            alternatives.append({
                "catalog_id": item.get("catalog_id"),
                "name": item.get("brand") or item.get("name"),
                "salt": item.get("salt"),
                "strength": item.get("strength"),
                "form": item.get("form"),
                "pharmacy": record.get("pharmacy"),
                "pack_size": int(record.get("pack_size", pack_size)),
                "pack_price": round(pack_price, 2),
                "unit_price": round(unit_price, 2),
                "disclaimer": SWITCHING_DISCLAIMER,
            })

    alternatives.sort(key=lambda item: item["unit_price"])
    return alternatives
