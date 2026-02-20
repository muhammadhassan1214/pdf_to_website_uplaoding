"""
Common automation functions for PDF to Website Automation.

This module contains shared functions used by both main.py (CLI mode)
and main_processor.py (GUI mode) to avoid code duplication.
"""

import os
import time

from dotenv import load_dotenv
from selenium.webdriver.common.by import By

from script.utils.functions import (
    create_xpath, get_season, format_tire_size
)
from script.utils.utils import (
    safe_navigate_to_url, input_element, click_element, logger,
    get_element_text, wait_while_element_is_displaying,
    select_dropdown_by_text, check_element_exists
)

load_dotenv()

# Configuration constants
BASE_URL = 'http://82.165.174.94'
CHEAP_BRANDS = ['ARIVO', 'GOODRIDE', 'WESTLAKE']
PREMIUM_BRANDS = ['HANKOOK', 'GOODYEAR', 'CONTINENTAL']
SEASONS = ['Sommerreifen', 'Winterreifen', 'Ganzjahresreifen']


def log_message(message, gui_callback=None):
    """
    Log a message to both logger and GUI if available.

    Args:
        message: The message to log
        gui_callback: Optional callback function for logging to GUI
    """
    logger.info(message)
    if gui_callback:
        gui_callback(message)


def login(driver, gui_callback=None):
    """
    Login to the website.

    Args:
        driver: Selenium WebDriver instance
        gui_callback: Optional callback function for logging to GUI

    Raises:
        Exception: If login fails
    """
    try:
        safe_navigate_to_url(driver, f'{BASE_URL}/login')
        input_element(driver, (By.ID, 'email'), os.getenv('LOGIN_USERNAME'))
        input_element(driver, (By.ID, 'password'), os.getenv('LOGIN_PASSWORD'))
        click_element(driver, (By.XPATH, "//button[@type='submit']"))
        time.sleep(5)
        log_message("Login successful", gui_callback)
    except Exception as e:
        log_message(f"Fehler beim Login: {e}", gui_callback)
        raise


def search_product(driver, brand, season, tire_size, gui_callback=None):
    """
    Search for a product with specified parameters.

    Args:
        driver: Selenium WebDriver instance
        brand: Brand name to search
        season: Season type (Sommerreifen, Winterreifen, Ganzjahresreifen)
        tire_size: Tire size string
        gui_callback: Optional callback function for logging to GUI

    Raises:
        Exception: If search fails
    """
    try:
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Brands')), brand)
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Usages')), season)
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Enter tyre size (e.g. 205/55 R16 91 H)']"),
                      format_tire_size(tire_size))
        input_element(driver, (By.XPATH, "(//input[@placeholder= 'Min Availability'])[2]"), '75')
        click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[2]"))
        wait_while_element_is_displaying(driver, (By.XPATH, "//div[contains(@class, 'animate-spin')]"))
    except Exception as e:
        log_message(f"Fehler bei der Produktsuche: {e}", gui_callback)
        raise


