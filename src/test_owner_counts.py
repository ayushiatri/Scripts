from google.oauth2.credentials import Credentials
import gspread
import datetime
import requests
from constants import CLIENT_SECRET, CLIENT_ID, REFRESH_TOKEN
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import random
import time
import re
import json

CITIES = ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"]
PROPERTY_TYPES = ["Residential", "PG", "Commercial"]
SEGMENTS = ["Buy", "Rent"]

CLIENT_ID = CLIENT_ID
CLIENT_SECRET = CLIENT_SECRET
REFRESH_TOKEN = REFRESH_TOKEN

SHEET_NAME = "Daily Owner Listings"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
]

creds = Credentials(
    None,
    refresh_token=REFRESH_TOKEN,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_uri="https://oauth2.googleapis.com/token"
)
gc = gspread.authorize(creds)

try:
    sheet = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sheet = gc.create(SHEET_NAME)
    print(f"Created new Google Sheet: {SHEET_NAME}")

today_str = datetime.datetime.now().strftime("%Y-%m-%d")
try:
    worksheet = sheet.add_worksheet(title=today_str, rows="100", cols="10")
except gspread.exceptions.APIError:
    worksheet = sheet.worksheet(today_str)

headers = ["Date", "Source", "City", "Segment", "Property Type", "Count of Listings"]
worksheet.append_row(headers)

def get_99acres_count(city, segment, property_type, retries=3):
    segment_map = {"Buy": "S", "Rent": "R"}
    property_type_map = {"Residential": "R", "Commercial": "C", "PG": "PG"}
    city_map = {
        "Delhi": ("1075722", "delhi"),
        "Mumbai": ("1075798", "mumbai"),
        "Bangalore": ("1075804", "bangalore"),
        "Hyderabad": ("1075817", "hyderabad"),
        "Chennai": ("1075808", "chennai"),
        "Pune": ("1075813", "pune"),
        "Kolkata": ("1075801", "kolkata"),
        "Ahmedabad": ("1075810", "ahmedabad"),
    }

    if city not in city_map or segment not in segment_map or property_type not in property_type_map:
        return 0

    city_code, city_slug = city_map[city]
    preference = segment_map[segment]
    res_com = property_type_map[property_type]

    url = (
        f"https://www.99acres.com/search/property/"
        f"{'buy' if segment == 'Buy' else 'rent'}/{city_slug}"
        f"?city={city_code}&keyword={city_slug}&preference={preference}"
        f"&area_unit=1&res_com={res_com}"
    )

    for attempt in range(retries):
        try:
            print(f"Fetching: {url} (Attempt {attempt+1})")

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-http2",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                    ]
                )
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS)
                )
                page = context.new_page()

                # Navigate until DOM is ready
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                html = page.content()
                browser.close()

            # Try to extract numberOfItems from page source
            match = re.search(r'"numberOfItems"\s*:\s*(\d+)', html)
            if match:
                return int(match.group(1))

            # Fallback: parse JSON-LD script
            soup = BeautifulSoup(html, "html.parser")
            script_tag = soup.find("script", attrs={"type": "application/ld+json"})
            if script_tag:
                data = json.loads(script_tag.string)
                return data.get("numberOfItems", 0)

        except Exception as e:
            print(f"[99acres] Attempt {attempt+1} failed for {city}-{segment}-{property_type}: {e}")
            time.sleep(random.randint(2, 5))  # small randomized delay

    return 0


# def get_magicbricks_count(city, segment, property_type):
#     property_type_map = {
#         "Residential": "Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa",
#         "PG": "Paying-Guest",
#         "Commercial": "Commercial-Office-Space,Office-ITPark-SEZ,Commercial-Shop,Commercial-Showroom,Commercial-Land,Warehouse-Godown,Industrial-Building,Industrial-Shed,Co-working-Space"
#     }
#     proptype_value = property_type_map.get(property_type, "")
#     if not proptype_value:
#         return 0
#
#     url = f"https://www.magicbricks.com/property-for-{segment.lower()}/"
#     if property_type in ["Residential", "PG"]:
#         url += "residential-real-estate"
#     else:
#         url += "commercial-real-estate"
#     url += f"?proptype={proptype_value}&cityName={city.replace(' ', '+')}"
#
#     try:
#         print(f"URL: {url}")
#         r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
#         match = re.search(r"nsrResultCount\s*:\s*([0-9]+)", r.text)
#         count = int(match.group(1)) if match else 0
#         return count
#     except Exception as e:
#         print(f"Error fetching MagicBricks {city}-{segment}-{property_type}: {e}")
#         return 0

# def get_nobroker_count(city, segment, property_type):
#     url = COMPETITOR_URLS["NoBroker"].format(
#         city=city.replace(" ", "-").lower(),
#         segment=segment.lower(),
#         property_type=property_type.lower()
#     )
#     try:
#         r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
#         match = re.search(r"listing-count\s*[:=]\s*([0-9]+)", r.text)
#         count = int(match.group(1)) if match else 0
#         return count
#     except Exception as e:
#         print(f"Error fetching NoBroker {city}-{segment}-{property_type}: {e}")
#         return 0

SCRAPER_FUNCTIONS = {
    "99acres": get_99acres_count,
    # "MagicBricks": get_magicbricks_count,
    # "NoBroker": get_nobroker_count
}

for source in SCRAPER_FUNCTIONS.keys():
    for city in CITIES:
        for segment in SEGMENTS:
            for prop_type in PROPERTY_TYPES:
                count = SCRAPER_FUNCTIONS[source](city, segment, prop_type)
                row = [today_str, source, city, segment, prop_type, count]
                worksheet.append_row(row)
                time.sleep(1)

print(f"\n✅ Daily owner listings counts updated successfully!")
print(f"Google Sheet URL: {sheet.url}")
