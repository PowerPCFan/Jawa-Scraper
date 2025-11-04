import json
import uuid
import math
import image
import re as regexp
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import Browser
from typed_dicts import SellerInfo, ListingResponse, ListingData
from global_vars import jawa_base_url, charlies_computers_page, listings_grid_query


def crawl_seller_info(seller_page_url: str, seller_page_html: str) -> SellerInfo:
    print(f"Fetching seller info from {seller_page_url}...")

    soup = BeautifulSoup(seller_page_html, 'html.parser')

    seller_area_children = soup.select('section.tw-grid.tw-grid-cols-1.tw-gap-8 > div > div > div,h1')

    # basically the same selector as seller_area_children since it matches both sections with a different list index
    image_swiper_slides = soup.select('section.tw-grid.tw-grid-cols-1.tw-gap-8 > div > div > div > div')
    # remove first two "slides" that are part of seller area
    image_swiper_slides = image_swiper_slides[2:]

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
    reviews_stars = math.ceil(float(str(reviews_container.select('div.tw-pt-1')[0].get_text(strip=True))))
    def get_review_count(text: str):  # noqa: E306
        return int(regexp.sub(r'\D', '', text))
    reviews_count = get_review_count(str(reviews_container.select('div.tw-pt-1')[1].get_text(strip=True)))

    followers = int(followers_info[0].replace('followers', '').strip())
    listings_sold = int(followers_info[2].replace('sold', '').strip())

    # each swiper slide container has an image inside, and each slide has a data-swiper-slide-index attribute
    # sort slides by their data-swiper-slide-index attribute to keep the order that the seller set
    def get_slide_index(slide):
        index_attr = slide.get('data-swiper-slide-index')
        if index_attr is None:
            return 0
        return int(str(index_attr))

    images = [str(slide.select('img')[0]['src']) for slide in sorted(image_swiper_slides, key=get_slide_index)]

    return {
        "profile": {
            "url": seller_page_url,
            "picture": image.download(str(pfp_url)),
            "name": seller_name,
            "verified": verified,
            "followers": followers,
            "sold": listings_sold
        },
        "reviews": {
            "count": reviews_count,
            "stars": reviews_stars,
            "url": reviews_url
        },
        "images": [
            image.download(img) for img in images
        ],
        "heading": heading,
    }


def crawl_seller_listing_details(listing_url: str, name: str, sold: bool, chromium: Browser) -> ListingResponse:
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
            for index, img in enumerate(images):
                if img.startswith('/'):
                    images[index] = urljoin(jawa_base_url, img)
                images[index] = image.download(images[index])

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


def crawl_seller_listings(seller_page_html: str, chromium: Browser) -> list[ListingData]:
    print(f"Crawling listings from {charlies_computers_page}...")

    soup = BeautifulSoup(seller_page_html, 'html.parser')

    listing_data_list: list[ListingData] = []

    listings_grid = soup.select(listings_grid_query)

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

            downloaded_thumbnail_url = image.download(thumbnail_url)

            title_tag = listing_container.select_one('div.tw-paragraph-m-bold')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"

            sold_out_tag = listing_container.select_one("div.tw-text-4xl.tw-font-bold")
            sold_out = bool(sold_out_tag and "Sold out" in sold_out_tag.get_text())

            price_tag = listing_container.select_one('div.tw-paragraph-m-bold.tw-text-brand-primary')
            price = price_tag.get_text(strip=True) if price_tag else None

            details = crawl_seller_listing_details(
                listing_url,
                title,
                sold_out,
                chromium
            )

            listing_data_list.append({
                "metadata": {
                    "uuid": listing_uuid,
                    "title": title,
                    "url": listing_url,
                },
                "media": {
                    "thumbnail_url": downloaded_thumbnail_url,
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

    return listing_data_list
