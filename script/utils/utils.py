import os
import time
import logging
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, WebDriverException,
    NoSuchElementException
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def click_element(driver, by_locator):
    element = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(by_locator))
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'})", element)
    element.click()

def get_element_text(driver, by_locator, timeout=2, default: str = "") -> str:
    try:
        element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(by_locator))
        text = element.text.strip()
        return text if text else default
    except TimeoutException:
        logger.warning(f"Element not visible for text extraction within {timeout} seconds: {by_locator}")
        return default
    except (NoSuchElementException, WebDriverException) as e:
        logger.error(f"Error getting element text: {e}")
        return default
    except Exception as e:
        logger.error(f"Unexpected error in get_element_text: {e}")
        return default

def check_element_exists(driver, by_locator, timeout=2) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located(by_locator))
        return True
    except TimeoutException:
        return False
    except (NoSuchElementException, WebDriverException):
        return False
    except Exception as e:
        logger.error(f"Unexpected error in check_element_exists: {e}")
        return False

def wait_for_page_load(driver, timeout: int = 30) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)
        return True
    except TimeoutException:
        logger.warning(f"Page load timeout after {timeout} seconds")
        return False
    except WebDriverException as e:
        logger.error(f"Error waiting for page load: {e}")
        return False

def safe_navigate_to_url(driver, url: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            driver.get(url)
            if wait_for_page_load(driver):
                logger.info(f"Successfully navigated to: {url}")
                return True
            logger.warning(f"Page load incomplete for: {url}")
        except WebDriverException as e:
            logger.error(f"Navigation attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    logger.error(f"Failed to navigate to {url} after {max_retries} attempts")
    return False

def get_element_attribute(driver, by_locator, attribute: str, timeout: int = 10,
                          default: str = "") -> str:
    try:
        element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(by_locator))
        attr_value = element.get_attribute(attribute)
        return attr_value if attr_value is not None else default
    except TimeoutException:
        logger.warning(f"Element not found for attribute '{attribute}' within {timeout} seconds: {by_locator}")
        return default
    except Exception as e:
        logger.error(f"Error getting element attribute '{attribute}': {e}")
        return default

def input_element(driver, by_locator, text):
    element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(by_locator))
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'})", element)
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located(by_locator)).send_keys(Keys.CONTROL, '\A',
                                                                                                 '\b')
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located(by_locator)).send_keys(text)


def select_dropdown_by_text(driver, by_locator, text):
    element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(by_locator))
    select = Select(element)
    select.select_by_visible_text(text)


def get_normal_driver(headless: bool = False) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    path = rf'{BASE_DIR}\\chrome-dir'
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            logger.info(f"Created chrome directory: {path}")
        except OSError as e:
            logger.error(f"Failed to create chrome directory: {e}")
            path = None
    if path:
        options.add_argument(f'--user-data-dir={path}')
    options.add_argument("--log-level=3")
    if headless:
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
    else:
        options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("data:,")
    return driver

def wait_while_element_is_displaying(driver, by_locator, timeout=10):
    """Waits while the specified element is displayed."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            element = driver.find_element(by_locator)
            if not element.is_displayed():
                return
        except Exception:
            return
        time.sleep(0.5)
    logger.warning(f"Timeout waiting for element {by_locator} to stop displaying.")