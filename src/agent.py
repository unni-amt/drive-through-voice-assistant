import json
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass
from typing import Annotated, Literal

from database import (
    COMMON_INSTRUCTIONS,
    FakeDB,
    MenuItem,
    find_items_by_id,
    menu_instructions,
)
from dotenv import load_dotenv
from order import OrderedCombo, OrderedHappy, OrderedRegular, OrderState
from pydantic import Field

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    FunctionTool,
    JobContext,
    RunContext,
    ToolError,
    cli,
    function_tool,
    inference,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")

logger = logging.getLogger("drive-thru")


@dataclass
class Userdata:
    order: OrderState
    drink_items: list[MenuItem]
    combo_items: list[MenuItem]
    happy_items: list[MenuItem]
    regular_items: list[MenuItem]
    sauce_items: list[MenuItem]


# --- ENRICHED RECEIPT WRITER ---
def update_receipt_file(userdata: Userdata):
    """Enriches the order with human-readable names and prices, then saves it."""
    # Combine all menus into one list so we can easily search for IDs
    all_menu_items = (
        userdata.combo_items + userdata.happy_items + 
        userdata.regular_items + userdata.drink_items + userdata.sauce_items
    )

    receipt_data = {
        "items": [],
        "total_price": 0.0
    }

    for item in userdata.order.items.values():
        receipt_item = {
            "order_id": item.order_id,
            "name": "",
            "sub_items": [],
            "price": 0.0
        }
        item_total = 0.0

        # Regular items
        if item.type == "regular":
            matches = find_items_by_id(all_menu_items, item.item_id, item.size)
            if not matches: # Fallback if specific size isn't found
                matches = find_items_by_id(all_menu_items, item.item_id)
                
            if matches:
                mi = matches[0]
                receipt_item["name"] = f"{mi.name} {f'({item.size})' if item.size else ''}".strip()
                item_total += mi.price

        # Combo and Happy Meals
        elif item.type in ["combo_meal", "happy_meal"]:
            matches = find_items_by_id(all_menu_items, item.meal_id)
            if matches:
                mi = matches[0]
                receipt_item["name"] = mi.name
                item_total += mi.price

            # Add Drink
            if item.drink_id:
                d_matches = find_items_by_id(all_menu_items, item.drink_id, item.drink_size)
                if not d_matches:
                    d_matches = find_items_by_id(all_menu_items, item.drink_id)
                if d_matches:
                    d_mi = d_matches[0]
                    receipt_item["sub_items"].append(f"+ {d_mi.name} {f'({item.drink_size})' if item.drink_size else ''}".strip())
                    item_total += d_mi.price 

            # Add Sauce/Chutney
            if getattr(item, 'sauce_id', None):
                s_matches = find_items_by_id(all_menu_items, item.sauce_id)
                if s_matches:
                    s_mi = s_matches[0]
                    receipt_item["sub_items"].append(f"+ {s_mi.name}")
                    item_total += s_mi.price

        receipt_item["price"] = item_total
        receipt_data["total_price"] += item_total
        receipt_data["items"].append(receipt_item)

    # Write the enriched data to the JSON file
    with open("src/receipt.json", "w", encoding="utf-8") as f:
        json.dump(receipt_data, f, indent=2)


