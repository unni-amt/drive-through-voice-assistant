from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

COMMON_INSTRUCTIONS = (
    "You are saanvi, a quick and friendly attendant at 'Spice Route', a popular Indian fast-casual restaurant. \n"
    "Your job is to guide the customer smoothly through their order, speaking in short, natural voice responses. \n"
    "This is a voice interaction-assume the customer just pulled up and is speaking to you through a drive-thru speaker. \n"
    "Respond like you're hearing them, not reading text. \n"
    "Assume they want food, even if they don’t start with a clear request, and help them get what they’re looking for. \n"
    "\n\n"
    "If an item comes in different sizes, always ask for the size unless the customer already gave one. \n"
    "If a customer orders a 'large meal' or 'large thali', automatically assume the drink should be large as well. \n"
    "Do not ask again to confirm the size of the drink. This inference is meant to streamline the interaction. \n"
    "If the customer clearly indicates a different size for the drink, respect their preference. \n"
    "\n\n"
    "Be fast-keep responses short and snappy. \n"
    "Sound human-sprinkle in light vocal pauses like 'Mmh…', 'Let me see…', or 'Alright…' at natural moments-but not too often. \n"
    "Keep everything upbeat and easy to follow. Never overwhelm the customer, don't ask multiple questions at the same time. \n"
    "\n\n"
    "When a customer is confused or asks for something that doesn’t exist, let them know politely and suggest something close. \n"
    "Always confirm what they picked in a warm, clear way, like: 'Alright, one Butter Chicken Combo!' \n"
    "If something’s unavailable, say so with empathy: 'Ah, we're out of Mango Lassi right now-can I get you a Sweet Lassi instead?' \n"
    "\n\n"
    "Whenever a customer asks for, changes, or removes something from their order, you MUST use a tool to make it happen. \n"
    "Don’t fake it. Don’t pretend something was added - actually **call** the tool and make it real on the ordering system. \n"
    "\n\n"
    "Transcripts often contain speech-to-text errors-don’t mention the transcript, don’t repeat its mistakes. \n"
    "Instead treat each user input as a rough draft of what was said. \n"
    "If you can guess the user’s intent and it’s safe to do so, infer their meaning and respond naturally. \n"
    "If the transcript is ambiguous/nonsense and you can’t guess their intent, ask the customer to repeat again. \n"
    "Stay on-topic; if input is nonsensical in a drive-thru context, ask for concise clarification. \n"
    "\n\n"
    "Do not add any item on the user's behalf unless they specifically request it. If the user hasn't asked for an item, NEVER add it. \n"
    "\n\n"
    "When a customer changes an item or meal, make sure to remove the previous version before adding the new one. \n"
    "Otherwise, the order may contain duplicates. \n"
    "\n\n"
    "Stricly stick to the defined menu, Do not invent or suggest any new sizes or items. \n"
    "If the item specified by the user is unclear or not **exactly** on the menu, ask for clarification or say you don't have this specific item \n"
    "E.g: a paratha isn't a naan\n"
    "Do not ask for size unless the item has more than one size option specified. \n"
    "If an item does not require a size according to the menu, **NEVER** ask the customer to choose one or mention size at all. \n"
    "\n\n"
    "If there is any error from the tool, you should inform the customer and ask them to try again."
)


ItemSize = Literal["S", "M", "L"]
ItemCategory = Literal["drink", "combo_meal", "happy_meal", "regular", "sauce"]


class MenuItem(BaseModel):
    id: str
    name: str
    calories: int
    price: float
    available: bool
    size: ItemSize | None = None
    voice_alias: str | None = None
    category: ItemCategory


