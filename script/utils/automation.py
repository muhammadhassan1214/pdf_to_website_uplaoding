"""
Common automation functions for PDF to Website Automation.

This module contains shared functions used by both main.py (CLI mode)
and main_processor.py (GUI mode) to avoid code duplication.
"""

import os
import csv
import time

from dotenv import load_dotenv
from script.utils.site_locators import SiteLocators as Sl
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
QUALITY_BRANDS = ['NEXEN', 'KUMHO', 'KLEBER']
PREMIUM_BRANDS = ['HANKOOK', 'GOODYEAR', 'CONTINENTAL']

SEASONS = ['Sommerreifen', 'Winterreifen', 'Ganzjahresreifen']
UNMATCHED_RIMS_CSV = 'unmatched_rims.csv'


def log_unmatched_rim(manufacturer, model, tyre_dia):
    """
    Log an unmatched rim search to CSV file with duplicate prevention.

    Args:
        manufacturer: Rim manufacturer name
        model: Rim model
        tyre_dia: Tyre diameter/size
    """
    csv_path = UNMATCHED_RIMS_CSV
    headers = ['Manufacturer', 'Model', 'Tyre_Diameter']

    # Check if file exists and read existing entries to prevent duplicates
    existing_entries = set()
    file_exists = os.path.exists(csv_path)

    if file_exists:
        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entry_key = (row.get('Manufacturer', ''), row.get('Model', ''), row.get('Tyre_Diameter', ''))
                    existing_entries.add(entry_key)
        except Exception as e:
            logger.warning(f"Could not read existing unmatched_rims.csv: {e}")

    # Create the new entry key
    new_entry = (str(manufacturer), str(model), str(tyre_dia))

    # Check if entry already exists
    if new_entry in existing_entries:
        logger.debug(f"Duplicate unmatched rim entry skipped: {new_entry}")
        return

    # Append the new entry
    try:
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header if file is new
            if not file_exists or os.path.getsize(csv_path) == 0:
                writer.writerow(headers)
            writer.writerow([manufacturer, model, tyre_dia])
        logger.info(f"Logged unmatched rim: {manufacturer}, {model}, {tyre_dia}")
    except Exception as e:
        logger.warning(f"Could not log unmatched rim to CSV: {e}")


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
        input_element(driver, Sl.USERNAME_INPUT, os.getenv('LOGIN_USERNAME'))
        input_element(driver, Sl.PASSWORD_INPUT, os.getenv('LOGIN_PASSWORD'))
        click_element(driver, Sl.SUBMIT_BUTTON)
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
        select_dropdown_by_text(driver, (By.XPATH, Sl.COMMON_ELEMENT('Select Brands')), brand)
        select_dropdown_by_text(driver, (By.XPATH, Sl.COMMON_ELEMENT('Select Usages')), season)
        input_element(driver, Sl.TYRE_SIZE_INPUT, format_tire_size(tire_size))
        input_element(driver, Sl.MIN_AVAILABLE_QUANTITY_INPUT, '75')
        click_element(driver, Sl.SEARCH_BUTTON)
        wait_while_element_is_displaying(driver, Sl.SPINNER)
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
        click_element(driver, Sl.FIRST_RESULT)
        click_element(driver, Sl.GENERATE_BY_AI_BUTTON)
        input_field = check_element_exists(driver, Sl.TITLE_INPUT, timeout=30)
        if not input_field:
            log_message("Eingabefeld für den Titel nicht gefunden.", gui_callback)
            return
        season_title = title.replace('All-season', get_season(season))
        input_element(driver, Sl.TITLE_INPUT, season_title)

        # If reference text is provided, append it to the product description
        if reference_text:
            try:
                # Wait for the description field to be available
                description_field = check_element_exists(driver, Sl.DESCRIPTION_INPUT, timeout=30)
                if description_field:
                    description_field_element = driver.find_element(*Sl.DESCRIPTION_INPUT)
                    # Get current description and append reference text
                    current_description = get_element_text(driver, Sl.DESCRIPTION_INPUT)
                    new_description = current_description.strip()
                    if new_description:
                        new_description += "\n\n"
                    new_description += reference_text
                    # execute javascript to replace the value directly
                    driver.execute_script("arguments[0].value = arguments[1];", description_field_element, new_description)
                    log_message("Reference text appended to description", gui_callback)
            except Exception as desc_error:
                log_message(f"Could not append reference text: {desc_error}", gui_callback)

        click_element(driver, Sl.SAVE_BUTTON)
        navigate_to_rims_page(driver)
        log_message(f"Product created: {season_title[:50]}...", gui_callback)
    except Exception as e:
        log_message(f"Fehler bei der Produkterstellung: {e}", gui_callback)
        raise


