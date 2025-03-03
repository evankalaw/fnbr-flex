import aiohttp
import asyncio
import json
import platform
import os
import re
from datetime import datetime

# Constants
SWITCH_TOKEN = "OThmN2U0MmMyZTNhNGY4NmE3NGViNDNmYmI0MWVkMzk6MGEyNDQ5YTItMDAxYS00NTFlLWFmZWMtM2U4MTI5MDFjNGQ3"


class EpicUser:
    def __init__(self, data: dict):
        self.access_token = data.get("access_token", "")
        self.account_id = data.get("account_id", "")


class EpicAuthenticator:
    def __init__(self):
        self.http = aiohttp.ClientSession(
            headers={
                "User-Agent": f"CustomTool/1.0 {platform.system()}/{platform.version()}"
            }
        )
        self.access_token = ""

    async def get_initial_token(self):
        async with self.http.post(
            "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token",
            headers={
                "Authorization": f"basic {SWITCH_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        ) as resp:
            data = await resp.json()
            return data["access_token"]

    async def create_device_code(self):
        self.access_token = await self.get_initial_token()
        async with self.http.post(
            "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/deviceAuthorization",
            headers={
                "Authorization": f"bearer {self.access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ) as resp:
            data = await resp.json()
            return data["verification_uri_complete"], data["device_code"]

    async def wait_for_auth(self, device_code):
        while True:
            async with self.http.post(
                "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token",
                headers={
                    "Authorization": f"basic {SWITCH_TOKEN}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "device_code", "device_code": device_code},
            ) as resp:
                data = await resp.json()
                if "access_token" in data:
                    return EpicUser(data)
            await asyncio.sleep(5)

    async def get_fortnite_profile(self, user: EpicUser):
        url = f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{user.account_id}/client/QueryProfile?profileId=athena"
        print(f"Requesting URL: {url}")
        async with self.http.post(
            url,
            headers={
                "Authorization": f"bearer {user.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "Fortnite/++Fortnite+Release-14.60-CL-14778894 Windows/10.0.19041.1.256.64bit",
            },
            json={},
        ) as resp:
            if resp.status == 200:
                profile_data = await resp.json()
                print(f"Received profileId: {profile_data.get('profileId')}")
                items = (
                    profile_data.get("profileChanges", [{}])[0]
                    .get("profile", {})
                    .get("items", {})
                )
                print(f"Total items count: {len(items)}")
                if items:
                    print(f"Sample item: {list(items.keys())[0]}")
                else:
                    print("No items found in the profile.")
                return items
            else:
                print(f"Failed to fetch profile: Status {resp.status}")
                print(await resp.text())
                return None

    async def close(self):
        await self.http.close()


def load_cosmetics_data(filename="cosmetics.json"):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "data" in data:
                cosmetics = {
                    item["id"].lower(): {
                        "name": item["name"],
                        "introduction": item.get("introduction", {})
                        .get("text", "")
                        .lower(),
                        "type": item["type"]["backendValue"],
                        "series": item.get("series", {}).get("value", "").lower(),
                        "rarity": item["rarity"]["value"].lower(),
                        "set": item.get("set", {}).get("value", "").lower(),
                        "added": item.get("added", ""),
                    }
                    for item in data["data"]
                }
            else:
                cosmetics = {
                    item["id"].lower(): {
                        "name": item["name"],
                        "introduction": item.get("introduction", {})
                        .get("text", "")
                        .lower(),
                        "type": item["type"]["backendValue"],
                        "series": item.get("series", {}).get("value", "").lower(),
                        "rarity": item["rarity"]["value"].lower(),
                        "set": item.get("set", {}).get("value", "").lower(),
                        "added": item.get("added", ""),
                    }
                    for item in data
                }
            return cosmetics
    else:
        print(f"Cosmetics file '{filename}' not found.")
        return {}


def get_item_info(template_id, cosmetics_dict):
    if ":" in template_id:
        category, item_id = template_id.split(":", 1)
        item_id_lower = item_id.lower()
        item_info = cosmetics_dict.get(
            item_id_lower,
            {
                "name": "Unknown Item",
                "introduction": "",
                "type": "",
                "series": "",
                "rarity": "",
                "set": "",
                "added": "",
            },
        )
        name = item_info["name"]
        intro = item_info["introduction"]
        item_type = item_info["type"]
        series = item_info["series"]
        rarity = item_info["rarity"]
        set_name = item_info["set"]
        added_date = item_info["added"]

        # Extract chapter and season
        chapter_season_match = re.search(r"chapter (\d+), season (\d+)", intro)
        chapter_season = (
            (int(chapter_season_match.group(1)), int(chapter_season_match.group(2)))
            if chapter_season_match
            else None
        )

        # Define pass timelines
        og_pass_seasons = [(1, s) for s in range(1, 11)]  # Chapter 1, Seasons 1-10
        og_pass_og_season = (4, "OG")  # Chapter 4: Season OG (Nov 2023)
        festival_pass_start = (5, 1)  # Chapter 5, Season 1 (Dec 2023)

        # Pass origin
        from_og_pass = (
            chapter_season in og_pass_seasons and "battle pass" in intro
        ) or (chapter_season == og_pass_og_season)
        from_festival_pass = (
            item_type == "AthenaMusicPack" and chapter_season >= festival_pass_start
            if chapter_season
            else False
        )

        # Refined heuristic
        is_earned = (
            "battle pass" in intro
            or "event" in intro
            or (
                chapter_season
                and rarity in ["common", "uncommon"]
                and not series
                and not set_name
            )
        )
        is_purchased = not is_earned and (
            "shop" in intro
            or set_name
            or rarity in ["epic", "legendary"]
            or series
            in ["gaming legends series", "marvel series", "dc series", "icon series"]
            or not chapter_season
        )

        return (
            name,
            is_purchased,
            item_type,
            chapter_season,
            from_og_pass,
            from_festival_pass,
            set_name,
        )
    return "Unknown Item", False, "", None, False, False, ""


def is_festival_period(date_str):
    """Check if date is within known Festival Pass periods"""
    if not date_str:
        return False

    # Convert date string to datetime object
    try:
        # Parse the date string - handle different formats
        if "Z" in date_str:
            # Remove the Z and explicitly make it offset-naive
            date_str = date_str.replace("Z", "")
            date = datetime.fromisoformat(date_str)
        elif "+" in date_str:
            # Parse with timezone, then make offset-naive
            date = datetime.fromisoformat(date_str).replace(tzinfo=None)
        else:
            # Already offset-naive
            date = datetime.fromisoformat(date_str)
    except (ValueError, TypeError) as e:
        print(f"Date parsing error with '{date_str}': {e}")
        return False

    # Known Festival Pass periods (example dates)
    festival_periods = [
        (datetime(2023, 12, 3), datetime(2024, 3, 8)),  # Chapter 5 Season 1
        # Add more periods as needed
    ]

    try:
        return any(start <= date <= end for start, end in festival_periods)
    except TypeError as e:
        print(
            f"Date comparison error: {e} (comparing {date} with {festival_periods[0][0]})"
        )
        # Fallback - if comparison still fails, return False
        return False


def analyze_intro_text(intro):
    """Analyze introduction text for source indicators"""
    intro = intro.lower()
    sources = {
        "battle_pass": any(
            phrase in intro
            for phrase in [
                "battle pass",
                "battlepass",
                "tier ",
                "chapter",
                "season pass",
            ]
        ),
        "og_pass": "og pass" in intro or "og season" in intro,
        "festival_pass": any(
            phrase in intro
            for phrase in [
                "festival pass",
                "rhythm pass",
                "music pack pass",
                "festival event",
            ]
        ),
        "item_shop": any(
            phrase in intro
            for phrase in [
                "item shop",
                "featured item",
                "daily item",
                "available in the shop",
            ]
        ),
        "crew_pack": "crew pack" in intro or "fortnite crew" in intro,
    }
    return sources


def get_item_source(template_id, cosmetics_dict):
    """Determine the source of an item with confidence level"""
    if ":" not in template_id:
        return "Unknown", 0.0

    category, item_id = template_id.split(":", 1)
    item_id_lower = item_id.lower()

    item_data = cosmetics_dict.get(item_id_lower, {})
    intro = item_data.get("introduction", "").lower()
    rarity = item_data.get("rarity", "").lower()
    added_date = item_data.get("added", "")
    item_type = item_data.get("type", "")
    series = item_data.get("series", "")
    set_name = item_data.get("set", "")

    # Get basic item info first
    (
        name,
        is_purchased,
        item_type,
        chapter_season,
        from_og_pass,
        from_festival_pass,
        set_name,
    ) = get_item_info(template_id, cosmetics_dict)

    # Analyze introduction text for clues
    text_sources = analyze_intro_text(intro)

    # Determine source with enhanced logic
    source = "Unknown"
    confidence = 0

    # Battle Pass logic
    if text_sources["battle_pass"] or (chapter_season and "battle pass" in intro):
        source = "Battle Pass"
        confidence = 0.8

        # Check if it's specifically OG Pass
        if from_og_pass or text_sources["og_pass"]:
            source = "OG Pass"
            confidence = 0.9

    # Festival Pass logic
    elif (
        from_festival_pass
        or text_sources["festival_pass"]
        or is_festival_period(added_date)
    ):
        source = "Festival Pass"
        confidence = 0.8

    # Item Shop logic
    elif text_sources["item_shop"] or (is_purchased and set_name):
        source = "Item Shop"
        confidence = 0.7

    # Crew Pack logic
    elif text_sources["crew_pack"]:
        source = "Crew Pack"
        confidence = 0.9

    # Fallback to original logic with lower confidence
    elif is_purchased:
        source = "Item Shop"
        confidence = 0.5
    else:
        source = "Battle Pass/Free Reward"
        confidence = 0.4

    return source, confidence


async def main():
    auth = EpicAuthenticator()
    try:
        cosmetics_dict = load_cosmetics_data("cosmetics.json")
        if not cosmetics_dict:
            print(
                "Cannot proceed without cosmetics data. Please provide cosmetics.json."
            )
            return

        verification_url, device_code = await auth.create_device_code()
        print(f"Visit this URL to authorize: {verification_url}")

        user = await auth.wait_for_auth(device_code)
        print(f"Authenticated as account ID: {user.account_id}")

        profile = await auth.get_fortnite_profile(user)
        if profile:
            print("\nAthena Items in Locker:")
            category_map = {
                "AthenaCharacter": "Outfits",
                "AthenaDance": "Emotes",
                "AthenaGlider": "Gliders",
                "AthenaPickaxe": "Pickaxes",
                "AthenaWrap": "Wraps",
                "AthenaBackpack": "Backpacks",
            }

            categorized_items = {cat: [] for cat in category_map.values()}
            purchased_items = []
            battle_pass_seasons = set()
            og_pass_items = []
            festival_pass_items = []
            bundle_sets = set()
            item_sources = {}

            for item_id, item_data in profile.items():
                template_id = item_data.get("templateId", "")
                for prefix, category in category_map.items():
                    if template_id.startswith(prefix):
                        (
                            name,
                            is_purchased,
                            item_type,
                            chapter_season,
                            from_og_pass,
                            from_festival_pass,
                            set_name,
                        ) = get_item_info(template_id, cosmetics_dict)
                        if item_type == prefix:
                            status = "Purchased" if is_purchased else "Earned"
                            categorized_items[category].append((name, status))
                            if is_purchased:
                                purchased_items.append(name)
                                if set_name:
                                    bundle_sets.add(set_name)
                            if chapter_season:
                                battle_pass_seasons.add(chapter_season)
                            if from_og_pass:
                                og_pass_items.append(name)
                            if from_festival_pass:
                                festival_pass_items.append(name)
                        source, confidence = get_item_source(
                            template_id, cosmetics_dict
                        )

                        item_sources[name] = {
                            "source": source,
                            "confidence": confidence,
                            "evidence": {
                                "introduction_contains_battle_pass": "battle pass"
                                in cosmetics_dict.get(
                                    template_id.split(":", 1)[1].lower(), {}
                                )
                                .get("introduction", "")
                                .lower(),
                                "chapter_season": chapter_season,
                                "rarity": cosmetics_dict.get(
                                    template_id.split(":", 1)[1].lower(), {}
                                ).get("rarity", ""),
                                "set_name": set_name,
                                "has_release_date": bool(
                                    cosmetics_dict.get(
                                        template_id.split(":", 1)[1].lower(), {}
                                    ).get("added", "")
                                ),
                            },
                        }
                        break

            # Print categorized items
            for category, items in categorized_items.items():
                if items:
                    print(f"\n{category}:")
                    for name, status in items:
                        print(f"- {name} ({status})")

            # Print purchased items for price API
            if purchased_items:
                print("\nPurchased Items for Price API:")
                for name in purchased_items:
                    print(f"- {name}")

            # Print Battle Pass count
            print(f"\nUnique Battle Passes Detected: {len(battle_pass_seasons)}")
            if battle_pass_seasons:
                print("Battle Pass Seasons:")
                for chapter, season in sorted(
                    battle_pass_seasons, key=lambda x: (x[0], str(x[1]))
                ):  # Handle "OG" as string
                    print(f"- Chapter {chapter}, Season {season}")

            # Print OG Pass items
            print(f"\nItems from OG Pass: {len(og_pass_items)}")
            if og_pass_items:
                for name in og_pass_items:
                    print(f"- {name}")

            # Print Festival Pass items
            print(f"\nItems from Festival Pass: {len(festival_pass_items)}")
            if festival_pass_items:
                for name in festival_pass_items:
                    print(f"- {name}")

            # Print Bundle count
            print(f"\nUnique Bundles Detected: {len(bundle_sets)}")
            if bundle_sets:
                print("Bundles:")
                for set_name in bundle_sets:
                    print(f"- {set_name}")

    finally:
        await auth.close()


async def query_price_api(name):
    print(
        f"Querying price for '{name}' at your API endpoint: https://your-api.example.com/price?item={name}"
    )


if __name__ == "__main__":
    asyncio.run(main())