def create_product(driver, title, season, gui_callback=None, reference_text=None):
    """
    Create a product on the website.

    Args:
        driver: Selenium WebDriver instance
        title: Product title
        season: Season type for title replacement
        gui_callback: Optional callback function for logging to GUI
        reference_text: Optional text from PDF reference to append to product description

    Raises:
        Exception: If product creation fails
    """
    try:
        click_element(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"))
        click_element(driver, (By.XPATH, "//button[text()= 'Generate by AI']"))
        input_field_element = (By.CSS_SELECTOR, "input[placeholder= 'Enter or edit title...']")
        input_field = check_element_exists(driver, input_field_element, timeout=30)
        if not input_field:
            log_message("Eingabefeld für den Titel nicht gefunden.", gui_callback)
            return
        season_title = title.replace('All-season', get_season(season))
        input_element(driver, input_field_element, season_title)

        # If reference text is provided, append it to the product description
        if not reference_text:
            try:
                # Wait for the description field to be available
                description_locator = (By.XPATH, "//label[text()= 'Description']/following-sibling::textarea")
                description_field = check_element_exists(driver, description_locator, timeout=30)
                if description_field:
                    description_field_element = driver.find_element(*description_locator)
                    # Get current description and append reference text
                    current_description = get_element_text(driver, description_locator)
                    new_description = current_description.strip()
                    if new_description:
                        new_description += "\n\n"
                    new_description += reference_text
                    # execute javascript to replace the value directly
                    driver.execute_script("arguments[0].value = arguments[1];", description_field_element, new_description)
                    log_message(f"Reference text appended to description", gui_callback)
            except Exception as desc_error:
                log_message(f"Could not append reference text: {desc_error}", gui_callback)

        click_element(driver, (By.XPATH, "//button[text()= 'Submit']"))
        navigate_to_rims_page(driver)
        log_message(f"Product created: {season_title[:50]}...", gui_callback)
    except Exception as e:
        log_message(f"Fehler bei der Produkterstellung: {e}", gui_callback)
        raise


def no_result_found(driver):
    """
    Check if no results were found.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if "No tyres found" message is displayed
    """
    return check_element_exists(driver, (By.XPATH, "//div[text()= 'No tyres found']"))


def navigate_to_rims_page(driver, gui_callback=None):
    """
    Navigate to the rims and tyres page.

    Args:
        driver: Selenium WebDriver instance
        gui_callback: Optional callback function for logging to GUI
    """
    safe_navigate_to_url(driver, f'{BASE_URL}/rims_tyers')
    time.sleep(2)


import time
from selenium.webdriver.common.by import By


def search_rim(driver, model, tyre_dia, rim_manufacturer=None, gui_callback=None):
    """
    Search for a rim with specified parameters.
    Includes a fallback retry for 'WHEELWORLD' to '2DRV by WHEELWORLD'.

    Args:
        driver: Selenium WebDriver instance
        model: Rim model to search
        tyre_dia: Tyre diameter/size
        rim_manufacturer: Rim manufacturer name (e.g., 'BROCK / RC', 'BBS', etc.)
                         If None, defaults to 'BROCK / RC'
        gui_callback: Optional callback function for logging to GUI

    Returns:
        bool: True if rims were found, False otherwise
    """
    # Use provided manufacturer or default to 'BROCK / RC'
    initial_manufacturer = rim_manufacturer if rim_manufacturer else 'BROCK / RC'

    # Set up our retry queue
    manufacturers_to_try = [initial_manufacturer]
    if initial_manufacturer == "WHEELWORLD":
        manufacturers_to_try.append("2DRV by WHEELWORLD")

    for current_manufacturer in manufacturers_to_try:
        if gui_callback:
            gui_callback(f"Searching with manufacturer: {current_manufacturer}")

        # Execute the search actions
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Manufacturer')), current_manufacturer)
        time.sleep(2)

        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Size')),
                                str(tyre_dia) if tyre_dia else '')

        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Min Availability']"), '75')
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Rim type']"), model if model else '')

        click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[1]"))

        # Check if the "No rims found" element appears
        no_rims_found = check_element_exists(driver, (By.XPATH, "//div[text()= 'No rims found']"))

        # If rims WERE found, return True immediately and break the loop
        if not no_rims_found:
            return True

        # If we reach here, no rims were found.
        # The loop will naturally continue to '2DRV by WHEELWORLD' if it's in the list.
        if gui_callback and current_manufacturer == "WHEELWORLD":
            gui_callback("No rims found for 'WHEELWORLD'. Retrying with fallback...")

    # If the loop exhausts the list without returning True, then no rims were found at all
    return False


def find_rim_element(driver, tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore):
    """
    Find and click on a specific rim element in the search results.

    Args:
        driver: Selenium WebDriver instance
        tyre_width: Tyre width value
        tyre_dia: Tyre diameter
        holes: Number of holes
        pcd: Pitch circle diameter
        t_offset: Offset value
        centre_bore: Centre bore value

    Returns:
        tuple: (element_exists: bool, locator: str)
    """
    locator = f"(//tr/td[text()= '{tyre_width}']/following-sibling::td[text()= '{tyre_dia}']/following-sibling::td[text()= '{holes}']/following-sibling::td[text()= '{pcd}']/following-sibling::td[text()= '{t_offset} - {t_offset}']/following-sibling::td[text()= '{centre_bore}'])[1]"
    element_exists = check_element_exists(driver, (By.XPATH, locator), timeout=2)
    return element_exists, locator