def no_result_found(driver):
    return check_element_exists(driver, Sl.NO_TYRE_FOUND_MESSAGE, timeout=2)


def navigate_to_rims_page(driver, gui_callback=None):
    safe_navigate_to_url(driver, f'{BASE_URL}/rims_tyers')
    time.sleep(2)


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
        select_dropdown_by_text(driver, (By.XPATH, Sl.COMMON_ELEMENT('Select Manufacturer')), current_manufacturer)
        time.sleep(2)

        if not select_dropdown_by_text(driver, (By.XPATH, Sl.COMMON_ELEMENT('Select Size')),
                                str(tyre_dia) if tyre_dia else ''):
            log_message(f"Size dropdown option not found for tyre diameter: {tyre_dia}", gui_callback)
            return False

        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Min Availability']"), '50')
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Rim type']"), model if model else '')

        click_element(driver, Sl.SEARCH_BUTTON_2)
        wait_while_element_is_displaying(driver, Sl.SPINNER)

        # Check if the "No rims found" element appears
        no_rims_found = check_element_exists(driver, Sl.NO_RIM_FOUND_MESSAGE, timeout=2)

        # If rims WERE found, return True immediately and break the loop
        if not no_rims_found:
            return True

        # If we reach here, no rims were found.
        # The loop will naturally continue to '2DRV by WHEELWORLD' if it's in the list.
        if gui_callback and current_manufacturer == "WHEELWORLD":
            gui_callback("No rims found for 'WHEELWORLD'. Retrying with fallback...")

    # If the loop exhausts the list without returning True, then no rims were found at all
    # Log the unmatched rim search to CSV
    log_unmatched_rim(initial_manufacturer, model, tyre_dia)
    return False


def find_rim_element(driver, tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore, centre_bore_secondary=None):
    """
    Find and click on a specific rim element in the search results.

    If primary centre_bore doesn't match, retry with secondary centre_bore if available.

    Args:
        driver: Selenium WebDriver instance
        tyre_width: Tyre width value
        tyre_dia: Tyre diameter
        holes: Number of holes
        pcd: Pitch circle diameter
        t_offset: Offset value
        centre_bore: Centre bore value (primary)
        centre_bore_secondary: Secondary centre bore value (optional, for retry)

    Returns:
        tuple: (element_exists: bool, locator: str)
    """
    # Try with primary centre bore first
    locator = Sl.RIM_LOCATOR(tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore)
    element_exists = check_element_exists(driver, locator, timeout=2)

    # If primary match fails and secondary centre bore is available, retry with secondary
    if not element_exists and centre_bore_secondary:
        locator = Sl.RIM_LOCATOR(tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore_secondary)
        element_exists = check_element_exists(driver, locator, timeout=2)

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

                result_element = check_element_exists(driver, Sl.FIRST_RESULT, timeout=2)
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


