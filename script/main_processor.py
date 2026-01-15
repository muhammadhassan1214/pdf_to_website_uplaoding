"""
Main processor module for PDF to Website Automation.
This module contains the core processing logic that can be called from the GUI.
Uses common functions from script.utils.automation to avoid code duplication.
"""

import os

from script.utils.functions import (
    get_pdf_paths, parse_data_from_pdf, validate_task,
    load_cache, move_task_to_processed, process_tasks_with_title_splitting,
    delete_cache_file, remove_duplicate_tasks_from_cache
)
from script.utils.utils import get_normal_driver, logger
from script.utils.automation import (
    login, process_single_task, is_driver_valid, log_message
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


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

        # Remove duplicate tasks from cache before processing
        duplicates_removed, removal_details = remove_duplicate_tasks_from_cache()
        if duplicates_removed > 0:
            log_message(f"Removed {duplicates_removed} duplicate task(s) from cache", gui_callback)
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
            processing_result = process_single_task(driver, task, gui_callback, stop_checker)

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

