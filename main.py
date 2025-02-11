from datetime import datetime
import time
from downloader import WaybackDownloader
import os


def main():
    try:
        # Get the current script's directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Create an absolute path for the downloads folder
        download_dir = os.path.join(current_dir, "downloaded_pages")

        print(f"Files will be saved to: {download_dir}")

        downloader = WaybackDownloader(
            output_dir=download_dir,
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
                    # Verify that the file exists
                    if os.path.exists(filepath):
                        print(f"Successfully verified file at: {filepath}")
                    else:
                        print(f"Warning: File was not found at: {filepath}")
                time.sleep(2)  # Rate limiting
            except Exception as e:
                print(f"Error downloading snapshot: {e}")
                continue

        print("\nDownload complete!")

        # List the contents of the download directory
        if os.path.exists(download_dir):
            print("\nContents of download directory:")
            for root, dirs, files in os.walk(download_dir):
                level = root.replace(download_dir, '').count(os.sep)
                indent = ' ' * 4 * level
                print(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    print(f"{subindent}{f}")
        else:
            print(f"\nWarning: Download directory not found at {download_dir}")

    except Exception as e:
        print(f"An error occurred in main: {e}")
        raise


if __name__ == "__main__":
    main()