# Wayback Machine Website Downloader

A Python tool to download and archive complete websites from the Internet Archive's Wayback Machine, including navigation menus, linked pages, and assets.

## Features

- Downloads complete websites from Wayback Machine snapshots
- Prioritizes navigation menu items and main site structure
- Downloads assets (images, scripts, stylesheets)
- Maintains original site structure
- Supports date range selection for snapshots
- Configurable crawl depth
- Concurrent downloads for better performance
- Retry mechanism for failed downloads

## Requirements

```
beautifulsoup4>=4.9.3
requests>=2.25.1
urllib3<2.0.0
cssutils>=2.7.1
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/mrgkanev/download-archiveorg-pages-py.git
cd download-archiveorg-pages-py
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the script using Python:

```bash
python main.py
```

You will be prompted to:
1. Enter the maximum crawl depth (0-5)
2. Enter the URL to download
3. Optionally specify a date range for snapshots

## Example

```bash
python main.py
Enter maximum crawl depth (0-5): 2
Enter the URL to download (e.g., example.com): example.com
Enter start date (YYYYMMDD) or press Enter to skip: 20200101
Enter end date (YYYYMMDD) or press Enter to skip: 20201231
```

## Configuration

Default settings can be modified in `config.py`:
- `output_dir`: Directory for downloaded files
- `max_depth`: Maximum crawl depth
- `max_retries`: Number of retry attempts
- `concurrent_downloads`: Number of concurrent downloads
- `timeout`: Connection and read timeouts

## Structure

- `main.py`: Entry point script
- `downloader.py`: Main downloader class
- `config.py`: Configuration settings
- `utils.py`: Utility functions
- `requirements.txt`: Required Python packages

## Output

Downloads are organized by domain and timestamp:
```
downloaded_pages/
    example_com_20200101123456/
        index.html
        about_us.html
        contact.html
        assets/
            images/
            css/
            js/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.