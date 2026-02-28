"""
Main processor module for PDF to Website Automation.
This module contains the core processing logic that can be called from the GUI.
Uses common functions from script.utils.automation to avoid code duplication.
"""

import os

from script.utils.functions import (
    parse_data_from_pdf, validate_task,
    move_task_to_processed,
    delete_cache_file, remove_duplicate_tasks_from_cache,
    extract_reference_text_from_pdf
)
from script.utils.utils import get_normal_driver
from script.utils.automation import (
    login, process_single_task, is_driver_valid, log_message
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_automation(pdf_path=None, reference_number=None, brand_filter=None, gui_callback=None, stop_checker=None, driver_setter=None):
    """
    Main automation function that processes a single PDF and automates website interactions.

    Args:
        pdf_path: Path to the PDF file to process (required).
        reference_number: Optional reference number (e.g., A12) to extract text for product descriptions.
        brand_filter: Optional brand name to filter tasks (e.g., "Audi", "BMW"). "All Brands" means no filter.
        gui_callback: Optional callback function for logging to GUI.
        stop_checker: Optional function that returns True if stop was requested.
        driver_setter: Optional callback to set driver reference in GUI for cleanup.

    Returns:
        bool: True if processing completed successfully, False otherwise.
    """
    task_list = []
    driver = None
    reference_text = None

    def should_stop():
        return stop_checker() if stop_checker else False

    # Helper function to filter tasks by brand
    def filter_tasks_by_brand(tasks, brand):
        if not brand or brand == "All Brands":
            return tasks

        filtered = []
        brand_lower = brand.lower()
        for task in tasks:
            # Check if brand name is in the Title (case insensitive)
            # Title format is typically "19 Inch... for Audi..."
            if brand_lower in str(task.get('Title', '')).lower():
                filtered.append(task)

        return filtered

    try:
        # Delete cache file for fresh run
        delete_cache_file()

        # Validate PDF path is provided
        if not pdf_path:
            log_message("No PDF file specified. Please select a PDF file.", gui_callback)
            return False

        if not os.path.exists(pdf_path):
            log_message(f"PDF not found: {pdf_path}", gui_callback)
            return False

        pdf_filename = os.path.basename(pdf_path)
        log_message(f"Processing: {pdf_filename}", gui_callback)

        # Extract reference text from the PDF if reference number is provided
        if reference_number:
            reference_text = extract_reference_text_from_pdf(pdf_path, [i.strip() for i in reference_number.split(',')])
            if reference_text:
                log_message(f"Reference text found: {reference_text[:50]}...", gui_callback)
            else:
                log_message(f"Reference '{reference_number}' not found in PDF", gui_callback)

        if should_stop():
            log_message("Processing stopped by user", gui_callback)
            return False

        # Parse data from PDF file
        file_data_list = parse_data_from_pdf(pdf_path)

        if not file_data_list:
            log_message(f"No valid data found in: {pdf_filename}", gui_callback)
            return False

        # Apply Brand Filtering if selected
        if brand_filter and brand_filter != "All Brands":
            original_count = len(file_data_list)
            file_data_list = filter_tasks_by_brand(file_data_list, brand_filter)
            if len(file_data_list) < original_count:
                log_message(f"  → Filtered by brand '{brand_filter}': {len(file_data_list)} of {original_count} tasks kept", gui_callback)

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
            return False

        log_message(f"Total tasks: {len(task_list)}", gui_callback)

        if not task_list:
            log_message("No valid tasks found (check PDF content or Brand Filter). Exiting.", gui_callback)
            return False

        # Remove duplicate tasks
        duplicates_removed, removal_details = remove_duplicate_tasks_from_cache()
        if duplicates_removed > 0:
            log_message(f"Removed {duplicates_removed} duplicate task(s)", gui_callback)
            # Reload task list to exclude duplicates
            seen_task_keys = set()
            unique_task_list = []
            for task in task_list:
                key = (
                    str(task.get('Title', '')),
                    str(task.get('Model', '')),
                    str(task.get('Tyre_Width', '')),
                    str(task.get('Tyre_dia', '')),
                    str(task.get('holes', '')),
                    str(task.get('pcd', '')),
                    str(task.get('centre_bore', '')),
                    str(task.get('offset', '')),
                    str(task.get('tire_size', ''))
                )
                if key not in seen_task_keys:
                    seen_task_keys.add(key)
                    unique_task_list.append(task)
            task_list = unique_task_list
            log_message(f"Tasks after deduplication: {len(task_list)}", gui_callback)

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
            if not is_driver_valid(driver):
                log_message("Browser session closed. Stopping.", gui_callback)
                return False

            log_message(f"Processing task {task_index}/{len(task_list)}: {task.get('Title', 'No Title')[:50]}...", gui_callback)

            source_pdf = task.get('_source_pdf', 'unknown.pdf')
            task_data = {k: v for k, v in task.items() if not k.startswith('_')}

            # Process task using common function
            processing_result = process_single_task(driver, task, gui_callback, stop_checker, reference_text)

            # Check if stop was requested during task processing
            if should_stop():
                log_message("Processing stopped by user", gui_callback)
                return False

            # Log summary for this task
            if processing_result['premium_created'] or processing_result['cheap_created']:
                log_message(f"Task {task_index} completed: Premium={processing_result['premium_created']}, Cheap={processing_result['cheap_created']}", gui_callback)
            else:
                log_message(f"Task {task_index}: No products created - no matching brand/season combinations found", gui_callback)

            move_task_to_processed(source_pdf, task_data, processing_result)

            # Check for errors that should stop processing
            if processing_result.get('error'):
                error_str = processing_result['error']
                if 'Browser closed' in error_str or 'stop requested' in error_str.lower():
                    log_message("Processing stopped - browser closed", gui_callback)
                    return False
                log_message(f"In der Automatisierung ist ein Fehler aufgetreten: {error_str}", gui_callback)
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