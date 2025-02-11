import os
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import cssutils
import logging
import utils
from config import DEFAULT_CONFIG, ASSET_TAGS, setup_logging, create_session


class WaybackDownloader:
    def __init__(self, output_dir=None, max_depth=None, max_retries=None, concurrent_downloads=None):
        # Initialize with defaults or provided values
        self.output_dir = output_dir or DEFAULT_CONFIG['output_dir']
        self.max_depth = max_depth or DEFAULT_CONFIG['max_depth']
        self.max_retries = max_retries or DEFAULT_CONFIG['max_retries']
        self.concurrent_downloads = concurrent_downloads or DEFAULT_CONFIG['concurrent_downloads']

        # Initialize sets for tracking
        self.downloaded_urls = set()
        self.processed_assets = set()

        # Set up logging
        self.logger = setup_logging()

        # Suppress cssutils logging
        cssutils.log.setLevel(logging.CRITICAL)

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Create session
        self.session = create_session()

    def get_wayback_url(self, url, timestamp):
        """Construct proper wayback URL."""
        if not url or not timestamp:
            return None
        try:
            clean_url = utils.clean_url(url)
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

    def download_with_retry(self, url):
        """Download URL with retry logic."""
        if not url:
            return None

        try:
            self.logger.debug(f"Downloading: {url}")
            response = self.session.get(url)
            response.raise_for_status()
            return response
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return None

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

            content_type = response.headers.get('content-type', '').split(';')[0]
            asset_path = utils.get_asset_path(url, content_type)

            if not asset_path:
                return None

            if utils.save_to_file(response.content, base_path, asset_path):
                return asset_path

            return None

        except Exception as e:
            self.logger.error(f"Error processing asset {url}: {e}")
            return None

    def process_html(self, content, timestamp, base_path, original_url):
        """Process HTML content to download assets and fix links."""
        if not content or not timestamp or not base_path or not original_url:
            self.logger.error("Missing required parameters for HTML processing")
            return None

        try:
            # Convert content to string if needed
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8', errors='ignore')
                except Exception as e:
                    self.logger.error(f"Error decoding content: {e}")
                    return None

            soup = BeautifulSoup(content, 'html.parser')
            base_url = utils.get_base_url(original_url)

            if not base_url:
                self.logger.error("Could not determine base URL")
                return None

            # Remove archive.org elements
            for element in soup.find_all(['script', 'style', 'link', 'iframe']):
                if element and isinstance(element.string, str) and 'archive.org' in element.string:
                    element.decompose()

            # Process assets
            with ThreadPoolExecutor(max_workers=self.concurrent_downloads) as executor:
                futures = []

                for tag, attrs in ASSET_TAGS.items():
                    for element in soup.find_all(tag):
                        for attr in attrs:
                            if element.get(attr):
                                url = str(element[attr])
                                if url and not url.startswith(('data:', 'javascript:', '#', 'mailto:', 'tel:')):
                                    clean_url = utils.clean_url(url)
                                    if clean_url:
                                        full_url = utils.safe_url_join(base_url, clean_url)
                                        if full_url:
                                            futures.append((element, attr, executor.submit(
                                                self.download_asset, full_url, timestamp, base_path)))

                for element, attr, future in futures:
                    try:
                        new_path = future.result()
                        if new_path:
                            element[attr] = str(new_path)
                    except Exception as e:
                        self.logger.error(f"Error processing asset future: {e}")

            # Fix internal links
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    clean_href = utils.clean_url(href)
                    if clean_href:
                        joined_url = utils.safe_url_join(base_url, clean_href)
                        if joined_url:
                            a['href'] = str(joined_url)

            try:
                return str(soup)
            except Exception as e:
                self.logger.error(f"Error converting soup to string: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Error processing HTML: {e}")
            return None

    def get_menu_links(self, soup, base_url):
        """Extract menu/navigation links from the page."""
        menu_links = set()

        # Common menu/navigation selectors
        nav_selectors = [
            'nav',
            'header',
            '.menu',
            '.navigation',
            '#menu',
            '#nav',
            '.navbar',
            '[role="navigation"]',
            '.main-menu',
            '.primary-menu',
            '.top-menu',
            '#primary-menu',
            '.header-menu'
        ]

        # Find all navigation elements
        for selector in nav_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Get all links within this navigation element
                links = element.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        clean_href = utils.clean_url(href)
                        if clean_href:
                            full_url = utils.safe_url_join(base_url, clean_href)
                            if full_url:
                                menu_links.add(full_url)

        return menu_links

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
                self.logger.error("Failed to process HTML content")
                return None

            # Generate filename based on URL path
            path = parsed_url.path.strip('/')
            if not path:
                filename = 'index.html'
            else:
                # Convert path to filename
                filename = path.replace('/', '_') + '.html'

            # Save the processed HTML
            filepath = os.path.join(full_path, filename)
            if not utils.save_to_file(processed_html, full_path, filename):
                return None

            self.logger.info(f"Saved page to: {filepath}")

            # Process menu links first if not at max depth
            if depth < self.max_depth:
                soup = BeautifulSoup(processed_html, 'html.parser')
                menu_links = self.get_menu_links(soup, url)

                # Download menu links first
                for menu_url in menu_links:
                    if urlparse(menu_url).netloc == parsed_url.netloc:
                        self.download_page(menu_url, timestamp, depth + 1, visited)
                        time.sleep(1)  # Rate limiting

                # Then process other internal links if desired
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href and not href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                        clean_href = utils.clean_url(href)
                        if clean_href:
                            next_url = utils.safe_url_join(url, clean_href)
                            if next_url and next_url not in menu_links and urlparse(
                                    next_url).netloc == parsed_url.netloc:
                                self.download_page(next_url, timestamp, depth + 1, visited)
                                time.sleep(1)  # Rate limiting

            return filepath

        except Exception as e:
            self.logger.error(f"Error downloading page {url}: {e}")
            return None