from typing import TypedDict


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
