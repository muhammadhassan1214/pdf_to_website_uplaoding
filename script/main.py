"""
PDF to Website Automation - Main Entry Point

This module serves as the main entry point for the automation script.
It can be run in two modes:
1. GUI Mode (default): Run via run.bat or `python -m script.gui`
2. CLI Mode: Run directly with `python -m script.main`

For GUI mode, use the run.bat file or execute:
    python -m script.gui

For CLI mode (legacy), run:
    python -m script.main
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
task_list = []

cheap_brands = ['ARIVO', 'GOODRIDE', 'WESTLAKE']
premium_brands = ['CONTINENTAL', 'GOODYEAR', 'HANKOOK']
seasons = ['Sommerreifen', 'Winterreifen', 'Ganzjahresreifen']

def login(driver):
    try:
        safe_navigate_to_url(driver, f'{base_url}/login')
        input_element(driver, (By.ID, 'email'), os.getenv('LOGIN_USERNAME'))
        input_element(driver, (By.ID, 'password'), os.getenv('LOGIN_PASSWORD'))
        click_element(driver, (By.XPATH, "//button[@type='submit']"))
        time.sleep(5)
    except Exception as e:
        logger.error(f"Fehler beim Login: {e}")

def search_product(driver, brand, season, tire_size):
    try:
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Brands')), brand)
        select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Usages')), season)
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Enter tyre size (e.g. 205/55 R16 91 H)']"),
                      format_tire_size(tire_size))
        input_element(driver, (By.XPATH, "(//input[@placeholder= 'Min Availability'])[2]"), '1')
        click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[2]"))
        wait_while_element_is_displaying(driver, (By.XPATH, "//div[contains(@class, 'animate-spin')]"))
    except Exception as e:
        logger.error(f"Fehler bei der Produktsuche: {e}")

def create_product(driver, title, season):
    try:
        click_element(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"))
        click_element(driver, (By.XPATH, "//button[text()= 'Generate by AI']"))
        # Update title with season info
        season_title = title.replace('All-season', get_season(season))
        input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Enter or edit title...']"), season_title)
        click_element(driver, (By.XPATH, "//button[text()= 'Submit']"))
    except Exception as e:
        logger.error(f"Fehler bei der Produkterstellung: {e}")

def no_result_found(driver):
    return check_element_exists(driver, (By.XPATH, "//div[text()= 'No tyres found']"))

def main():
    try:
        # Delete cache file for fresh run
        delete_cache_file()

        pdf_dir = os.path.join(BASE_DIR, '..', 'documents')
        if not os.path.exists(pdf_dir):
            logger.error(f"PDF directory not found: {pdf_dir}")
            return
        all_files = get_pdf_paths(pdf_dir)
        logger.info(f"Found {len(all_files)} PDF file(s)")

        # parse_data_from_pdf returns a list of dictionaries for each PDF
        for file in all_files:
            pdf_filename = os.path.basename(file)
            logger.info(f"Processing: {pdf_filename}")
            file_data_list = parse_data_from_pdf(file)

            if not file_data_list:
                logger.warning(f"No valid data found in: {pdf_filename}")
                continue

            # Validate and filter tasks
            valid_tasks = []
            for task in file_data_list:
                is_valid, missing = validate_task(task)
                if is_valid:
                    # Add source PDF filename to track origin
                    task['_source_pdf'] = pdf_filename
                    valid_tasks.append(task)

            # Extend task_list with valid items from each PDF
            if valid_tasks:
                task_list.extend(valid_tasks)
                logger.info(f"  → {len(valid_tasks)} valid task(s) extracted")
            else:
                logger.warning(f"  → No valid matches found in: {pdf_filename}")

        # If no new PDFs found, load from cache
        if not all_files:
            logger.info("No PDFs in documents folder. Checking cache...")
            cache = load_cache()
            if cache:
                for pdf_filename, cache_entry in cache.items():
                    logger.info(f"Loading from cache: {pdf_filename}")
                    cached_data = cache_entry.get('data', [])

                    # Apply title splitting to cached data
                    cached_data = process_tasks_with_title_splitting(cached_data, max_title_length=80)

                    # Validate and filter cached tasks
                    valid_tasks = []
                    for task in cached_data:
                        is_valid, missing = validate_task(task)
                        if is_valid:
                            task['_source_pdf'] = pdf_filename
                            valid_tasks.append(task)

                    if valid_tasks:
                        task_list.extend(valid_tasks)
                        logger.info(f"  → {len(valid_tasks)} valid task(s) from cache")
                    else:
                        logger.warning(f"  → No valid matches in cached: {pdf_filename}")
            else:
                logger.info("No cached data available.")

        logger.info(f"Total tasks: {len(task_list)}")

        if not task_list:
            logger.warning("No valid tasks found. Exiting.")
            return

        # Log brief task summary
        logger.info("-" * 40)
        for i, task in enumerate(task_list, 1):
            logger.info(f"Task {i}: {task.get('Title', 'No Title')[:50]}...")
        logger.info("-" * 40)

        driver = get_normal_driver()
        login(driver)

        for task_index, task in enumerate(task_list, 1):
            logger.info(f"Processing task {task_index}/{len(task_list)}: {task.get('Title', 'No Title')[:50]}...")

            # Extract source PDF filename for tracking
            source_pdf = task.get('_source_pdf', 'unknown.pdf')

            # Create a copy of task without internal tracking field for processing result
            task_data = {k: v for k, v in task.items() if not k.startswith('_')}

            # Extract all fields from the AI extraction result
            title = task.get('Title')
            model = task.get('Model')
            tyre_width = task.get('Tyre_Width')
            tyre_dia = task.get('Tyre_dia')
            holes = task.get('holes')
            pcd = task.get('pcd')
            centre_bore = task.get('centre_bore')
            t_offset = task.get('offset')
            tire_size = task.get('tire_size')

            # Initialize processing result
            processing_result = {
                'element_found': False,
                'premium_created': False,
                'cheap_created': False,
                'error': None
            }

            try:
                safe_navigate_to_url(driver, f'{base_url}/rims_tyers')
                time.sleep(2)
                select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Manufacturer')), 'BROCK / RC')
                time.sleep(2)
                select_dropdown_by_text(driver, (By.XPATH, create_xpath('Select Size')), str(tyre_dia) if tyre_dia else '')
                input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Min Availability']"), '1')
                input_element(driver, (By.CSS_SELECTOR, "input[placeholder= 'Rim type']"), model if model else '')
                click_element(driver, (By.XPATH, "(//button[text()= 'Search'])[1]"))
                no_rims_found = check_element_exists(driver, (By.XPATH, "//div[text()= 'No rims found']"))
                if no_rims_found:
                    logger.warning(f"Element not found for task: {task}")
                    # Move task to processed even if element not found
                    move_task_to_processed(source_pdf, task_data, processing_result)
                    continue
                locator = f"(//tr/td[text()= '{tyre_width}']/following-sibling::td[text()= '{tyre_dia}']/following-sibling::td[text()= '{holes}']/following-sibling::td[text()= '{pcd}']/following-sibling::td[text()= '{t_offset} - {t_offset}']/following-sibling::td[text()= '{centre_bore}'])[1]"
                result_element_1 = check_element_exists(driver, (By.XPATH, locator), timeout=2)
                processing_result['element_found'] = True
                if not result_element_1:
                    logger.warning(f"Element with specified attributes not found for task: {task}")
                    # Move task to processed even if specific element not found
                    move_task_to_processed(source_pdf, task_data, processing_result)
                    continue
                click_element(driver, (By.XPATH, locator))

                # Track if premium and cheap products have been created
                premium_product_created = False
                cheap_product_created = False

                # Try premium brands first
                for brand in premium_brands:
                    if premium_product_created:
                        break  # Already created a premium product, move to cheap brands

                    for season in seasons:
                        logger.info(f"Trying premium brand: {brand} with season: {season}")
                        try:
                            search_product(driver, brand, season, tire_size)
                            if no_result_found(driver):
                                continue
                            result_element_2 = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                            if result_element_2:
                                create_product(driver, title, season)
                                logger.info(f"Premium product created: {brand} - {season} for task: {title[:50]}...")
                                premium_product_created = True
                                break  # Move to cheap brands after creating premium product
                            else:
                                logger.info(f"No match found for {brand} - {season}")
                        except Exception as e:
                            logger.warning(f"Error trying {brand} - {season}: {e}")
                            continue

                # Try cheap brands
                for brand in cheap_brands:
                    if cheap_product_created:
                        break  # Already created a cheap product, move to next task

                    for season in seasons:
                        logger.info(f"Trying cheap brand: {brand} with season: {season}")
                        try:
                            search_product(driver, brand, season, tire_size)
                            if no_result_found(driver):
                                continue
                            result_element_2 = check_element_exists(driver, (By.XPATH, "(//table)[2]/tbody/tr[1]"), timeout=2)
                            if result_element_2:
                                create_product(driver, title, season)
                                logger.info(f"Cheap product created: {brand} - {season} for task: {title[:50]}...")
                                cheap_product_created = True
                                break  # Move to next task after creating cheap product
                            else:
                                logger.info(f"No match found for {brand} - {season}")
                        except Exception as e:
                            logger.warning(f"Error trying {brand} - {season}: {e}")
                            continue

                # Update processing result
                processing_result['premium_created'] = premium_product_created
                processing_result['cheap_created'] = cheap_product_created

                # Log summary for this task
                if premium_product_created or cheap_product_created:
                    logger.info(f"Task {task_index} completed: Premium={premium_product_created}, Cheap={cheap_product_created}")
                else:
                    logger.warning(f"Task {task_index}: No products created - no matching brand/season combinations found")

                # Move task to processed after processing (unconditionally)
                move_task_to_processed(source_pdf, task_data, processing_result)

            except Exception as e:
                logger.error(f"In der Automatisierung ist ein Fehler aufgetreten: {e}")
                processing_result['error'] = str(e)
                # Move task to processed even on error
                move_task_to_processed(source_pdf, task_data, processing_result)
                if driver:
                    driver.quit()
                    return

    except Exception as e:
        logger.error(f"Fehler im Hauptprozess: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("PDF to Website Automation - CLI Mode")
    print("=" * 50)
    print()
    print("TIP: For GUI mode with better controls, use:")
    print("     - Double-click 'run.bat'")
    print("     - Or run: python -m script.gui")
    print()
    print("Starting CLI mode processing...")
    print()
    main()
