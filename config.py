import logging
import requests  # Added import
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Default configuration
DEFAULT_CONFIG = {
    'output_dir': "downloaded_pages",
    'max_depth': 2,
    'max_retries': 5,
    'concurrent_downloads': 5,
    'timeout': (10, 30),  # (connect timeout, read timeout)
}

# Retry configuration
RETRY_CONFIG = {
    'total': DEFAULT_CONFIG['max_retries'],
    'backoff_factor': 1,
    'status_forcelist': [429, 500, 502, 503, 504],
    'allowed_methods': ["HEAD", "GET", "OPTIONS"]
}

# Asset tags to process in HTML
ASSET_TAGS = {
    'img': ['src', 'data-src'],
    'script': ['src'],
    'link': ['href'],
    'audio': ['src'],
    'video': ['src'],
    'source': ['src'],
}


def setup_logging():
    """Configure logging settings."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger('WaybackDownloader')


def create_session(retries=None):
    """Create and configure requests session with retries."""
    if retries is None:
        retries = Retry(**RETRY_CONFIG)

    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.timeout = DEFAULT_CONFIG['timeout']

    return session