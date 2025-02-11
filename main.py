import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import os
import time
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
import re
import mimetypes
import hashlib
from concurrent.futures import ThreadPoolExecutor
import logging
import cssutils
from pathlib import Path


class WaybackDownloader:
    def __init__(self, output_dir="downloaded_pages", max_depth=2, max_retries=5, concurrent_downloads=5):
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.max_retries = max_retries
        self.concurrent_downloads = concurrent_downloads
        self.downloaded_urls = set()
        self.processed_assets = set()

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('WaybackDownloader')

        # Suppress cssutils logging
        cssutils.log.setLevel(logging.CRITICAL)

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Configure session with retries
        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Set reasonable timeout
        self.session.timeout = (10, 30)  # (connect timeout, read timeout)

    def get_wayback_url(self, url, timestamp):
        """Construct proper wayback URL."""
        if not url:
            return None
        try:
            clean_url = self.clean_url(url)
            if not clean_url:
                return None
            return f"https://web.archive.org/web/{timestamp}/{clean_url}"
        except Exception as e:
            self.logger.error(f"Error constructing wayback URL for {url}: {e}")
            return None

    def get_snapshots(self, url, from_date=None, to_date=None):
        """Get list of available snapshots for a URL."""
        try:
            cdx_api_url = "https://web.archive.org/cdx/search/cdx"
            params = {
                'url': url,
                'output': 'json',
                'fl': 'timestamp,original,statuscode,digest',
                'filter': 'statuscode:200',
                'collapse': 'digest'
            }

            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date

            self.logger.info(f"Fetching snapshots with params: {params}")
            response = self.session.get(cdx_api_url, params=params)
            response.raise_for_status()

            results = response.json()
            if not results or len(results) < 2:
                return []

            return results[1:]  # Skip header row

        except Exception as e:
            self.logger.error(f"Error fetching snapshots: {e}")
            return []

    def clean_url(self, url):
        """Remove archive.org components from URL."""
        if not url:
            return None

        try:
            # Convert to string if needed
            url = str(url)

            # Remove archive.org components
            if 'web.archive.org/web/' in url:
                match = re.search(r'/web/\d+/(https?://)?(.+)', url)
                if match:
                    return 'http://' + match.group(2) if not match.group(1) else match.group(1) + match.group(2)

            return url

        except Exception as e:
            self.logger.error(f"Error cleaning URL {url}: {e}")
            return None

    def download_with_retry(self, url, timeout=(10, 30)):
        """Download URL with retry logic."""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return None

    def save_asset(self, content, base_path, asset_path):
        """Save asset to file system."""
        try:
            full_path = os.path.join(base_path, asset_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'wb') as f:
                f.write(content)
            return True
        except Exception as e:
            self.logger.error(f"Error saving asset to {full_path}: {e}")
            return False

    def download_asset(self, url, timestamp, base_path):
        """Download and save an individual asset."""
        if not url or url in self.processed_assets:
            return None

        self.processed_assets.add(url)

        try:
            wayback_url = self.get_wayback_url(url, timestamp)
            if not wayback_url:
                return None

            self.logger.debug(f"Downloading asset: {wayback_url}")
            response = self.download_with_retry(wayback_url)

            if not response:
                return None

            # Generate asset path
            parsed_url = urlparse(url)
            path = parsed_url.path.lstrip('/')
            if not path:
                path = 'index.html'

            # Create asset directory
            asset_dir = os.path.join(base_path, 'assets', os.path.dirname(path))
            os.makedirs(asset_dir, exist_ok=True)

            # Save asset
            asset_path = os.path.join('assets', path)
            if self.save_asset(response.content, base_path, asset_path):
                return asset_path

            return None

        except Exception as e:
            self.logger.error(f"Error processing asset {url}: {e}")
            return None

    def process_html(self, content, timestamp, base_path, original_url):
        """Process HTML content to download assets and fix links."""
        if not content:
            return None

        try:
            soup = BeautifulSoup(content, 'html.parser')
            base_url = urlparse(original_url).scheme + '://' + urlparse(original_url).netloc

            # Remove archive.org elements
            for element in soup.find_all(['script', 'style', 'link', 'iframe']):
                if 'archive.org' in str(element):
                    element.decompose()

            # Process assets
            asset_tags = {
                'img': 'src',
                'script': 'src',
                'link': 'href',
                'audio': 'src',
                'video': 'src',
                'source': 'src',
            }

            with ThreadPoolExecutor(max_workers=self.concurrent_downloads) as executor:
                futures = []

                for tag, attr in asset_tags.items():
                    for element in soup.find_all(tag):
                        if element.get(attr):
                            url = element[attr]
                            if url and not url.startswith(('data:', 'javascript:', '#')):
                                full_url = urljoin(base_url, self.clean_url(url))
                                futures.append((element, attr, executor.submit(
                                    self.download_asset, full_url, timestamp, base_path)))

                for element, attr, future in futures:
                    try:
                        new_path = future.result()
                        if new_path:
                            element[attr] = new_path
                    except Exception as e:
                        self.logger.error(f"Error processing asset future: {e}")

            return str(soup)

        except Exception as e:
            self.logger.error(f"Error processing HTML: {e}")
            return None

    def download_page(self, url, timestamp, depth=0, visited=None):
        """Download a specific snapshot of a URL and its linked pages."""
        if visited is None:
            visited = set()

        if not url or url in visited or depth > self.max_depth:
            return None

        visited.add(url)

        try:
            wayback_url = self.get_wayback_url(url, timestamp)
            if not wayback_url:
                return None

            self.logger.info(f"Downloading page: {wayback_url}")
            response = self.download_with_retry(wayback_url)

            if not response:
                return None

            # Create directory for this download
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace(".", "_")
            page_dir = f"{domain}_{timestamp}"
            full_path = os.path.join(self.output_dir, page_dir)

            os.makedirs(full_path, exist_ok=True)

            # Process the HTML content
            processed_html = self.process_html(response.content, timestamp, full_path, url)
            if not processed_html:
                return None

            # Save the processed HTML
            filepath = os.path.join(full_path, 'index.html')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(processed_html)

            self.logger.info(f"Saved page to: {filepath}")

            # Process links if not at max depth
            if depth < self.max_depth:
                soup = BeautifulSoup(processed_html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        next_url = urljoin(url, self.clean_url(href))
                        if urlparse(next_url).netloc == parsed_url.netloc:
                            self.download_page(next_url, timestamp, depth + 1, visited)
                            time.sleep(1)  # Rate limiting

            return filepath

        except Exception as e:
            self.logger.error(f"Error downloading page {url}: {e}")
            return None


def main():
    try:
        downloader = WaybackDownloader(
            max_depth=int(input("Enter maximum crawl depth (0-5): ")),
            max_retries=5,
            concurrent_downloads=5
        )

        url = input("Enter the URL to download (e.g., example.com): ")
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        from_date = input("Enter start date (YYYYMMDD) or press Enter to skip: ")
        to_date = input("Enter end date (YYYYMMDD) or press Enter to skip: ")

        print(f"Fetching snapshots for {url}...")
        snapshots = downloader.get_snapshots(url, from_date, to_date)

        if not snapshots:
            print("No snapshots found for the given URL and date range.")
            return

        print(f"Found {len(snapshots)} snapshots.")

        for snapshot in snapshots:
            timestamp = snapshot[0]
            formatted_date = datetime.strptime(timestamp, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
            print(f"\nDownloading snapshot from {formatted_date}...")

            try:
                filepath = downloader.download_page(url, timestamp)
                if filepath:
                    print(f"Saved to: {filepath}")
                time.sleep(2)  # Rate limiting
            except Exception as e:
                print(f"Error downloading snapshot: {e}")
                continue

        print("\nDownload complete!")

    except Exception as e:
        print(f"An error occurred in main: {e}")
        raise


if __name__ == "__main__":
    main()