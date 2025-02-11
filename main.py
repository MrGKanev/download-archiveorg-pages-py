from datetime import datetime
import time
from downloader import WaybackDownloader  # Changed import


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