import time
import json
import uuid
import sys
import re as regexp
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser
from typing import TypedDict, Final
from pathlib import Path
from math import ceil


class ReviewsInfo(TypedDict):
    count: int | None
    stars: int | None
    url: str | None


class SellerInfo(TypedDict):
    name: str | None
    heading: str | None
    verified: bool | None
    pfp: str | None
    profile_url: str | None
    reviews_count: int | None
    reviews_stars: int | None
    reviews_url: str | None
    followers: int | None
    listings_sold: int | None


class ListingMetadata(TypedDict):
    uuid: str
    title: str
    url: str


class ListingMedia(TypedDict):
    thumbnail_url: str
    images: list[str]


class ListingStatus(TypedDict):
    price: str | None
    shipping_cost: float | None
    sold_out: bool


class ListingDetails(TypedDict):
    description: str


class ListingData(TypedDict):
    metadata: ListingMetadata
    media: ListingMedia
    status: ListingStatus
    details: ListingDetails


class ListingsDict(TypedDict):
    seller_info: SellerInfo
    listings: list[ListingData]


class ListingResponse(TypedDict):
    description: str
    images: list[str]
    shipping_cost: float | None


start_time = time.time()

charlies_computers_page: Final[str] = "https://www.jawa.gg/sp/184151/charlies-computers"
image_proxy: Final[str] = "https://external-content.duckduckgo.com/iu/?u="
jawa_base_url: Final[str] = "https://www.jawa.gg"
listings_grid_query: Final[str] = "div.tw-group.tw-relative"

output_dir: Final[Path] = Path(__file__).parent.parent / "output"
output_file: Final[Path] = output_dir / "listings.json"
output_dir.mkdir(parents=True, exist_ok=True)
output_file.unlink(missing_ok=True)
output_file.touch(exist_ok=True)


def get_seller_info(seller_page_url: str, seller_page_html: str) -> SellerInfo:
    print(f"Fetching seller info from {seller_page_url}...")

    soup = BeautifulSoup(seller_page_html, 'html.parser')

    seller_area_children = soup.select('section.tw-grid.tw-grid-cols-1.tw-gap-8 > div > div > div,h1')

    seller_info_card = seller_area_children[0]
    heading = seller_area_children[1].get_text(strip=True)
    # note: [2] is the container for the follow/message buttons
    followers_info = seller_area_children[3].get_text(strip=True).split('•')

    seller_pfp_container = seller_info_card.select('div.tw-relative.tw-z-\\[100\\]')[0]
    seller_info_container = seller_info_card.select('div.tw-flex.tw-flex-col.tw-gap-1')[0]

    pfp_url = seller_pfp_container.select('div > img')[0]['src']
    verified = bool(seller_pfp_container.select_one('img[alt="Jawa Verified"]'))

    seller_name = seller_info_container.select('div.tw-flex > div')[0].get_text(strip=True)
    reviews_container = seller_info_container.select('a')[0]

    reviews_url = urljoin(jawa_base_url, reviews_container['href'].__str__())
    reviews_stars = ceil(float(str(reviews_container.select('div.tw-pt-1')[0].get_text(strip=True))))
    def get_review_count(text: str):  # noqa: E306
        return int(regexp.sub(r'\D', '', text))
    reviews_count = get_review_count(str(reviews_container.select('div.tw-pt-1')[1].get_text(strip=True)))

    followers = int(followers_info[0].replace('followers', '').strip())
    listings_sold = int(followers_info[2].replace('sold', '').strip())

    return {
        "name": seller_name,
        "heading": heading,
        "verified": verified,
        "pfp": image_proxy + str(pfp_url),
        "profile_url": seller_page_url,
        "reviews_count": reviews_count,
        "reviews_stars": reviews_stars,
        "reviews_url": reviews_url,
        "followers": followers,
        "listings_sold": listings_sold
    }


def crawl_listing_details(listing_url: str, name: str, sold: bool, chromium: Browser) -> ListingResponse:
    with chromium.new_page() as page:
        print(f"Crawling details for listing '{name}'...")
        page.goto(listing_url)
        page.wait_for_load_state('domcontentloaded')  # ensure DOM load
        html_content = page.content()

    soup = BeautifulSoup(html_content, 'html.parser')

    json_ld_tag = soup.find('script', type='application/ld+json')
    if json_ld_tag:
        try:
            # use json data that is conveniently at the top of the page
            json_ld_data = json.loads(json_ld_tag.string or '{}')
            description: str = json_ld_data.get('description', 'No description')
            offers: dict = json_ld_data.get('offers', {})
            shipping_cost = offers.get('shippingDetails', {}).get('shippingRate', {}).get('value', None)

            images: list[str] = [
                img['src'] for img in soup.select(
                    'div.tw-hidden div.swiper.swiper-horizontal div.swiper-wrapper img'
                ) if 'src' in img.attrs
            ]  # type: ignore
            for index, image in enumerate(images):
                if image.startswith('/'):
                    images[index] = urljoin(jawa_base_url, image)
                images[index] = image_proxy + image

            return {
                "description": description,
                "images": images,
                "shipping_cost": shipping_cost,
            }
        except json.JSONDecodeError:
            raise Exception(f"Error decoding JSON-LD data for {listing_url}")

    return {
        "description": "No description",
        "images": [],
        "shipping_cost": None,
    }


def main(chromium: Browser) -> None:
    with chromium.new_page() as page:
        page.goto(charlies_computers_page)
        page.wait_for_selector(listings_grid_query, state='visible')
        seller_page_html: str = page.content()
        seller_info = get_seller_info(charlies_computers_page, seller_page_html)

        print(f"Crawling listings from {charlies_computers_page}...")

    soup = BeautifulSoup(seller_page_html, 'html.parser')

    listings_grid = soup.select(listings_grid_query)

    listings_dict: ListingsDict = {
        "seller_info": seller_info,
        "listings": []
    }
    listings_data = listings_dict["listings"]

    for listing_container in listings_grid:
        try:
            listing_url_tag = listing_container.select_one('a')
            listing_url = str(listing_url_tag['href']) if listing_url_tag else "#"
            if listing_url.startswith('/'):
                listing_url = urljoin(jawa_base_url, listing_url)

            listing_uuid = uuid.uuid5(uuid.NAMESPACE_URL, listing_url).__str__()

            image_tag = listing_container.select_one('img')
            thumbnail_url = str(image_tag['src']) if image_tag else ""
            if thumbnail_url.startswith('/'):
                thumbnail_url = urljoin(jawa_base_url, thumbnail_url)
            thumbnail_url = image_proxy + thumbnail_url

            title_tag = listing_container.select_one('div.tw-paragraph-m-bold')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"

            sold_out_tag = listing_container.select_one("div.tw-text-4xl.tw-font-bold")
            sold_out = bool(sold_out_tag and "Sold out" in sold_out_tag.get_text())

            price_tag = listing_container.select_one('div.tw-paragraph-m-bold.tw-text-brand-primary')
            price = price_tag.get_text(strip=True) if price_tag else None

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
        json.dump(listings_dict, file, indent=4)

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
