
from pricing import (
    calculate_packs_needed,
    calculate_item_cost,
    calculate_delivery_cost,
    calculate_pharmacy_total,
    compare_pharmacies,
    optimize_basket,
)


# Test 1: Exact number of packs
assert calculate_packs_needed(20, 10) == 2
print("Test 1 passed: Exact packs")


# Test 2: Round up for partial packs
assert calculate_packs_needed(20, 15) == 2
print("Test 2 passed: Partial pack rounded up")


# Test 3: Calculate medicine cost
result = calculate_item_cost(20, 15, 30)

assert result["packs_needed"] == 2
assert result["total_units_purchased"] == 30
assert result["total_cost"] == 60
print("Test 3 passed: Item cost")


# Test 4: Reject invalid pack size
try:
    calculate_packs_needed(20, 0)
    raise AssertionError("Zero pack size should raise ValueError")
except ValueError:
    print("Test 4 passed: Invalid pack size rejected")


# Test 5: Delivery fee below threshold
assert calculate_delivery_cost(400, 30, 499) == 30
print("Test 5 passed: Delivery fee applied")


# Test 6: Free delivery at threshold
assert calculate_delivery_cost(499, 30, 499) == 0
print("Test 6 passed: Free delivery at threshold")


# Test 7: Complete pharmacy total
result = calculate_pharmacy_total(400, 30, 499)

assert result["basket_subtotal"] == 400
assert result["delivery_cost"] == 30
assert result["total_cost"] == 430
print("Test 7 passed: Pharmacy total")


# Test 8: Cheapest single-pharmacy comparison
subtotals = {
    "Pharmacy A": 400,
    "Pharmacy B": 450,
    "Pharmacy C": 550,
}

settings = {
    "Pharmacy A": {
        "delivery_fee": 30,
        "free_delivery_threshold": 499,
    },
    "Pharmacy B": {
        "delivery_fee": 20,
        "free_delivery_threshold": 399,
    },
    "Pharmacy C": {
        "delivery_fee": 40,
        "free_delivery_threshold": 599,
    },
}

result = compare_pharmacies(subtotals, settings)

assert result["cheapest"]["pharmacy"] == "Pharmacy A"
assert result["cheapest"]["total_cost"] == 430
print("Test 8 passed: Cheapest pharmacy comparison")


# Test 9: Split basket saves more than the minimum
basket_items = [
    {
        "name": "Medicine A",
        "required_units": 1,
        "prices": {
            "Pharmacy A": {"pack_size": 1, "pack_price": 100},
            "Pharmacy B": {"pack_size": 1, "pack_price": 60},
        },
    },
    {
        "name": "Medicine B",
        "required_units": 1,
        "prices": {
            "Pharmacy A": {"pack_size": 1, "pack_price": 60},
            "Pharmacy B": {"pack_size": 1, "pack_price": 100},
        },
    },
]

split_settings = {
    "Pharmacy A": {
        "delivery_fee": 0,
        "free_delivery_threshold": 0,
    },
    "Pharmacy B": {
        "delivery_fee": 0,
        "free_delivery_threshold": 0,
    },
}

result = optimize_basket(
    basket_items,
    split_settings,
    min_split_savings=30,
)

assert result["best_single"]["total_cost"] == 160
assert result["best_split"]["total_cost"] == 120
assert result["split_savings"] == 40
assert result["recommend_split"] is True
assert result["recommended"]["type"] == "split"

print("Test 9 passed: Split basket saves Rs. 40")


# Test 10: Split must save at least Rs. 30
result = optimize_basket(
    basket_items,
    split_settings,
    min_split_savings=50,
)

assert result["split_savings"] == 40
assert result["recommend_split"] is False
assert result["recommended"]["type"] == "single"

print("Test 10 passed: Minimum savings rule")


print("\nAll ten pricing tests passed!")