class FakeDB:
    async def list_drinks(self) -> list[MenuItem]:
        drink_data = [
            {
                "id": "thums_up",
                "name": "Thums Up®",
                "sizes": {
                    "S": {"calories": 150, "price": 40.00},
                    "M": {"calories": 200, "price": 50.00},
                    "L": {"calories": 280, "price": 60.00},
                },
            },
            {
                "id": "limca",
                "name": "Limca®",
                "sizes": {
                    "S": {"calories": 140, "price": 40.00},
                    "M": {"calories": 190, "price": 50.00},
                    "L": {"calories": 270, "price": 60.00},
                },
            },
            {
                "id": "mango_lassi",
                "name": "Mango Lassi",
                "sizes": {
                    "S": {"calories": 250, "price": 80.00},
                    "M": {"calories": 350, "price": 110.00},
                    "L": {"calories": 480, "price": 150.00},
                },
            },
            {
                "id": "sweet_lassi",
                "name": "Sweet Lassi",
                "sizes": {
                    "S": {"calories": 220, "price": 70.00},
                    "M": {"calories": 310, "price": 90.00},
                    "L": {"calories": 420, "price": 130.00},
                },
            },
            {
                "id": "salted_lassi",
                "name": "Salted Lassi",
                "sizes": {
                    "S": {"calories": 150, "price": 60.00},
                    "M": {"calories": 200, "price": 80.00},
                    "L": {"calories": 280, "price": 110.00},
                },
                "available": False,
            },
            {
                "id": "masala_chai",
                "name": "Masala Chai",
                "sizes": {
                    "S": {"calories": 120, "price": 30.00},
                    "M": {"calories": 180, "price": 50.00},
                    "L": {"calories": 240, "price": 70.00},
                },
            },
            {
                "id": "filter_coffee",
                "name": "Filter Coffee",
                "sizes": {
                    "S": {"calories": 100, "price": 40.00},
                    "M": {"calories": 150, "price": 60.00},
                    "L": {"calories": 200, "price": 80.00},
                },
            },
            {
                "id": "nimbu_pani",
                "name": "Fresh Nimbu Pani",
                "sizes": {
                    "S": {"calories": 90, "price": 40.00},
                    "M": {"calories": 140, "price": 60.00},
                    "L": {"calories": 190, "price": 80.00},
                },
            },
            {
                "id": "bottled_water",
                "name": "Kinley® Mineral Water",
                "calories": 0,
                "price": 20.00,
            },
        ]

        items = []
        for item in drink_data:
            if sizes := item.get("sizes", {}):
                for size, size_details in sizes.items():
                    items.append(
                        MenuItem(
                            id=item["id"],
                            name=item["name"],
                            calories=size_details["calories"],
                            price=size_details["price"],
                            size=size,
                            available=item.get("available", True),
                            category="drink",
                        )
                    )
            else:
                items.append(
                    MenuItem(
                        id=item["id"],
                        name=item["name"],
                        calories=item["calories"],
                        price=item["price"],
                        available=item.get("available", True),
                        category="drink",
                    )
                )

        return items

    async def list_combo_meals(self) -> list[MenuItem]:
        raw_meals = [
            {
                "id": "combo_butter_chicken",
                "name": "Butter Chicken Thali Combo",
                "alias": "1",
                "calories": 1250,
                "price": 350.00,
            },
            {
                "id": "combo_paneer_tikka_masala",
                "name": "Paneer Tikka Masala Thali Combo",
                "alias": "2",
                "calories": 1150,
                "price": 320.00,
            },
            {
                "id": "combo_chole_bhature",
                "name": "Chole Bhature Combo",
                "alias": "3",
                "calories": 980,
                "price": 220.00,
            },
            {
                "id": "combo_masala_dosa",
                "name": "Masala Dosa Combo",
                "alias": "4",
                "calories": 650,
                "price": 180.00,
            },
            {
                "id": "combo_chicken_biryani",
                "name": "Chicken Dum Biryani Combo",
                "alias": "5",
                "calories": 1100,
                "price": 340.00,
            },
            {
                "id": "combo_veg_biryani",
                "name": "Veg Biryani Combo",
                "alias": "6",
                "calories": 950,
                "price": 280.00,
            },
            {
                "id": "combo_samosa_chaat",
                "name": "Samosa Chaat & Chai Combo",
                "alias": "7",
                "calories": 620,
                "price": 150.00,
            },
            {
                "id": "combo_pav_bhaji",
                "name": "Mumbai Pav Bhaji Combo",
                "alias": "8",
                "calories": 850,
                "price": 190.00,
            },
        ]

        meals = []

        for item in raw_meals:
            meals.append(
                MenuItem(
                    id=item["id"],
                    name=item["name"],
                    calories=item["calories"],
                    price=item["price"],
                    voice_alias=item["alias"],
                    category="combo_meal",
                    available=True,
                )
            )

        return meals

    async def list_happy_meals(self) -> list[MenuItem]:
        raw_happy_meals = [
            {
                "id": "kids_mini_dosa",
                "name": "Mini Cheese Dosa Kid's Meal",
                "calories": 400,
                "price": 140.00,
            },
            {
                "id": "kids_butter_paneer",
                "name": "Kid's Butter Paneer & Rice Meal",
                "calories": 550,
                "price": 180.00,
            },
            {
                "id": "kids_sweet_pulao",
                "name": "Kid's Sweet Pulao Meal",
                "calories": 450,
                "price": 150.00,
            },
        ]

        meals = []

        for item in raw_happy_meals:
            meals.append(
                MenuItem(
                    id=item["id"],
                    name=item["name"],
                    calories=item["calories"],
                    price=item["price"],
                    available=True,
                    category="happy_meal",
                )
            )

        return meals

    async def list_regulars(self) -> list[MenuItem]:
        raw_items = [
            {
                "id": "samosa_2pc",
                "name": "Punjabi Samosa (2 pc)",
                "calories": 520,
                "price": 60.00,
            },
            {
                "id": "vada_pav",
                "name": "Vada Pav",
                "calories": 300,
                "price": 40.00,
            },
            {
                "id": "butter_naan",
                "name": "Butter Naan",
                "calories": 280,
                "price": 50.00,
            },
            {
                "id": "garlic_naan",
                "name": "Garlic Naan",
                "calories": 300,
                "price": 60.00,
            },
            {
                "id": "tandoori_roti",
                "name": "Tandoori Roti",
                "calories": 180,
                "price": 30.00,
            },
            {
                "id": "chicken_tikka_app",
                "name": "Chicken Tikka (6 pc)",
                "calories": 450,
                "price": 240.00,
            },
            {
                "id": "paneer_tikka_app",
                "name": "Paneer Tikka (6 pc)",
                "calories": 550,
                "price": 220.00,
            },
            {
                "id": "gulab_jamun",
                "name": "Gulab Jamun (2 pc)",
                "calories": 350,
                "price": 70.00,
            },
            {
                "id": "rasmalai",
                "name": "Rasmalai (2 pc)",
                "calories": 400,
                "price": 90.00,
            },
            {
                "id": "gajar_halwa",
                "name": "Gajar Ka Halwa",
                "calories": 450,
                "price": 110.00,
            },
        ]

        items = []
        for item in raw_items:
            if sizes := item.get("sizes", {}):
                for size, size_details in sizes.items():
                    items.append(
                        MenuItem(
                            id=item["id"],
                            name=item["name"],
                            calories=size_details["calories"],
                            price=size_details["price"],
                            size=size,
                            available=True,
                            category="regular",
                        )
                    )
            else:
                items.append(
                    MenuItem(
                        id=item["id"],
                        name=item["name"],
                        calories=item["calories"],
                        price=item["price"],
                        available=True,
                        category="regular",
                    )
                )

        return items

    async def list_sauces(self) -> list[MenuItem]:
        raw_items = [
            {
                "id": "mint_chutney",
                "name": "Mint Coriander Chutney",
                "calories": 25,
                "price": 15.00,
            },
            {
                "id": "tamarind_chutney",
                "name": "Sweet Tamarind Chutney",
                "calories": 60,
                "price": 15.00,
            },
            {
                "id": "garlic_chutney",
                "name": "Spicy Garlic Chutney",
                "calories": 40,
                "price": 15.00,
            },
            {
                "id": "boondi_raita",
                "name": "Boondi Raita",
                "calories": 120,
                "price": 40.00,
            },
            {
                "id": "mixed_pickle",
                "name": "Mixed Pickle (Achar)",
                "calories": 50,
                "price": 10.00,
            },
            {
                "id": "onion_salad",
                "name": "Lachha Onion Salad",
                "calories": 30,
                "price": 20.00,
            },
        ]
        sauces = []

        for item in raw_items:
            sauces.append(
                MenuItem(
                    id=item["id"],
                    name=item["name"],
                    calories=item["calories"],
                    price=item["price"],
                    available=True,
                    category="sauce",
                )
            )

        return sauces


