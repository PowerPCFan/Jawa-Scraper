import time
import json
import uuid
import sys
import math
import requests
import io
import re as regexp
from PIL import Image
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser
from typing import TypedDict, Final
from pathlib import Path


class ReviewsInfo(TypedDict):
    count: int
    stars: int
    url: str


class SellerProfile(TypedDict):
    url: str
    picture: str
    name: str
    verified: bool
    followers: int
    sold: int


class SellerInfo(TypedDict):
    profile: SellerProfile
    reviews: ReviewsInfo
    images: list[str]
    heading: str


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
image_url_prefix: Final[str] = "https://raw.githubusercontent.com/PowerPCFan/shop/refs/heads/main/output/images"
jawa_base_url: Final[str] = "https://www.jawa.gg"
listings_grid_query: Final[str] = "div.tw-group.tw-relative"

output_dir: Final[Path] = Path(__file__).parent.parent / "output"
output_file: Final[Path] = output_dir / "listings.json"
image_save_dir: Final[Path] = output_dir / "images"
output_dir.mkdir(parents=True, exist_ok=True)
output_file.unlink(missing_ok=True)
output_file.touch(exist_ok=True)
image_save_dir.mkdir(exist_ok=True)


def detect_image_format(
    image_data: bytes | None = None,
    response: requests.Response | None = None
) -> str | None:
    """
    *Written by Claude Sonnet 4*

    Comprehensive image format detector using multiple methods in order of speed:
    1. Magic number detection (fastest)
    2. HTTP Content-Type header
    3. Pillow format detection (requires PIL/Pillow)
    4. URL extension fallback

    Args:
        image_data: Raw image bytes
        response: HTTP response object (for Content-Type header)

    Returns:
        Image format as lowercase string ('jpeg', 'png', 'gif', 'webp', etc.)
        Returns `None` if format cannot be determined
    """

    # Method 1: Magic Number Detection (Fastest)
    if image_data:
        if image_data.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif image_data.startswith(b'RIFF') and len(image_data) >= 12 and b'WEBP' in image_data[8:12]:
            return 'webp'
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            return 'gif'
        elif image_data.startswith(b'\x00\x00\x01\x00') or image_data.startswith(b'\x00\x00\x02\x00'):
            return 'ico'
        elif image_data.startswith(b'BM'):
            return 'bmp'
        elif image_data.startswith(b'II*\x00') or image_data.startswith(b'MM\x00*'):
            return 'tiff'
        elif image_data.startswith(b'<?xml') or image_data.startswith(b'<svg'):
            return 'svg'
        elif len(image_data) >= 12 and b'ftypavif' in image_data[4:12]:
            return 'avif'
        elif len(image_data) >= 12 and (b'ftypheic' in image_data[4:12] or b'ftypmif1' in image_data[4:12]):
            return 'heic'

    # Method 2: HTTP Content-Type Header
    if response:
        content_type = response.headers.get('content-type', '').lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            return 'jpeg'
        elif 'png' in content_type:
            return 'png'
        elif 'gif' in content_type:
            return 'gif'
        elif 'webp' in content_type:
            return 'webp'
        elif 'bmp' in content_type:
            return 'bmp'
        elif 'tiff' in content_type or 'tif' in content_type:
            return 'tiff'
        elif 'svg' in content_type:
            return 'svg'
        elif 'avif' in content_type:
            return 'avif'
        elif 'heic' in content_type or 'heif' in content_type:
            return 'heic'
        elif 'ico' in content_type or 'icon' in content_type:
            return 'ico'

    # Method 3: Pillow Detection (Most Accurate)
    try:
        if image_data:
            with Image.open(io.BytesIO(image_data)) as img:
                format_name = img.format
                if format_name:
                    return format_name.lower()
    except Exception:
        pass
    return None


downloaded_images: set[str] = set()
def download_image(image_url: str) -> str:  # noqa: E302
    """
    *Written by Claude Sonnet 4*

    Download an image from Jawa and save it locally, with UUID-based naming.

    Args:
        image_url: The original image URL from Jawa

    Returns:
        The GitHub raw URL if download succeeds, otherwise the original URL
    """
    if not image_url or not image_url.startswith('https://www.jawa.gg/'):
        return image_url

    try:
        original_path = image_url.replace('https://www.jawa.gg/', '')

        path_parts = original_path.split('/')
        original_filename = path_parts[-1] if path_parts else original_path
        directory_path = '/'.join(path_parts[:-1]) if len(path_parts) > 1 else ''

        filename_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, original_filename))

        search_pattern = image_save_dir / directory_path / filename_uuid
        parent_dir = search_pattern.parent

        if parent_dir.exists():
            existing_files = list(parent_dir.glob(f"{filename_uuid}.*"))
            if existing_files:
                relative_path = existing_files[0].relative_to(image_save_dir)
                return f"{image_url_prefix}/{relative_path.as_posix()}"

        print(f"Downloading image: {original_filename}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        image_format = detect_image_format(
            image_data=response.content,
            response=response
        )

        extension = f".{image_format}" if image_format else ".bin"

        final_filename = f"{filename_uuid}{extension}"
        if directory_path:
            local_file_path = image_save_dir / directory_path / final_filename
        else:
            local_file_path = image_save_dir / final_filename

        local_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_file_path, 'wb') as f:
            f.write(response.content)
        relative_path = local_file_path.relative_to(image_save_dir)
        return f"{image_url_prefix}/{relative_path.as_posix()}"

    except Exception as e:
        print(f"Failed to download image {image_url}: {e}")
        return image_url


def get_seller_info(seller_page_url: str, seller_page_html: str) -> SellerInfo:
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
            "picture": download_image(str(pfp_url)),
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
            download_image(img) for img in images
        ],
        "heading": heading,
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
                images[index] = download_image(images[index])

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


def crawl_seller_listings(seller_page_html: str) -> list[ListingData]:
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

            downloaded_thumbnail_url = download_image(thumbnail_url)

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


def main(chromium: Browser) -> None:
    with chromium.new_page() as page:
        page.goto(charlies_computers_page)
        page.wait_for_selector(listings_grid_query, state='visible')
        seller_page_html: str = page.content()

    listings_dict: ListingsDict = {
        "seller_info": get_seller_info(charlies_computers_page, seller_page_html),
        "listings": crawl_seller_listings(seller_page_html)
    }

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
