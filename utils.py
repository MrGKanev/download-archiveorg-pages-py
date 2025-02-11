import os
import re
import logging
import mimetypes
from urllib.parse import urlparse, urljoin

logger = logging.getLogger('WaybackDownloader')


def safe_url_join(base, url):
    """Safely join base URL with another URL."""
    if not base or not url:
        return None
    try:
        return urljoin(str(base), str(url))
    except Exception as e:
        logger.error(f"Error joining URLs {base} and {url}: {e}")
        return None


def get_base_url(url):
    """Safely extract base URL."""
    if not url:
        return None
    try:
        parsed = urlparse(str(url))
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
    except Exception as e:
        logger.error(f"Error getting base URL from {url}: {e}")
        return None


def clean_url(url):
    """Remove archive.org components from URL."""
    if not url:
        return None

    try:
        # Convert to string if needed
        url = str(url)

        # Handle data URLs
        if url.startswith('data:'):
            return url

        # Remove archive.org components
        if 'web.archive.org/web/' in url:
            match = re.search(r'/web/\d+/(https?://)?(.+)', url)
            if match:
                cleaned = match.group(2)
                if not cleaned.startswith(('http://', 'https://')):
                    cleaned = 'http://' + cleaned
                return cleaned

        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        return url

    except Exception as e:
        logger.error(f"Error cleaning URL {url}: {e}")
        return None


def get_asset_path(url, content_type=None):
    """Generate appropriate asset path."""
    if not url:
        return None

    try:
        parsed = urlparse(url)
        path = parsed.path.lstrip('/')

        if not path:
            path = 'index.html'
        elif not os.path.splitext(path)[1]:
            # No extension, try to determine from content type
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    path += ext
            else:
                path += '.html'

        return os.path.join('assets', path)

    except Exception as e:
        logger.error(f"Error generating asset path for {url}: {e}")
        return None


def save_to_file(content, base_path, relative_path):
    """Save content to file system."""
    if not content or not base_path or not relative_path:
        return False

    try:
        full_path = os.path.join(base_path, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        if isinstance(content, str):
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            with open(full_path, 'wb') as f:
                f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error saving to {full_path}: {e}")
        return False