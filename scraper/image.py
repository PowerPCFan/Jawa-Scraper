import requests
import io
import uuid
from PIL import Image
from global_vars import image_save_dir, image_url_prefix


def detect_format(
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
def download(image_url: str) -> str:  # noqa: E302
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

        img_format = detect_format(
            image_data=response.content,
            response=response
        )

        extension = f".{img_format}" if img_format else ".bin"

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
