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


def main():
    """
    Main function for CLI mode processing.
    Uses common automation functions from script.utils.automation.
    """
    task_list = []

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
            log_message(f"Processing: {pdf_filename}")
            file_data_list = parse_data_from_pdf(file)

            if not file_data_list:
                log_message(f"No valid data found in: {pdf_filename}")
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
                log_message(f"  → {len(valid_tasks)} valid task(s) extracted")
            else:
                log_message(f"  → No valid matches found in: {pdf_filename}")

        # If no new PDFs found, load from cache
        if not all_files:
            log_message("No PDFs in documents folder. Checking cache...")
            cache = load_cache()
            if cache:
                for pdf_filename, cache_entry in cache.items():
                    log_message(f"Loading from cache: {pdf_filename}")
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
                        log_message(f"  → {len(valid_tasks)} valid task(s) from cache")
                    else:
                        log_message(f"  → No valid matches in cached: {pdf_filename}")
            else:
                log_message("No cached data available.")

        log_message(f"Total tasks: {len(task_list)}")

        if not task_list:
            log_message("No valid tasks found. Exiting.")
            return

        # Remove duplicate tasks from cache before processing
        duplicates_removed, removal_details = remove_duplicate_tasks_from_cache()
        if duplicates_removed > 0:
            log_message(f"Removed {duplicates_removed} duplicate task(s) from cache")
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
            log_message(f"Tasks after deduplication: {len(task_list)}")

        # Log brief task summary
        log_message("-" * 40)
        for i, task in enumerate(task_list, 1):
            log_message(f"Task {i}: {task.get('Title', 'No Title')[:50]}...")
        log_message("-" * 40)

        driver = get_normal_driver()
        login(driver)

        for task_index, task in enumerate(task_list, 1):
            # Check if driver is still valid
            if not is_driver_valid(driver):
                log_message("Browser session closed. Stopping.")
                return

            log_message(f"Processing task {task_index}/{len(task_list)}: {task.get('Title', 'No Title')[:50]}...")

            # Extract source PDF filename for tracking
            source_pdf = task.get('_source_pdf', 'unknown.pdf')

            # Create a copy of task without internal tracking field for processing result
            task_data = {k: v for k, v in task.items() if not k.startswith('_')}

            # Process task using common function
            processing_result = process_single_task(driver, task)

            # Log summary for this task
            if processing_result['premium_created'] or processing_result['cheap_created']:
                log_message(
                    f"Task {task_index} completed: Premium={processing_result['premium_created']}, Cheap={processing_result['cheap_created']}")
            else:
                log_message(
                    f"Task {task_index}: No products created - no matching brand/season combinations found")

            # Move task to processed after processing (unconditionally)
            move_task_to_processed(source_pdf, task_data, processing_result)

            # Check for errors that should stop processing
            if processing_result.get('error'):
                log_message(f"In der Automatisierung ist ein Fehler aufgetreten: {processing_result['error']}")
                if driver:
                    driver.quit()
                return

        # Close driver after all tasks completed
        if driver:
            driver.quit()
        log_message("All tasks processed successfully!")

    except Exception as e:
        log_message(f"Fehler im Hauptprozess: {e}")


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