def process_brands(driver, title, tire_size, brands, brand_type, gui_callback=None, stop_checker=None):
    """
    Process a list of brands and try to create a product.

    Args:
        driver: Selenium WebDriver instance
        title: Product title
        tire_size: Tire size string
        brands: List of brand names to try
        brand_type: Type of brand (e.g., 'premium', 'cheap') for logging
        gui_callback: Optional callback function for logging to GUI
        stop_checker: Optional function that returns True if stop was requested

    Returns:
        bool: True if a product was created, False otherwise
    """
    def should_stop():
        return stop_checker() if stop_checker else False

    product_created = False

    for brand in brands:
        if product_created or should_stop():
            break

        # Verify browser is still active
        try:
            _ = driver.current_url
        except Exception:
            log_message("Browser closed. Stopping.", gui_callback)
            return product_created

        for season in SEASONS:
            if should_stop():
                break

            log_message(f"Trying {brand_type} brand: {brand} with season: {season}", gui_callback)
            try:
                search_product(driver, brand, season, tire_size, gui_callback)
                if no_result_found(driver):
                    continue

                result_element = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                if result_element:
                    create_product(driver, title, season, gui_callback)
                    log_message(f"{brand_type.capitalize()} product created: {brand} - {season} for task: {title[:50]}...", gui_callback)
                    product_created = True
                    break
                else:
                    log_message(f"No match found for {brand} - {season}", gui_callback)
            except Exception as e:
                log_message(f"Error trying {brand} - {season}: {e}", gui_callback)
                continue

    return product_created


def is_driver_valid(driver):
    """
    Check if the WebDriver instance is still valid and responsive.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if driver is valid, False otherwise
    """
    try:
        if driver is None or not hasattr(driver, 'session_id') or driver.session_id is None:
            return False
        # Quick check to see if browser is responsive
        _ = driver.current_url
        return True
    except Exception:
        return False


def navigate_and_select_rim(driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, rim_manufacturer=None, gui_callback=None):
    """
    Navigate to rims page, search for rim and select it.

    Args:
        driver: Selenium WebDriver instance
        model: Rim model to search
        tyre_dia: Tyre diameter/size
        tyre_width: Tyre width value
        holes: Number of holes
        pcd: Pitch circle diameter
        t_offset: Offset value
        centre_bore: Centre bore value
        rim_manufacturer: Rim manufacturer name (e.g., 'BROCK / RC', 'BBS', etc.)
        gui_callback: Optional callback function for logging to GUI

    Returns:
        tuple: (success: bool, locator: str or None)
    """
    navigate_to_rims_page(driver, gui_callback)

    # Search for rim
    rims_found = search_rim(driver, model, tyre_dia, rim_manufacturer, gui_callback)

    if not rims_found:
        return False, None

    # Find specific rim element
    element_exists, locator = find_rim_element(
        driver, tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore
    )

    if not element_exists:
        return False, None

    click_element(driver, (By.XPATH, locator))
    click_element(driver, (By.XPATH, locator))
    return True, locator


