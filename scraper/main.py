# i hate this code

import time
import json
import uuid
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser
from typing import Any, Final, Union
from pathlib import Path
from contextlib import suppress


def crawl_listing_details(listing_url: str, name: str, sold: bool, chromium: Browser) -> dict[str, Any]:
    with chromium.new_page() as page:
        print(f"\nCrawling details for listing '{name}'...")
        page.goto(listing_url)
        page.wait_for_load_state('domcontentloaded')  # ensure DOM load
        html_content = page.content()

        # handle the checkout page url stuff here too, since we're already on the listing page
        checkout_page_url: str | None = None
        if not sold:
            print(f"Listing is still available, fetching checkout page URL for listing '{name}'...")
            # set as listing url just in case it fails
            checkout_page_url = listing_url
            with suppress(Exception):
                with page.expect_navigation(wait_until='domcontentloaded'):
                    page.click("text=Buy Now")
                checkout_page_url = page.url

    soup = BeautifulSoup(html_content, 'html.parser')

    json_ld_tag = soup.find('script', type='application/ld+json')
    if json_ld_tag:
        try:
            # use json data that is conveniently at the top of the page
            json_ld_data: dict[str, Any] = json.loads(json_ld_tag.string or '{}')
            description: str = json_ld_data.get('description', 'No description')
            offers: dict = json_ld_data.get('offers', {})
            shipping_cost = offers.get('shippingDetails', {}).get('shippingRate', {}).get('value', None)

            images: list = [
                img['src'] for img in soup.select(
                    'div.tw-hidden div.swiper.swiper-horizontal div.swiper-wrapper img'
                ) if 'src' in img.attrs
            ]

            return {
                "description": description,
                "images": images,
                "shipping_cost": shipping_cost,
                "checkout_page_url": checkout_page_url
            }
        except json.JSONDecodeError:
            raise Exception(f"Error decoding JSON-LD data for {listing_url}")

    return {
        "description": "No description",
        "images": [],
        "shipping_cost": None,
        "checkout_page_url": None
    }


def main(chromium: Browser) -> None:
    start_time = time.time()

    charlies_computers_page: Final[str] = "https://www.jawa.gg/sp/184151/charlies-computers"
    listings_grid_query: Final[str] = "div.tw-group.tw-relative"

    output_dir: Final[Path] = Path(__file__).parent.parent / "output"
    output_file: Final[Path] = output_dir / "listings.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)
    output_file.touch(exist_ok=True)

    with chromium.new_page() as page:
        print(f"Crawling listings from {charlies_computers_page}...")
        page.goto(charlies_computers_page)
        # ensure that the listings are loaded and visible
        page.wait_for_selector(listings_grid_query, state='visible')
        html: str = page.content()

    soup = BeautifulSoup(html, 'html.parser')

    listings_grid = soup.select(listings_grid_query)

    listings_dict: dict[str, list[dict[str, Union[str, bool, dict[str, Union[str, bool, None]], None]]]] = {
        "listings": []
    }
    listings_data = listings_dict["listings"]

    for listing_container in listings_grid:
        try:
            listing_url_tag = listing_container.select_one('a')
            listing_url = str(listing_url_tag['href']) if listing_url_tag else "#"
            if listing_url.startswith('/'):
                listing_url = urljoin("https://www.jawa.gg", listing_url)

            listing_uuid = uuid.uuid5(uuid.NAMESPACE_URL, listing_url).__str__()

            image_tag = listing_container.select_one('img')
            thumbnail_url = str(image_tag['src']) if image_tag else ""
            if thumbnail_url.startswith('/'):
                thumbnail_url = urljoin("https://www.jawa.gg", thumbnail_url)

            title_tag = listing_container.select_one('div.tw-paragraph-m-bold')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"

            sold_out_tag = listing_container.select_one("div.tw-text-4xl.tw-font-bold")
            sold_out = bool(sold_out_tag and "Sold out" in sold_out_tag.get_text())

            price_tag = listing_container.select_one('div.tw-paragraph-m-bold.tw-text-brand-primary')
            price = price_tag.get_text(strip=True) if price_tag else None

            # temp_listings_data.append({
            #     "uuid": listing_uuid,
            #     "title": title,
            #     "url": listing_url,
            #     "thumbnail_url": thumbnail_url,
            #     "price": price,
            #     "sold_out": sold_out
            # })

            details = crawl_listing_details(
                listing_url,
                title,
                sold_out,
                chromium
            )

            listings_data.append({
                "metadata": {
                    "uuid": listing_uuid,
                    "title": title,
                    "url": listing_url,
                    "checkout_page_url": details['checkout_page_url'],
                },
                "media": {
                    "thumbnail_url": thumbnail_url,
                    "images": details['images'],

                },
                "status": {
                    "price": price,
                    "shipping_cost": details['shipping_cost'],
                    "sold_out": sold_out
                },
                "details": {
                    "description": details['description']
                }
            })
        except Exception as e:
            raise Exception(f"Error processing listing: {e}")

    with open(output_file, mode='w', encoding='utf-8') as file:
        print(f"Writing JSON data to {output_file}...")
        json.dump(listings_data, file, indent=4)

    end_time = time.time()
    print(f"Time elapsed: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(headless=True) as chromium:
                main(chromium)
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
