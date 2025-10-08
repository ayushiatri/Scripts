import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ------------------ CONFIG ------------------
CITIES = ["Delhi"]
PROPERTY_TYPES = ["Residential", "PG", "Commercial"]
SEGMENTS = ["Buy", "Rent"]

city_map = {
    "Delhi": ("1075722", "delhi"),
}

segment_map = {"Buy": "S", "Rent": "R"}
property_type_map = {"Residential": "R", "Commercial": "C", "PG": "PG"}

# ------------------ INIT DRIVER ------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# ------------------ SCRAPER FUNCTION ------------------
def get_99acres_count(city, segment, property_type):
    city_code, city_slug = city_map[city]
    preference = segment_map[segment]
    res_com = property_type_map[property_type]

    url = (
        f"https://www.99acres.com/search/property/"
        f"{'buy' if segment == 'Buy' else 'rent'}/{city_slug}"
        f"?city={city_code}&keyword={city_slug}&preference={preference}"
        f"&area_unit=1&res_com={res_com}"
    )

    print(f"URL: {url}")
    driver.get(url)
    time.sleep(5)  # wait for JS to load content

    html = driver.page_source
    print(f"html: {html}")

    # Look for pattern like "42031 results"
    match = re.search(r'([\d,]+)\s+results', html)
    print(f"match: {match}")
    if match:
        count_str = match.group(1).replace(",", "")
        return int(count_str)
    else:
        print(f"[99acres] ❌ Count not found for {city}-{segment}-{property_type}")
        return 0

# ------------------ RUN SCRAPER ------------------
for city in CITIES:
    for segment in SEGMENTS:
        for prop_type in PROPERTY_TYPES:
            count = get_99acres_count(city, segment, prop_type)
            print(f"✅ {city}-{segment}-{prop_type}: {count}")

driver.quit()
