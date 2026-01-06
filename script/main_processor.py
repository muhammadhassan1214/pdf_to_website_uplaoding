"""
Main processor module for PDF to Website Automation.
This module contains the core processing logic that can be called from the GUI.
"""

import os
import time

from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from script.utils.functions import (
    create_xpath, get_pdf_paths, get_season,
    parse_data_from_pdf, validate_task, format_tire_size,
    load_cache, move_task_to_processed, process_tasks_with_title_splitting,
    delete_cache_file
)
from script.utils.utils import (
    get_normal_driver, safe_navigate_to_url,
    input_element, click_element, logger,
    select_dropdown_by_text, check_element_exists,
    wait_while_element_is_displaying
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()
base_url = 'http://82.165.174.94'

cheap_brands = ['ARIVO', 'GOODRIDE', 'WESTLAKE']
premium_brands = ['CONTINENTAL', 'GOODYEAR', 'HANKOOK']
seasons = ['Sommerreifen', 'Winterreifen', 'Ganzjahresreifen']


def log_message(message, gui_callback=None):
    """Log a message to both logger and GUI if available"""
    logger.info(message)
    if gui_callback:
        gui_callback(message)


def login(driver, gui_callback=None):
    """Login to the website"""
    try:
        safe_navigate_to_url(driver, f'{base_url}/login')
        input_element(driver, (By.ID, 'email'), os.getenv('LOGIN_USERNAME'))
        input_element(driver, (By.ID, 'password'), os.getenv('LOGIN_PASSWORD'))
        click_element(driver, (By.XPATH, "//button[@type='submit']"))
        time.sleep(5)
        log_message("Login successful", gui_callback)
    except Exception as e:
        log_message(f"Fehler beim Login: {e}", gui_callback)
        raise


def search_product(driver, brand, season, tire_size, gui_callback=None):
    """Search for a product with specified parameters"""
    try:
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Brands')), brand)
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Usages')), season)
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Enter tyre size (e.g. 205/55 R16 91 H)']"),
                      format_tire_size(tire_size))
        input_element(driver, (By.XPATH, "(//input[@placeholder= 'Min Availability'])[2]"), '1')
        click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[2]"))
        wait_while_element_is_displaying(driver, (By.XPATH, "//div[contains(@class, 'animate-spin')]"))
    except Exception as e:
        log_message(f"Fehler bei der Produktsuche: {e}", gui_callback)
        raise


