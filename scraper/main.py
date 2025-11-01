import time
import json
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from typing import Any, Final
from pathlib import Path


def crawl_listing_details(url: str, name: str) -> dict:
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as chromium:
            with chromium.new_page() as page:
                print(f"Crawling details for listing '{name}' ({url})...")
                page.goto(url)
                page.wait_for_timeout(5000)
                html_content = page.content()

    soup = BeautifulSoup(html_content, 'html.parser')

    json_ld_tag = soup.find('script', type='application/ld+json')
    if json_ld_tag:
        try:
            # use json data that is conveniently at the top of the page
            json_ld_data: dict[str, Any] = json.loads(json_ld_tag.string or '{}')
            description = json_ld_data.get('description', 'No description')
            offers: dict = json_ld_data.get('offers', {})
            shipping_cost = offers.get('shippingDetails', {}).get('shippingRate', {}).get('value', 'N/A')

            images = [
                img['src'] for img in soup.select(
                    'div.tw-hidden div.swiper.swiper-horizontal div.swiper-wrapper img'
                ) if 'src' in img.attrs
            ]

            return {
                "description": description,
                "images": images,
                "shipping_cost": shipping_cost
            }
        except json.JSONDecodeError:
            raise Exception(f"Error decoding JSON-LD data for {url}")

    return {
        "description": "No description",
        "images": [],
        "shipping_cost": "N/A"
    }


def main() -> None:
    start_time = time.time()

    charlies_computers_page: Final[str] = "https://www.jawa.gg/sp/184151/charlies-computers"
    listings_grid_query: Final[str] = "div.tw-group.tw-relative"

    output_dir: Final[Path] = Path(__file__).parent.parent / "output"
    output_file: Final[Path] = output_dir / "listings.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)
    output_file.touch(exist_ok=True)

    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as chromium:
            with chromium.new_page() as page:
                print(f"Crawling listings from {charlies_computers_page}...")
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
            thumbnail_url = str(image_tag['src']) if image_tag else ""
            if thumbnail_url.startswith('/'):
                thumbnail_url = urljoin("https://www.jawa.gg", thumbnail_url)

            title_tag = listing_container.select_one('div.tw-paragraph-m-bold')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"

            sold_out_tag = listing_container.select_one("div.tw-text-4xl.tw-font-bold")
            sold_out = bool(sold_out_tag and "Sold out" in sold_out_tag.get_text())

            price_tag = listing_container.select_one('div.tw-paragraph-m-bold.tw-text-brand-primary')
            price = price_tag.get_text(strip=True) if price_tag else "N/A"

            listings_data.append({
                "title": title,
                "url": listing_url,
                "thumbnail_url": thumbnail_url,
                "price": price,
                "sold_out": sold_out
            })
        except Exception as e:
            raise Exception(f"Error processing listing: {e}")

    for listing in listings_data:
        try:
            if isinstance(listing['url'], str):
                details = crawl_listing_details(listing['url'], listing['title'])  # type: ignore
                listing.update(details)
        except Exception as e:
            print(f"Error crawling details for {listing['url']}: {e}")

    with open(output_file, mode='w', encoding='utf-8') as file:
        print(f"Writing JSON data to {output_file}...")
        json.dump(listings_data, file, indent=4)

    end_time = time.time()
    print(f"Time elapsed: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