class DriveThruAgent(Agent):
    def __init__(self, *, userdata: Userdata) -> None:
        instructions = (
            COMMON_INSTRUCTIONS
            + "\n\n"
            + menu_instructions("drink", items=userdata.drink_items)
            + "\n\n"
            + menu_instructions("combo_meal", items=userdata.combo_items)
            + "\n\n"
            + menu_instructions("happy_meal", items=userdata.happy_items)
            + "\n\n"
            + menu_instructions("regular", items=userdata.regular_items)
            + "\n\n"
            + menu_instructions("sauce", items=userdata.sauce_items)
        )

        super().__init__(
            instructions=instructions,
            tools=[
                self.build_regular_order_tool(
                    userdata.regular_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_combo_order_tool(
                    userdata.combo_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_happy_order_tool(
                    userdata.happy_items, userdata.drink_items, userdata.sauce_items
                ),
            ],
        )

        
    def build_combo_order_tool(
        self, combo_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    ) -> FunctionTool:
        available_combo_ids = {item.id for item in combo_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_combo_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[
                str,
                Field(
                    description="The ID of the combo meal or thali the user requested.",
                    json_schema_extra={"enum": list(available_combo_ids)},
                ),
            ],
            drink_id: Annotated[
                str,
                Field(
                    description="The ID of the drink the user requested.",
                    json_schema_extra={"enum": list(available_drink_ids)},
                ),
            ],
            drink_size: Literal["S", "M", "L", "null"] | None,
            sauce_id: Annotated[
                str,
                Field(
                    description="The ID of the chutney or extra the user requested.",
                    json_schema_extra={"enum": [*available_sauce_ids, "null"]},
                ),
            ]
            | None,
        ):
            """
            Call this when the user orders a **Combo Meal or Thali**, like: “Number 1 with a large Thums Up” or “I'll do the Butter Chicken Thali.”

            Do not call this tool unless the user clearly refers to a known combo meal by name or number.
            Regular items like a single Vada Pav cannot be made into a meal unless such a combo explicitly exists.

            Only call this function once the user has clearly specified a drink — always ask for it if it's missing.

            A drink for a combo can be Small, Medium, or Large.
            If the user says just “a large meal,” assume the drink is that size.
            """
            if not find_items_by_id(combo_items, meal_id):
                raise ToolError(f"error: the meal {meal_id} was not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: the drink {drink_id} was not found")

            if drink_size == "null":
                drink_size = None

            if sauce_id == "null":
                sauce_id = None

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {drink_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if drink_size is not None and not available_sizes:
                raise ToolError(
                    f"error: size should not be specified for item {drink_id} as it does not support sizing options."
                )

            if drink_size and drink_size not in available_sizes:
                drink_size = None

            if sauce_id and not find_items_by_id(sauce_items, sauce_id):
                raise ToolError(f"error: the sauce {sauce_id} was not found")

            item = OrderedCombo(
                meal_id=meal_id,
                drink_id=drink_id,
                drink_size=drink_size,
                sauce_id=sauce_id,
            )
            await ctx.userdata.order.add(item)
            
            # --- WRITE ENRICHED DATA TO JSON FILE ---
            update_receipt_file(ctx.userdata)
            
            return f"The item was added: {item.model_dump_json()}"

        return order_combo_meal

    def build_happy_order_tool(
        self,
        happy_items: list[MenuItem],
        drink_items: list[MenuItem],
        sauce_items: list[MenuItem],
    ) -> FunctionTool:
        available_happy_ids = {item.id for item in happy_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_happy_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[
                str,
                Field(
                    description="The ID of the kid's meal the user requested.",
                    json_schema_extra={"enum": list(available_happy_ids)},
                ),
            ],
            drink_id: Annotated[
                str,
                Field(
                    description="The ID of the drink the user requested.",
                    json_schema_extra={"enum": list(available_drink_ids)},
                ),
            ],
            drink_size: Literal["S", "M", "L", "null"] | None,
            sauce_id: Annotated[
                str,
                Field(
                    description="The ID of the chutney or extra the user requested.",
                    json_schema_extra={"enum": [*available_sauce_ids, "null"]},
                ),
            ]
            | None,
        ) -> str:
            """
            Call this when the user orders a **Kid's Meal**. These meals come with a main item, a drink, and an optional side.

            The user must clearly specify a valid Kid's Meal option (e.g., “Can I get a Mini Dosa Meal?”).

            Before calling this tool:
            - Ensure the user has provided all required components: a valid meal, drink, and drink size.
            - If any of these are missing, prompt the user for the missing part before proceeding.

            Assume Small as default only if the user says "Kid's Meal" and gives no size preference, but always ask for clarification if unsure.
            """
            if not find_items_by_id(happy_items, meal_id):
                raise ToolError(f"error: the meal {meal_id} was not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: the drink {drink_id} was not found")

            if drink_size == "null":
                drink_size = None

            if sauce_id == "null":
                sauce_id = None

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {drink_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if drink_size is not None and not available_sizes:
                drink_size = None

            if sauce_id and not find_items_by_id(sauce_items, sauce_id):
                raise ToolError(f"error: the sauce {sauce_id} was not found")

            item = OrderedHappy(
                meal_id=meal_id,
                drink_id=drink_id,
                drink_size=drink_size,
                sauce_id=sauce_id,
            )
            await ctx.userdata.order.add(item)
            
            # --- WRITE ENRICHED DATA TO JSON FILE ---
            update_receipt_file(ctx.userdata)
            
            return f"The item was added: {item.model_dump_json()}"

        return order_happy_meal

    def build_regular_order_tool(
        self,
        regular_items: list[MenuItem],
        drink_items: list[MenuItem],
        sauce_items: list[MenuItem],
    ) -> FunctionTool:
        all_items = regular_items + drink_items + sauce_items
        available_ids = {item.id for item in all_items}

        @function_tool
        async def order_regular_item(
            ctx: RunContext[Userdata],
            item_id: Annotated[
                str,
                Field(
                    description="The ID of the item the user requested.",
                    json_schema_extra={"enum": list(available_ids)},
                ),
            ],
            size: Annotated[
                Literal["S", "M", "L", "null"] | None,
                Field(
                    description="Size of the item, if applicable (e.g., 'S', 'M', 'L'), otherwise 'null'. "
                ),
            ] = "null",
        ) -> str:
            """
            Call this when the user orders **a single item on its own**, not as part of a Combo Meal or Kid's Meal.

            The customer must provide clear and specific input. For example, item variants such as flavor must **always** be explicitly stated.

            The user might say—for example:
            - “Just the Vada Pav, no meal”
            - “A medium Mango Lassi”
            - “Can I get some Mint Chutney?”
            - “Can I get a Gulab Jamun?”
            """
            item_sizes = find_items_by_id(all_items, item_id)
            if not item_sizes:
                raise ToolError(f"error: {item_id} was not found.")

            if size == "null":
                size = None

            available_sizes = list({item.size for item in item_sizes if item.size})
            if size is None and len(available_sizes) > 1:
                raise ToolError(
                    f"error: {item_id} comes with multiple sizes: {', '.join(available_sizes)}. "
                    "Please clarify which size should be selected."
                )

            if size is not None and not available_sizes:
                size = None

            if (size and available_sizes) and size not in available_sizes:
                raise ToolError(
                    f"error: unknown size {size} for {item_id}. Available sizes: {', '.join(available_sizes)}."
                )

            item = OrderedRegular(item_id=item_id, size=size)
            await ctx.userdata.order.add(item)
            
            # --- WRITE ENRICHED DATA TO JSON FILE ---
            update_receipt_file(ctx.userdata)
            
            return f"The item was added: {item.model_dump_json()}"

        return order_regular_item

    @function_tool
    async def remove_order_item(
        self,
        ctx: RunContext[Userdata],
        order_id: Annotated[
            list[str],
            Field(
                description="A list of internal `order_id`s of the items to remove. Use `list_order_items` to look it up if needed."
            ),
        ],
    ) -> str:
        """
        Removes one or more items from the user's order using their `order_id`s.

        Useful when the user asks to cancel or delete existing items (e.g., “Remove the samosas”).

        If the `order_id`s are unknown, call `list_order_items` first to retrieve them.
        """
        not_found = [oid for oid in order_id if oid not in ctx.userdata.order.items]
        if not_found:
            raise ToolError(f"error: no item(s) found with order_id(s): {', '.join(not_found)}")

        removed_items = [await ctx.userdata.order.remove(oid) for oid in order_id]
        
        # --- WRITE ENRICHED DATA TO JSON FILE ---
        update_receipt_file(ctx.userdata)
        
        return "Removed items:\n" + "\n".join(item.model_dump_json() for item in removed_items)

    @function_tool
    async def list_order_items(self, ctx: RunContext[Userdata]) -> str:
        """
        Retrieves the current list of items in the user's order, including each item's internal `order_id`.

        Helpful when:
        - An `order_id` is required before modifying or removing an existing item.
        - Confirming details or contents of the current order.

        Examples:
        - User requests modifying an item, but the item's `order_id` is unknown (e.g., "Change the Lassi from small to large").
        - User requests removing an item, but the item's `order_id` is unknown (e.g., "Remove the Naan").
        - User asks about current order details (e.g., "What's in my order so far?").
        """
        items = ctx.userdata.order.items.values()
        if not items:
            return "The order is empty"

        return "\n".join(item.model_dump_json() for item in items)


async def new_userdata() -> Userdata:
    fake_db = FakeDB()
    drink_items = await fake_db.list_drinks()
    combo_items = await fake_db.list_combo_meals()
    happy_items = await fake_db.list_happy_meals()
    regular_items = await fake_db.list_regulars()
    sauce_items = await fake_db.list_sauces()

    order_state = OrderState(items={})
    userdata = Userdata(
        order=order_state,
        drink_items=drink_items,
        combo_items=combo_items,
        happy_items=happy_items,
        regular_items=regular_items,
        sauce_items=sauce_items,
    )
    return userdata


server = AgentServer()


async def on_session_end(ctx: JobContext) -> None:
    report = ctx.make_session_report()
    # Add 'default=str' to safely handle complex objects like the LLM
    report_json = json.dumps(report.to_dict(), indent=2, default=str)
    
    # Optional: Print it so you can actually see the report in your terminal!
    print(f"\n--- SESSION REPORT ---\n{report_json}\n----------------------\n")


@server.rtc_session(on_session_end=on_session_end)
async def drive_thru_agent(ctx: JobContext) -> None:
    userdata = await new_userdata()
    
    # Optional: Clear the receipt.json with an empty schema when a new session starts
    with open("receipt.json", "w", encoding="utf-8") as f:
        json.dump({"items": [], "total_price": 0.0}, f, indent=2)
        
    session = AgentSession[Userdata](
        userdata=userdata,
        stt=inference.STT(
            "deepgram/nova-3",
            language="en-IN", # Updated to Indian English for better local accent recognition
            extra_kwargs={
                "keyterm": [
                    "Thali",
                    "Biryani",
                    "Lassi",
                    "Samosa",
                    "Paneer",
                    "Chutney",
                    "Naan",
                    "Vada Pav",
                    "Thums Up",
                ],
            },
        ),
        llm=inference.LLM("openai/gpt-5-mini"),
        tts=inference.TTS("cartesia/sonic-3", voice="f786b574-daa5-4673-aa0c-cbe3e8534c02"),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),
        max_tool_steps=10,
    )

    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(
            str(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg_noise.mp3")),
            volume=1.0,
        ),
    )

    await session.start(agent=DriveThruAgent(userdata=userdata), room=ctx.room)
    await background_audio.start(room=ctx.room, agent_session=session)


if __name__ == "__main__":
    cli.run_app(server)