def create_product(driver, title, season, gui_callback=None):
    """Create a product on the website"""
    try:
        click_element(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"))
        click_element(driver, (By.XPATH, "//button[text()= 'Generate by AI']"))
        # Update title with season info
        season_title = title.replace('All-season', get_season(season))
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Enter or edit title...']"), season_title)
        click_element(driver, (By.XPATH, "//button[text()= 'Submit']"))
        log_message(f"Product created: {season_title[:50]}...", gui_callback)
    except Exception as e:
        log_message(f"Fehler bei der Produkterstellung: {e}", gui_callback)
        raise


def no_result_found(driver):
    """Check if no results were found"""
    return check_element_exists(driver, (By.XPATH, "//div[text()= 'No tyres found']"))


def run_automation(pdf_path=None, gui_callback=None, stop_checker=None, driver_setter=None):
    """
    Main automation function that processes PDFs and automates website interactions.

    Args:
        pdf_path: Optional path to a specific PDF file. If None, processes all PDFs from documents folder.
        gui_callback: Optional callback function for logging to GUI.
        stop_checker: Optional function that returns True if stop was requested.
        driver_setter: Optional callback to set driver reference in GUI for cleanup.

    Returns:
        bool: True if processing completed successfully, False otherwise.
    """
    task_list = []
    driver = None

    def should_stop():
        return stop_checker() if stop_checker else False

    try:
        # Delete cache file for fresh run
        delete_cache_file()

        # Determine which PDFs to process
        if pdf_path:
            # Process specific PDF file
            if os.path.exists(pdf_path):
                all_files = [pdf_path]
                log_message(f"Processing: {os.path.basename(pdf_path)}", gui_callback)
            else:
                log_message(f"PDF not found: {pdf_path}", gui_callback)
                return False
        else:
            # Process all PDFs from documents folder
            pdf_dir = os.path.join(BASE_DIR, '..', 'documents')
            if not os.path.exists(pdf_dir):
                log_message(f"PDF directory not found: {pdf_dir}", gui_callback)
                return False
            all_files = get_pdf_paths(pdf_dir)

        log_message(f"Found {len(all_files)} PDF file(s)", gui_callback)

        # Parse data from PDF files
        for file in all_files:
            if should_stop():
                log_message("Processing stopped by user", gui_callback)
                return False

            pdf_filename = os.path.basename(file)
            log_message(f"Processing: {pdf_filename}", gui_callback)
            file_data_list = parse_data_from_pdf(file)

            if not file_data_list:
                log_message(f"No valid data found in: {pdf_filename}", gui_callback)
                continue

            # Validate and filter tasks
            valid_tasks = []
            for task in file_data_list:
                is_valid, missing = validate_task(task)
                if is_valid:
                    task['_source_pdf'] = pdf_filename
                    valid_tasks.append(task)

            if valid_tasks:
                task_list.extend(valid_tasks)
                log_message(f"  → {len(valid_tasks)} valid task(s) extracted", gui_callback)
            else:
                log_message(f"  → No valid matches found in: {pdf_filename}", gui_callback)

        # If no new PDFs found, load from cache
        if not all_files:
            log_message("No PDFs in documents folder. Checking cache...", gui_callback)
            cache = load_cache()
            if cache:
                for pdf_filename, cache_entry in cache.items():
                    if should_stop():
                        log_message("Processing stopped by user", gui_callback)
                        return False

                    log_message(f"Loading from cache: {pdf_filename}", gui_callback)
                    cached_data = cache_entry.get('data', [])

                    cached_data = process_tasks_with_title_splitting(cached_data, max_title_length=80)

                    valid_tasks = []
                    for task in cached_data:
                        is_valid, missing = validate_task(task)
                        if is_valid:
                            task['_source_pdf'] = pdf_filename
                            valid_tasks.append(task)

                    if valid_tasks:
                        task_list.extend(valid_tasks)
                        log_message(f"  → {len(valid_tasks)} valid task(s) from cache", gui_callback)
                    else:
                        log_message(f"  → No valid matches in cached: {pdf_filename}", gui_callback)
            else:
                log_message("No cached data available.", gui_callback)

        log_message(f"Total tasks: {len(task_list)}", gui_callback)

        if not task_list:
            log_message("No valid tasks found. Exiting.", gui_callback)
            return False

        # Log brief task summary
        log_message("-" * 40, gui_callback)
        for i, task in enumerate(task_list, 1):
            log_message(f"Task {i}: {task.get('Title', 'No Title')[:50]}...", gui_callback)
        log_message("-" * 40, gui_callback)

        # Start browser automation
        driver = get_normal_driver()
        if driver_setter:
            driver_setter(driver)

        login(driver, gui_callback)

        for task_index, task in enumerate(task_list, 1):
            if should_stop():
                log_message("Processing stopped by user", gui_callback)
                return False

            # Check if driver is still valid
            try:
                if driver is None or not hasattr(driver, 'session_id') or driver.session_id is None:
                    log_message("Browser session closed. Stopping.", gui_callback)
                    return False
                # Quick check to see if browser is responsive
                _ = driver.current_url
            except Exception:
                log_message("Browser no longer available. Stopping.", gui_callback)
                return False

            log_message(f"Processing task {task_index}/{len(task_list)}: {task.get('Title', 'No Title')[:50]}...", gui_callback)

            source_pdf = task.get('_source_pdf', 'unknown.pdf')
            task_data = {k: v for k, v in task.items() if not k.startswith('_')}

            # Extract fields
            title = task.get('Title')
            model = task.get('Model')
            tyre_width = task.get('Tyre_Width')
            tyre_dia = task.get('Tyre_dia')
            holes = task.get('holes')
            pcd = task.get('pcd')
            centre_bore = task.get('centre_bore')
            t_offset = task.get('offset')
            tire_size = task.get('tire_size')

            processing_result = {
                'element_found': False,
                'premium_created': False,
                'cheap_created': False,
                'error': None
            }

            try:
                # Check stop condition before each major operation
                if should_stop():
                    log_message("Processing stopped by user", gui_callback)
                    return False

                safe_navigate_to_url(driver, f'{base_url}/rims_tyers')

                if should_stop():
                    log_message("Processing stopped by user", gui_callback)
                    return False

                time.sleep(2)
                select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Manufacturer')), 'BROCK / RC')

                if should_stop():
                    log_message("Processing stopped by user", gui_callback)
                    return False

                time.sleep(2)
                select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Size')), str(tyre_dia) if tyre_dia else '')
                input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Min Availability']"), '1')
                input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Rim type']"), model if model else '')
                click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[1]"))

                no_rims_found = check_element_exists(driver, (By.XPATH, "//div[text()= 'No rims found']"))
                if no_rims_found:
                    log_message(f"Element not found for task: {task}", gui_callback)
                    move_task_to_processed(source_pdf, task_data, processing_result)
                    continue

                locator = f"(//tr/td[text()= '{tyre_width}']/following-sibling::td[text()= '{tyre_dia}']/following-sibling::td[text()= '{holes}']/following-sibling::td[text()= '{pcd}']/following-sibling::td[text()= '{t_offset} - {t_offset}']/following-sibling::td[text()= '{centre_bore}'])[1]"
                result_element_1 = check_element_exists(driver, (By.XPATH, locator), timeout=2)
                processing_result['element_found'] = True

                if not result_element_1:
                    log_message(f"Element with specified attributes not found for task: {task}", gui_callback)
                    move_task_to_processed(source_pdf, task_data, processing_result)
                    continue

                click_element(driver, (By.XPATH, locator))

                # Check if we should stop before brand loops
                if should_stop():
                    log_message("Processing stopped by user", gui_callback)
                    return False

                premium_product_created = False
                cheap_product_created = False

                # Try premium brands
                for brand in premium_brands:
                    if premium_product_created or should_stop():
                        break

                    # Verify browser is still active
                    try:
                        _ = driver.current_url
                    except Exception:
                        log_message("Browser closed. Stopping.", gui_callback)
                        return False

                    for season in seasons:
                        if should_stop():
                            break
                        log_message(f"Trying premium brand: {brand} with season: {season}", gui_callback)
                        try:
                            search_product(driver, brand, season, tire_size, gui_callback)
                            if no_result_found(driver):
                                continue
                            result_element_2 = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                            if result_element_2:
                                create_product(driver, title, season, gui_callback)
                                log_message(f"Premium product created: {brand} - {season} for task: {title[:50]}...", gui_callback)
                                premium_product_created = True
                                break
                            else:
                                log_message(f"No match found for {brand} - {season}", gui_callback)
                        except Exception as e:
                            log_message(f"Error trying {brand} - {season}: {e}", gui_callback)
                            continue

                # Try cheap brands
                for brand in cheap_brands:
                    if cheap_product_created or should_stop():
                        break

                    # Verify browser is still active
                    try:
                        _ = driver.current_url
                    except Exception:
                        log_message("Browser closed. Stopping.", gui_callback)
                        return False

                    for season in seasons:
                        if should_stop():
                            break
                        log_message(f"Trying cheap brand: {brand} with season: {season}", gui_callback)
                        try:
                            search_product(driver, brand, season, tire_size, gui_callback)
                            if no_result_found(driver):
                                continue
                            result_element_2 = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                            if result_element_2:
                                create_product(driver, title, season, gui_callback)
                                log_message(f"Cheap product created: {brand} - {season} for task: {title[:50]}...", gui_callback)
                                cheap_product_created = True
                                break
                            else:
                                log_message(f"No match found for {brand} - {season}", gui_callback)
                        except Exception as e:
                            log_message(f"Error trying {brand} - {season}: {e}", gui_callback)
                            continue

                processing_result['premium_created'] = premium_product_created
                processing_result['cheap_created'] = cheap_product_created

                if premium_product_created or cheap_product_created:
                    log_message(f"Task {task_index} completed: Premium={premium_product_created}, Cheap={cheap_product_created}", gui_callback)
                else:
                    log_message(f"Task {task_index}: No products created - no matching brand/season combinations found", gui_callback)

                move_task_to_processed(source_pdf, task_data, processing_result)

            except Exception as e:
                error_str = str(e)
                # Check if this is due to stop request / browser closure
                if should_stop() or 'NewConnectionError' in error_str or 'MaxRetry' in error_str or 'session' in error_str.lower():
                    log_message("Processing stopped - browser closed", gui_callback)
                    return False

                log_message(f"In der Automatisierung ist ein Fehler aufgetreten: {e}", gui_callback)
                processing_result['error'] = str(e)
                move_task_to_processed(source_pdf, task_data, processing_result)
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                return False

        # Successfully completed all tasks
        if driver:
            driver.quit()
        log_message("All tasks processed successfully!", gui_callback)
        return True

    except Exception as e:
        log_message(f"Fehler im Hauptprozess: {e}", gui_callback)
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False

