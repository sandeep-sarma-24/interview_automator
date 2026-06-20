"""Point every test at an isolated temp database BEFORE app modules import."""
import os
import tempfile

# Set the base dir at collection time, before app.config is first read.
os.environ["SCRAPER_BASE_DIR"] = tempfile.mkdtemp(prefix="jobcopilot-test-")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()
