import os
import urllib.request
import traceback
import re
import validators
from time import sleep
from tqdm import tqdm
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def setup_driver(chromedriver_path):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless Chrome
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.binary_location = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"  # Replace with your actual Chrome path
    return webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)


def get_book_url():
    while True:
        url = input("\nStep 1: Paste the URL of the book preview to be downloaded:\nYour input: ")
        match = re.search(r"id=[A-Za-z0-9]+", url)
        if match:
            id_part = match.group(0)
            return (
                f"https://books.google.com/books?{id_part}&pg=1&hl=en#v=onepage&q&f=false",
                f"https://books.google.com/books?{id_part}&pg=1&hl=en&f=false&output=embed&source=gbs_embed"
            )
        print("Invalid input. Please try again.")


def get_book_data(driver, url):
    driver.get(url)
    sleep(2)
    try:
        title = driver.find_element(By.CLASS_NAME, "gb-volume-title").text
        author = driver.find_element(By.CLASS_NAME, "addmd").text
        return f"{title} by {author}"
    except Exception:
        print("Failed to extract book data. Ensure the URL is valid.")
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
            for _ in range(25):  # Scroll 25 pages
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.SPACE)
            sleep(2)
        except Exception:
            attempts += 1
    return driver.page_source


def extract_urls(page_source):
    """
    Takes driver's page source as an input,
    returns a `dict` of page image URLs.
    """
    urls = re.findall(r"https:\/\/[^']+content[^']+pg=[A-Z\d]+[^']+", page_source)
    print("Extracted URLs:", urls)
    return {page: url for page, url in zip(range(1, len(urls) + 1), urls)}


def save_backup(urls):
    save = input("Would you like to save a backup of the URLs? (yes/no): ").strip().lower()
    if save == "yes":
        with open("backup.txt", "w") as f:
            f.write(str(urls))
        print("Backup saved.")
    else:
        print("Backup not saved.")


def download_images(pages, directory):
    os.makedirs(directory, exist_ok=True)
    for page, url in tqdm(pages.items(), desc="Downloading images"):
        if not validators.url(url):
            print(f"Invalid URL skipped: {url}")
            continue
        try:
            response = requests.head(url)
            if response.status_code != 200:
                print(f"URL not accessible: {url}")
                continue
            filepath = os.path.join(directory, f"page{page}.png")
            urllib.request.urlretrieve(url, filepath)
        except Exception as e:
            print(f"Failed to download {url}: {e}")


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
        print("Invalid selection. Defaulting to all pages.")
        return all_pages


if __name__ == "__main__":
    chromedriver_path = os.getenv('CHROMEDRIVER_PATH', "C:/Users/Salawudeen/Desktop/bookdwonloadeer/google-books-downloader/chromedriver.exe")
    driver = setup_driver(chromedriver_path)

    try:
        data_url, pages_url = get_book_url()
        book_data = get_book_data(driver, data_url)
        print(f"Processing book: {book_data}")

        page_source = scroll_and_capture(driver)
        all_pages = extract_urls(page_source)
        save_backup(all_pages)

        selection = input("Specify pages to download (e.g., 'all', '1-10', 'odd'): ")
        selected_pages = select_pages(selection, all_pages)

        download_dir = input("Enter the directory to save images (leave blank for current directory): ") or "."
        download_images(selected_pages, os.path.join(download_dir, book_data))

        print(f"Successfully downloaded {len(selected_pages)} pages.")
    except Exception as e:
        with open("error.log", "w") as log:
            log.write(traceback.format_exc())
        print(f"An error occurred. Details logged in error.log: {e}")
    finally:
        driver.quit()
