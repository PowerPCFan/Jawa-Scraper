import json
import sys
import simple_timer
import crawlers
from playwright.sync_api import sync_playwright, Browser
from typed_dicts import ListingsDict
from global_vars import charlies_computers_page, listings_grid_query, output_file


simple_timer.start()


def main(chromium: Browser) -> None:
    with chromium.new_page() as page:
        page.goto(charlies_computers_page)
        page.wait_for_selector(listings_grid_query, state='visible')
        seller_page_html: str = page.content()

    listings_dict: ListingsDict = {
        "seller_info": crawlers.crawl_seller_info(charlies_computers_page, seller_page_html),
        "listings": crawlers.crawl_seller_listings(seller_page_html, chromium)
    }

    with open(output_file, mode='w', encoding='utf-8') as file:
        print(f"Writing JSON data to {output_file}...")
        json.dump(listings_dict, file, indent=4)

    print(f"Time elapsed: {simple_timer.end():.2f} seconds")


if __name__ == "__main__":
    try:
        print("Launching Chromium...")
        with sync_playwright() as playwright:
            with playwright.chromium.launch(headless=True) as chromium:
                print("Starting up the scraper...\n")
                main(chromium)
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
