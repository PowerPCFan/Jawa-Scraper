from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from typing import Final
from pathlib import Path
import json

charlies_computers_page: Final[str] = "https://www.jawa.gg/sp/184151/charlies-computers"
listings_grid_query: Final[str] = "div.tw-group.tw-relative"
discounted_price_query: Final[str] = "div.tw-font-bold"
original_price_query: Final[str] = "div.tw-line-through"

output_dir: Final[Path] = Path(__file__).parent.parent / "output"
output_file: Final[Path] = output_dir / "listings.json"
output_dir.mkdir(parents=True, exist_ok=True)
output_file.unlink(missing_ok=True)
output_file.touch(exist_ok=True)

with sync_playwright() as playwright:
    with playwright.chromium.launch(headless=True) as chromium:
        with chromium.new_page() as page:
            page.goto(charlies_computers_page)
            page.wait_for_selector(listings_grid_query)
            html: str = page.content()

soup = BeautifulSoup(html, 'html.parser')

listings_grid = soup.select(listings_grid_query)

listings_dict: dict[str, list[dict[str, str | bool]]] = {
    "listings": []
}
listings_data = listings_dict["listings"]

for listing_container in listings_grid:
    try:
        listing_url_tag = listing_container.select_one('a')
        listing_url = str(listing_url_tag['href']) if listing_url_tag else "#"
        if listing_url.startswith('/'):
            listing_url = urljoin("https://www.jawa.gg", listing_url)

        image_tag = listing_container.select_one('img')
        image_url = str(image_tag['src']) if image_tag else ""
        if image_url.startswith('/'):
            image_url = urljoin("https://www.jawa.gg", image_url)

        title_tag = listing_container.select_one('div.tw-paragraph-m-bold')
        title = title_tag.get_text(strip=True) if title_tag else "No Title"

        sold_out_tag = listing_container.select_one("div.tw-text-4xl.tw-font-bold")
        sold_out = bool(sold_out_tag and "Sold out" in sold_out_tag.get_text())

        price_tag = listing_container.select_one('div.tw-paragraph-m-bold.tw-text-brand-primary')
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        listings_data.append({
            "title": title,
            "url": listing_url,
            "image_url": image_url,
            "price": price,
            "sold_out": sold_out
        })
    except Exception as e:
        print(f"Error processing listing: {e}")
        pass

with open(output_file, mode='w', encoding='utf-8') as file:
    json.dump(listings_data, file, indent=4)
