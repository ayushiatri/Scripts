from google.oauth2.credentials import Credentials
import gspread
import datetime
import random
import time
import re
import json
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from constants import CLIENT_SECRET, CLIENT_ID, REFRESH_TOKEN

CITIES = ["Delhi", "Noida", "Gurugram", "Mumbai", "Bangalore", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad"]
PROPERTY_TYPES = ["Residential", "PG", "Commercial"]
SEGMENTS = ["Buy", "Rent"]

SOURCES = ["99acres", "MagicBricks", "NoBroker"]

CLIENT_ID = CLIENT_ID
CLIENT_SECRET = CLIENT_SECRET
REFRESH_TOKEN = REFRESH_TOKEN
SHEET_NAME = "Daily Owner Listings"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
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

today_str = datetime.datetime.now().strftime("%Y-%m-%d")
try:
    worksheet = sheet.add_worksheet(title=today_str, rows="100", cols="10")
except gspread.exceptions.APIError:
    worksheet = sheet.worksheet(today_str)

headers = ["Date", "Source", "City", "Segment", "Property Type", "Count of Listings"]
worksheet.append_row(headers)

def build_99acres_url(city, segment, property_type):
    city_map = {"Delhi": ("1075722", "delhi"),
                "Mumbai": ("12", "mumbai"),
                "Bangalore": ("20", "bangalore"),
                "Gurugram": ("8", "gurgaon"),
                "Noida": ("7", "noida"),
                "Hyderabad": ("269", "hyderabad"),
                "Chennai": ("32", "chennai"),
                "Pune": ("19", "pune"),
                "Kolkata": ("25", "kolkata"),
                "Ahmedabad": ("45", "ahmedabad")
                }
    if city not in city_map or (property_type == "PG" and segment == "Buy"):
        return None
    city_code, city_slug = city_map[city]

    if segment == "Rent" and property_type == "PG":
        return f"https://www.99acres.com/search/property/rent/residential/{city_slug}?city={city_code}&preference=P&area_unit=1&res_com=R&isPreLeased=N"
    segment_map = {"Buy": "S", "Rent": "R"}
    res_com_map = {"Residential": "R", "Commercial": "C", "PG": "PG"}

    return f"https://www.99acres.com/search/property/{'buy' if segment == 'Buy' else 'rent'}/{city_slug}?city={city_code}&preference={segment_map[segment]}&area_unit=1&res_com={res_com_map[property_type]}"


def build_magicbricks_url(city, segment, property_type):
    if property_type == "PG" and segment == "Buy":
        return None

    city_name_map = {
        "Delhi": ("New-Delhi", "2624"),
        "Noida": ("Noida", "2625"),
        "Gurugram": ("Gurgaon", "2626"),
        "Mumbai": ("Mumbai", "2505"),
        "Bangalore": ("Bangalore", "3327"),
        "Hyderabad": ("Hyderabad", "3930"),
        "Chennai": ("Chennai", "181"),
        "Pune": ("Pune", "2377"),
        "Kolkata": ("Kolkata", "2060"),
        "Ahmedabad": ("Ahmedabad", "1760")
    }

    if city not in city_name_map:
        return None

    city_name, city_code = city_name_map[city]
    if property_type == "PG":
        return f"https://www.magicbricks.com/property-for-rent/residential-paying-guest?cityName={city_name}"

    if property_type == "Residential":
        return f"https://www.magicbricks.com/property-for-sale/residential-real-estate?cityName={city_name}"

    commercial_types = "Commercial-Office-Space,Office-ITPark-SEZ,Commercial-Shop,Commercial-Showroom"

    if segment == "Buy":
        return (
            f"https://www.magicbricks.com/property-for-sale/commercial-real-estate"
            f"?proptype={commercial_types}&categoryC=S&cityName={city_name.replace('-', ' ')}"
        )

    if segment == "Rent":
        return (
            f"https://www.magicbricks.com/property-for-rent/commercial-real-estate"
            f"?bedroom=&proptype={commercial_types}&cityName={city_name}"
        )

    return None


def build_nobroker_url(city, segment, property_type):
    city_slug = city.lower()
    if property_type == "PG" and segment == "Buy":
        return None
    if property_type == "PG":
        return f"https://www.nobroker.in/property/rent/{city_slug}/?sharedAccomodation=1"
    if property_type == "Commercial":
        return f"https://www.nobroker.in/property/{'sale' if segment == 'Buy' else 'rent'}/{city_slug}/commercial-property"
    return f"https://www.nobroker.in/property/{'sale' if segment == 'Buy' else 'rent'}/{city_slug}"


def extract_listing_count(html, source=None, property_type=None):

    match = re.search(r'"numberOfItems"\s*:\s*(\d+)', html)
    if match:
        return int(match.group(1))

    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", attrs={"type": "application/ld+json"})
    if script_tag:
        try:
            data = json.loads(script_tag.string)
            if "numberOfItems" in data:
                return data.get("numberOfItems", 0)
        except json.JSONDecodeError:
            pass

    if source == "MagicBricks" and property_type == "PG":
        for script in soup.find_all("script"):
            if script.string and "gsData" in script.string:
                match = re.search(r"resultCount\s*[:=]\s*'(\d+)'", script.string)
                if match:
                    return int(match.group(1))

    match = re.search(r"(\d[\d,]*)\s+results", html)
    if match:
        return int(match.group(1).replace(",", ""))

    return 0


with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    context = browser.new_context(user_agent=random.choice(USER_AGENTS))
    page = context.new_page()

    for city in CITIES:
        for segment in SEGMENTS:
            for prop_type in PROPERTY_TYPES:
                for source in SOURCES:
                    if source == "99acres":
                        url = build_99acres_url(city, segment, prop_type)
                    elif source == "MagicBricks":
                        url = build_magicbricks_url(city, segment, prop_type)
                    elif source == "NoBroker":
                        url = build_nobroker_url(city, segment, prop_type)
                    else:
                        continue

                    if not url:
                        continue

                    print(f"[{source}] Fetching: {url}")
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        html = page.content()
                        count = extract_listing_count(html, source=source, property_type=prop_type)
                    except Exception as e:
                        print(f"[ERROR] {source} {city}-{segment}-{prop_type}: {e}")
                        count = 0

                    worksheet.append_row([today_str, source, city, segment, prop_type, count])
                    time.sleep(1)

    browser.close()

print("\n Daily owner listings counts updated successfully!")
print(f" Google Sheet URL: {sheet.url}")
