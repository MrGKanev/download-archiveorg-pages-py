import requests
import json
from datetime import datetime
import os
import time
from urllib.parse import urlparse


class WaybackDownloader:
    def __init__(self, output_dir="downloaded_pages"):
        """Initialize the downloader with an output directory."""
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def get_snapshots(self, url, from_date=None, to_date=None):
        """Get list of available snapshots for a URL."""
        cdx_api_url = f"https://web.archive.org/cdx/search/cdx"

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

        response = requests.get(cdx_api_url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to get snapshots: {response.status_code}")

        results = response.json()
        if not results or len(results) < 2:  # No results or only header row
            return []

        # Skip the header row
        return results[1:]

    def download_snapshot(self, url, timestamp):
        """Download a specific snapshot of a URL."""
        wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"

        response = requests.get(wayback_url)
        if response.status_code != 200:
            raise Exception(f"Failed to download snapshot: {response.status_code}")

        # Create filename from URL and timestamp
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace(".", "_")
        filename = f"{domain}_{timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)

        # Save the content
        with open(filepath, 'wb') as f:
            f.write(response.content)

        return filepath


def main():
    # Example usage
    downloader = WaybackDownloader()

    # URL to download
    url = input("Enter the URL to download (e.g., example.com): ")
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    # Optional date range
    from_date = input("Enter start date (YYYYMMDD) or press Enter to skip: ")
    to_date = input("Enter end date (YYYYMMDD) or press Enter to skip: ")

    try:
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
                filepath = downloader.download_snapshot(url, timestamp)
                print(f"Saved to: {filepath}")
                time.sleep(1)  # Be nice to the Wayback Machine servers
            except Exception as e:
                print(f"Error downloading snapshot: {e}")
                continue

        print("\nDownload complete!")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()