def process_single_task(driver, task, gui_callback=None, stop_checker=None, reference_text=None):
    """
    Process a single task/product.

    Args:
        driver: Selenium WebDriver instance
        task: Task dictionary containing all task data
        gui_callback: Optional callback function for logging to GUI
        stop_checker: Optional function that returns True if stop was requested
        reference_text: Optional text from PDF reference to append to product description

    Returns:
        dict: Processing result with keys: element_found, premium_created, cheap_created, error
    """
    def should_stop():
        return stop_checker() if stop_checker else False

    # Extract fields from task
    title = task.get('Title')
    model = task.get('Model')
    tyre_width = task.get('Tyre_Width')
    tyre_dia = task.get('Tyre_dia')
    holes = task.get('holes')
    pcd = task.get('pcd')
    centre_bore = task.get('centre_bore')
    t_offset = task.get('offset')
    tire_size = task.get('tire_size')
    rim_manufacturer = task.get('Rim_Manufacturer')

    processing_result = {
        'element_found': False,
        'premium_created': False,
        'cheap_created': False,
        'error': None
    }

    try:
        if should_stop():
            return processing_result

        # First navigation and rim selection to verify the element exists
        success, locator = navigate_and_select_rim(
            driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, rim_manufacturer, gui_callback
        )

        if not success:
            log_message(f"Element with specified attributes not found for task: {task}", gui_callback)
            return processing_result

        processing_result['element_found'] = True

        if should_stop():
            return processing_result

        # Try cheap brands - navigate fresh for each brand type
        log_message("Starting cheap brand search...", gui_callback)
        cheap_product_created = process_brands_with_navigation(
            driver, title, tire_size, CHEAP_BRANDS, 'cheap',
            model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore,
            rim_manufacturer, gui_callback, stop_checker, reference_text
        )
        processing_result['cheap_created'] = cheap_product_created

        if should_stop():
            return processing_result

        # Try premium brands - navigate fresh for each brand type
        log_message("Starting premium brand search...", gui_callback)
        premium_product_created = process_brands_with_navigation(
            driver, title, tire_size, PREMIUM_BRANDS, 'premium',
            model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore,
            rim_manufacturer, gui_callback, stop_checker, reference_text
        )
        processing_result['premium_created'] = premium_product_created

        return processing_result

    except Exception as e:
        error_str = str(e)
        # Check if this is due to stop request / browser closure
        if should_stop() or 'NewConnectionError' in error_str or 'MaxRetry' in error_str or 'session' in error_str.lower():
            processing_result['error'] = "Browser closed or stop requested"
        else:
            processing_result['error'] = str(e)
            log_message(f"In der Automatisierung ist ein Fehler aufgetreten: {e}", gui_callback)
        return processing_result


def process_brands_with_navigation(driver, title, tire_size, brands, brand_type,
                                    model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore,
                                    rim_manufacturer=None, gui_callback=None, stop_checker=None, reference_text=None):
    """
    Process a list of brands with fresh navigation for each attempt.
    Navigates to rims page and selects the rim before each brand/season search.

    Args:
        driver: Selenium WebDriver instance
        title: Product title
        tire_size: Tire size string
        brands: List of brand names to try
        brand_type: Type of brand (e.g., 'premium', 'cheap') for logging
        model: Rim model
        tyre_dia: Tyre diameter
        tyre_width: Tyre width
        holes: Number of holes
        pcd: Pitch circle diameter
        t_offset: Offset value
        centre_bore: Centre bore value
        rim_manufacturer: Rim manufacturer name (e.g., 'BROCK / RC', 'BBS', etc.)
        gui_callback: Optional callback function for logging to GUI
        stop_checker: Optional function that returns True if stop was requested
        reference_text: Optional text from PDF reference to append to product description

    Returns:
        bool: True if a product was created, False otherwise
    """
    def should_stop():
        return stop_checker() if stop_checker else False

    product_created = False

    for brand in brands:
        if product_created or should_stop():
            break

        # Verify browser is still active
        try:
            _ = driver.current_url
        except Exception:
            log_message("Browser closed. Stopping.", gui_callback)
            return product_created

        for season in SEASONS:
            if should_stop():
                break

            log_message(f"Trying {brand_type} brand: {brand} with season: {season}", gui_callback)

            try:
                # Navigate to rims page and select rim fresh for each search
                success, locator = navigate_and_select_rim(
                    driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, rim_manufacturer, gui_callback
                )

                if not success:
                    log_message(f"Could not find rim element, skipping {brand} - {season}", gui_callback)
                    continue

                # Now search for the product
                search_product(driver, brand, season, tire_size, gui_callback)

                if no_result_found(driver):
                    continue

                result_element = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                if result_element:
                    create_product(driver, title, season, gui_callback, reference_text)
                    log_message(f"{brand_type.capitalize()} product created: {brand} - {season} for task: {title[:50]}...", gui_callback)
                    product_created = True
                    break
                else:
                    log_message(f"No match found for {brand} - {season}", gui_callback)
            except Exception as e:
                log_message(f"Error trying {brand} - {season}: {e}", gui_callback)
                continue

    return product_created
