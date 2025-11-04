from typing import Final
from pathlib import Path

charlies_computers_page: Final[str] = "https://www.jawa.gg/sp/184151/charlies-computers"
image_url_prefix: Final[str] = "https://raw.githubusercontent.com/PowerPCFan/Jawa-Scraper/refs/heads/main/output/images"
jawa_base_url: Final[str] = "https://www.jawa.gg"
listings_grid_query: Final[str] = "div.tw-group.tw-relative"

output_dir: Final[Path] = Path(__file__).parent.parent / "output"
output_file: Final[Path] = output_dir / "listings.json"
image_save_dir: Final[Path] = output_dir / "images"
output_dir.mkdir(parents=True, exist_ok=True)
output_file.unlink(missing_ok=True)
output_file.touch(exist_ok=True)
image_save_dir.mkdir(exist_ok=True)