# The code below is optimized for ease of use instead of efficiency.


def map_by_sizes(
    items: list[MenuItem],
) -> tuple[dict[str, dict[ItemSize, MenuItem]], list[MenuItem]]:
    result = defaultdict(dict)
    leftovers = [item for item in items if not item.size]
    [result[item.id].update({item.size: item}) for item in items if item.size]
    return dict(result), leftovers


def find_items_by_id(
    items: list[MenuItem], item_id: str, size: ItemSize | None = None
) -> list[MenuItem]:
    return [item for item in items if item.id == item_id and (size is None or item.size == size)]


def menu_instructions(category: ItemCategory, *, items: list[MenuItem]) -> str:
    if category == "drink":
        return _drink_menu_instructions(items)
    elif category == "combo_meal":
        return _combo_menu_instructions(items)
    elif category == "happy_meal":
        return _happy_menu_instructions(items)
    elif category == "sauce":
        return _sauce_menu_instructions(items)
    elif category == "regular":
        return _regular_menu_instructions(items)


def _drink_menu_instructions(items: list[MenuItem]) -> str:
    available_sizes, leftovers = map_by_sizes(items)
    menu_lines = []

    for _, size_map in available_sizes.items():
        first_item = next(iter(size_map.values()))
        menu_lines.append(f"  - {first_item.name} (id:{first_item.id}):")

        for item in size_map.values():
            line = f"    - Size {item.size}: {item.calories} Cal, ₹{item.price:.2f}"
            if not item.available:
                line += " UNAVAILABLE"
            menu_lines.append(line)

    for item in leftovers:
        # explicitely saying there is no `size` for this item, otherwise the LLM seems to hallucinate quite often
        line = f"  - {item.name}: {item.calories} Cal, ₹{item.price:.2f} (id:{item.id}) - Not size-selectable`"
        if not item.available:
            line += " UNAVAILABLE"
        menu_lines.append(line)

    return "# Drinks:\n" + "\n".join(menu_lines)