def navigate_and_select_rim(driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary=None, rim_manufacturer=None, gui_callback=None):
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
        centre_bore: Centre bore value (primary)
        centre_bore_secondary: Secondary centre bore value (optional, for retry)
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
        driver, tyre_width, tyre_dia, holes, pcd, t_offset, centre_bore, centre_bore_secondary
    )

    if not element_exists:
        return False, None

    click_element(driver, locator)
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
        dict: Processing result with keys: element_found, premium_created, quality_created, cheap_created, error
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
    centre_bore_secondary = task.get('centre_bore_secondary')
    t_offset = task.get('offset')
    tire_size = task.get('tire_size')
    rim_manufacturer = task.get('Rim_Manufacturer')

    processing_result = {
        'element_found': False,
        'premium_created': False,
        'quality_created': False,
        'cheap_created': False,
        'premium_seasons': {},
        'quality_seasons': {},
        'cheap_seasons': {},
        'error': None
    }

    try:
        if should_stop():
            return processing_result

        # First navigation and rim selection to verify the element exists
        success, locator = navigate_and_select_rim(
            driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary, rim_manufacturer, gui_callback
        )

        if not success:
            log_message(f"Element with specified attributes not found for task: {task}", gui_callback)
            return processing_result

        processing_result['element_found'] = True

        if should_stop():
            return processing_result

        # Try cheap brands - navigate fresh for each brand type
        log_message("Starting cheap brand search...", gui_callback)
        cheap_seasons_created = process_brands_with_navigation(
            driver, title, tire_size, CHEAP_BRANDS, 'cheap',
            model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary,
            rim_manufacturer, gui_callback, stop_checker, reference_text
        )
        processing_result['cheap_seasons'] = cheap_seasons_created
        processing_result['cheap_created'] = any(cheap_seasons_created.values())

        if should_stop():
            return processing_result

        # Try quality brands - navigate fresh for each brand type
        log_message("Starting quality brand search...", gui_callback)
        quality_seasons_created = process_brands_with_navigation(
            driver, title, tire_size, QUALITY_BRANDS, 'quality',
            model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary,
            rim_manufacturer, gui_callback, stop_checker, reference_text
        )
        processing_result['quality_seasons'] = quality_seasons_created
        processing_result['quality_created'] = any(quality_seasons_created.values())

        if should_stop():
            return processing_result

        # Try premium brands - navigate fresh for each brand type
        log_message("Starting premium brand search...", gui_callback)
        premium_seasons_created = process_brands_with_navigation(
            driver, title, tire_size, PREMIUM_BRANDS, 'premium',
            model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary,
            rim_manufacturer, gui_callback, stop_checker, reference_text
        )
        processing_result['premium_seasons'] = premium_seasons_created
        processing_result['premium_created'] = any(premium_seasons_created.values())

        # Log detailed summary
        cheap_count = sum(1 for v in cheap_seasons_created.values() if v)
        quality_count = sum(1 for v in quality_seasons_created.values() if v)
        premium_count = sum(1 for v in premium_seasons_created.values() if v)
        total_products = cheap_count + quality_count + premium_count
        log_message(f"Task summary: {total_products} products created (Cheap: {cheap_count}, Quality: {quality_count}, Premium: {premium_count})", gui_callback)

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
                                    model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary=None,
                                    rim_manufacturer=None, gui_callback=None, stop_checker=None, reference_text=None):
    """
    Process a list of brands with fresh navigation for each attempt.
    Navigates to rims page and selects the rim before each brand/season search.

    Creates separate products for each season (Summer, Winter, All-Season) within each brand tier.

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
        centre_bore: Centre bore value (primary)
        centre_bore_secondary: Secondary centre bore value (optional, for retry)
        rim_manufacturer: Rim manufacturer name (e.g., 'BROCK / RC', 'BBS', etc.)
        gui_callback: Optional callback function for logging to GUI
        stop_checker: Optional function that returns True if stop was requested
        reference_text: Optional text from PDF reference to append to product description

    Returns:
        dict: Dictionary with season keys and boolean values indicating if product was created for each season
              e.g., {'Sommerreifen': True, 'Winterreifen': False, 'Ganzjahresreifen': True}
    """
    def should_stop():
        return stop_checker() if stop_checker else False

    # Track products created per season
    products_created = {season: False for season in SEASONS}

    for brand in brands:
        if should_stop():
            break

        # Check if all seasons have products created - if so, we're done with this brand tier
        if all(products_created.values()):
            break

        # Verify browser is still active
        try:
            _ = driver.current_url
        except Exception:
            log_message("Browser closed. Stopping.", gui_callback)
            return products_created

        for season in SEASONS:
            if should_stop():
                break

            # Skip this season if we already created a product for it
            if products_created[season]:
                continue

            log_message(f"Trying {brand_type} brand: {brand} with season: {season}", gui_callback)

            try:
                # Navigate to rims page and select rim fresh for each search
                success, locator = navigate_and_select_rim(
                    driver, model, tyre_dia, tyre_width, holes, pcd, t_offset, centre_bore, centre_bore_secondary, rim_manufacturer, gui_callback
                )

                if not success:
                    log_message(f"Could not find rim element, skipping {brand} - {season}", gui_callback)
                    continue

                # Now search for the product
                search_product(driver, brand, season, tire_size, gui_callback)

                if no_result_found(driver):
                    continue

                result_element = check_element_exists(driver, Sl.FIRST_RESULT, timeout=2)
                if result_element:
                    create_product(driver, title, season, gui_callback, reference_text)
                    log_message(f"{brand_type.capitalize()} product created: {brand} - {season} for task: {title[:50]}...", gui_callback)
                    products_created[season] = True
                    # Don't break - continue to try other seasons with other brands if needed
                else:
                    log_message(f"No match found for {brand} - {season}", gui_callback)
            except Exception as e:
                log_message(f"Error trying {brand} - {season}: {e}", gui_callback)
                continue

    # Return True if at least one product was created for any season
    return products_created
