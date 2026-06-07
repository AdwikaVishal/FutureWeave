import logging
import os

from data_grounding import normalise_location

from .common import ProviderResult, fetch_json

logger = logging.getLogger("futureweave.data")


async def fetch_cost_of_living(location: str) -> ProviderResult:
    api_key = os.environ.get("NUMBEO_API_KEY")
    city = normalise_location(location)

    if city == "India" or not city:
        return ProviderResult(
            provider="numbeo",
            dataset="cost_of_living",
            available=False,
            error=f"Cannot determine city for location: {location}",
        )

    if not api_key:
        return ProviderResult(
            provider="numbeo",
            dataset="cost_of_living",
            available=False,
            error="NUMBEO_API_KEY is not configured",
        )

    result = await fetch_json(
        "numbeo",
        "cost_of_living",
        "https://www.numbeo.com/api/city_prices",
        params={"api_key": api_key, "query": city, "currency": "INR"},
    )
    if not result.available:
        return result

    prices = result.data.get("prices") or []
    if not prices:
        result.available = False
        result.error = "Numbeo response had no prices"
        return result

    rent_items = []
    grocery_items = []
    transport_items = []
    utility_items = []

    for item in prices:
        name = (item.get("item_name") or "").lower()
        price = item.get("average_price") or item.get("price")
        if price is None:
            continue
        avg = float(price)
        if any(k in name for k in ["rent", "apartment", "flat", "house"]):
            rent_items.append({"name": name, "price": avg})
        elif any(k in name for k in ["milk", "bread", "rice", "egg", "chicken", "vegetable", "fruit", "meat", "cheese", " Tomato", "Potato"]):
            grocery_items.append({"name": name, "price": avg})
        elif any(k in name for k in ["transport", "bus", "train", "taxi", "fuel", "petrol", "gasoline"]):
            transport_items.append({"name": name, "price": avg})
        elif any(k in name for k in ["electricity", "water", "gas", "internet", "phone", "mobile"]):
            utility_items.append({"name": name, "price": avg})

    parsed_data = {
        "location": city,
        "prices": prices,
        "categories": {
            "rent": rent_items,
            "groceries": grocery_items,
            "transport": transport_items,
            "utilities": utility_items,
        },
        "summary": {
            "total_items": len(prices),
            "rent_items": len(rent_items),
            "grocery_items": len(grocery_items),
            "transport_items": len(transport_items),
            "utility_items": len(utility_items),
        },
        "source": "numbeo",
        "api_key_configured": True,
    }

    logger.info(
        "[LIVE_DATA] Source=Numbeo Status=200 Location=%s Items=%d Rents=%d Groceries=%d Transport=%d Utilities=%d",
        city, len(prices), len(rent_items), len(grocery_items), len(transport_items), len(utility_items),
    )

    result.data = parsed_data
    return result