def _combo_menu_instructions(items: list[MenuItem]) -> str:
    menu_lines = []
    for item in items:
        line = f"  **{item.voice_alias}**. {item.name}: {item.calories} Cal, ₹{item.price:.2f} (id:{item.id})"

        if not item.available:
            line += " UNAVAILABLE"
        menu_lines.append(line)

    instructions = (
        "# Combo Meals / Thalis:\n"
        "The user can select a combo meal by saying its voice alias (e.g., '1', '2', '4'). Use the alias to identify which combo they chose.\n"
        "But don't mention the voice alias to the user if not needed."
    )
    return instructions + "\n".join(menu_lines)


def _happy_menu_instructions(items: list[MenuItem]) -> str:
    menu_lines = []
    for item in items:
        line = f"  - {item.name}: {item.calories} Cal, ₹{item.price:.2f} (id:{item.id})"
        if not item.available:
            line += " UNAVAILABLE"
        menu_lines.append(line)

    return (
        "# Kid's Meals:\n" + "\n".join(menu_lines) + "\n\nRecommended drinks with the Kid's Meal:\n"
        "  - Mango Lassi\n"
        "  - Bottled Water\n"
        "  - Or any other small drink."
    )


def _sauce_menu_instructions(items: list[MenuItem]) -> str:
    menu_lines = []
    for item in items:
        line = f"  - {item.name}: {item.calories} Cal, ₹{item.price:.2f} (id:{item.id})"
        if not item.available:
            line += " UNAVAILABLE"
        menu_lines.append(line)

    return "# Chutneys & Extras:\n" + "\n".join(menu_lines)


# regular/a la carte
def _regular_menu_instructions(items: list[MenuItem]) -> str:
    available_sizes, leftovers = map_by_sizes(items)
    menu_lines = []

    for _, size_map in available_sizes.items():
        first_item = next(iter(size_map.values()))
        menu_lines.append(f"  - {first_item.name} (id:{first_item.id}):")

        for item in size_map.values():
            line = f"    - Size {item.size}: {item.calories} Cal, ₹{item.price:.2f}"
            if not item.available:
                line += " UNAVAILABLE"
            menu_lines.append(line)

    for item in leftovers:
        line = f"  - {item.name}: {item.calories} Cal, ₹{item.price:.2f} (id:{item.id}) - Not size-selectable"
        if not item.available:
            line += " UNAVAILABLE"
        menu_lines.append(line)

    return "# Regular items/À la carte:\n" + "\n".join(menu_lines)