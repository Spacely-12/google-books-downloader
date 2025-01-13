import os
import re
import traceback
import validators
from time import sleep
from tqdm import tqdm
import requests
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import requests
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# Setup logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)


def setup_driver(chromedriver_path):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    logging.info("Initializing WebDriver...")
    return webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)


def get_book_url():
    while True:
        url = input("\nStep 1: Paste the URL of the book preview to be downloaded:\nYour input: ").strip()
        if validators.url(url):
            match = re.search(r"id=[A-Za-z0-9]+", url)
            if match:
                id_part = match.group(0)
                return (
                    f"https://books.google.com/books?{id_part}&pg=1&hl=en#v=onepage&q&f=false",
                    f"https://books.google.com/books?{id_part}&pg=1&hl=en&f=false&output=embed&source=gbs_embed"
                )
        logging.warning("Invalid URL. Please try again.")


def get_book_data(driver, url):
    driver.get(url)
    sleep(2)
    try:
        title = driver.find_element(By.CLASS_NAME, "gb-volume-title").text
        author = driver.find_element(By.CLASS_NAME, "addmd").text
        return f"{title} by {author}"
    except Exception:
        logging.error("Failed to extract book data. Ensure the URL is valid.")
        return "Unknown Book"


def scroll_and_capture(driver):
    checkpoint = None
    attempts = 0
    while attempts < 5:
        try:
            page_display = driver.find_element(By.CLASS_NAME, "pageImageDisplay")
            if checkpoint == page_display:
                break
            checkpoint = page_display
            page_display.click()
            for _ in range(25):
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.SPACE)
            sleep(2)
        except Exception:
            attempts += 1
    return driver.page_source


def extract_urls(page_source):
    urls = re.findall(r"https:\/\/[^']+content[^']+pg=[A-Z\d]+[^']+", page_source)
    logging.info(f"Extracted {len(urls)} URLs from page source.")
    return {page: url for page, url in zip(range(1, len(urls) + 1), urls)}


def save_backup(urls):
    with open("backup.txt", "w") as f:
        f.write(str(urls))
    logging.info("Backup of URLs saved to backup.txt.")



def download_image(page, url, directory):
    filepath = os.path.join(directory, f"page{page}.jpg")  # Change file extension to .jpg
    if not validators.url(url):
        logging.warning(f"Invalid URL skipped: {url}")
        return False
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logging.warning(f"URL not accessible: {url}")
            return False
        
        # Open the image and convert it to RGB if necessary (for saving as JPEG)
        img = Image.open(BytesIO(response.content))
        img = img.convert("RGB")  # Convert to RGB mode if it's in another format (e.g., RGBA or PNG)
        
        # Save the image as JPEG
        img.save(filepath, "JPEG")
        return True
    except Exception as e:
        logging.error(f"Failed to download {url}: {e}")
        return False



def download_images_concurrently(pages, directory, max_threads=5):
    os.makedirs(directory, exist_ok=True)
    with ThreadPoolExecutor(max_threads) as executor:
        results = list(tqdm(
            executor.map(lambda item: download_image(item[0], item[1], directory), pages.items()),
            total=len(pages),
            desc="Downloading images"
        ))
    successful_downloads = sum(results)
    logging.info(f"Downloaded {successful_downloads}/{len(pages)} images.")
    return successful_downloads


def select_pages(selection, all_pages):
    try:
        if selection == 'all':
            return all_pages
        elif '-' in selection:
            start, end = map(int, selection.split('-'))
            return {page: url for page, url in all_pages.items() if start <= page <= end}
        elif selection == 'odd':
            return {page: url for page, url in all_pages.items() if page % 2 != 0}
        elif selection == 'even':
            return {page: url for page, url in all_pages.items() if page % 2 == 0}
        else:
            pages = map(int, selection.split(','))
            return {page: url for page, url in all_pages.items() if page in pages}
    except Exception:
        logging.warning("Invalid selection. Defaulting to all pages.")
        return all_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Books Downloader")
    parser.add_argument("--chromedriver", default="chromedriver.exe", help="Path to ChromeDriver")
    args = parser.parse_args()

    driver = setup_driver(args.chromedriver)

    try:
        data_url, pages_url = get_book_url()
        book_data = get_book_data(driver, data_url)
        logging.info(f"Processing book: {book_data}")

        page_source = scroll_and_capture(driver)
        all_pages = extract_urls(page_source)
        save_backup(all_pages)

        selection = input("Specify pages to download (e.g., 'all', '1-10', 'odd'): ")
        selected_pages = select_pages(selection, all_pages)

        download_dir = input("Enter the directory to save images (leave blank for current directory): ") or "."
        successful_downloads = download_images_concurrently(selected_pages, os.path.join(download_dir, book_data))

        logging.info(f"Successfully downloaded {successful_downloads} pages.")
    except Exception as e:
        logging.error("An error occurred.", exc_info=True)
    finally:
        driver.quit()
