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
import sys

from script.utils.functions import (
    parse_data_from_pdf, validate_task,
    move_task_to_processed,
    delete_cache_file, remove_duplicate_tasks_from_cache
)
from script.utils.utils import get_normal_driver
from script.utils.automation import (
    login, process_single_task, is_driver_valid, log_message
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# DEBUG CONFIGURATION - Set PDF path here for testing
# =============================================================================
# Set this to a PDF file path for quick debugging, or leave as None to use CLI args
DEBUG_PDF_PATH = r"D:/fiverr/Automation/wladi_keil/pdf_to_website/documents/BYDUNDTELS00442972_1.pdf"
# Example: DEBUG_PDF_PATH = r"D:\fiverr\Automation\wladi_keil\pdf_to_website\documents\test.pdf"
# =============================================================================


def process_single_pdf(pdf_path: str, reference_number: str = None) -> bool:
    """
    Process a single PDF file and run automation.

    Args:
        pdf_path: Path to the PDF file to process.
        reference_number: Optional reference number for product descriptions.

    Returns:
        bool: True if processing completed successfully, False otherwise.
    """
    task_list = []
    driver = None

    try:
        # Validate PDF path
        if not pdf_path:
            log_message("Error: No PDF file specified.")
            return False

        if not os.path.exists(pdf_path):
            log_message(f"Error: PDF file not found: {pdf_path}")
            return False

        pdf_filename = os.path.basename(pdf_path)
        log_message(f"Processing: {pdf_filename}")

        # Delete cache file for fresh run
        delete_cache_file()

        # Parse data from PDF
        file_data_list = parse_data_from_pdf(pdf_path)
        print(file_data_list)

        if not file_data_list:
            log_message(f"No valid data found in: {pdf_filename}")
            return False

        # Validate and filter tasks
        for task in file_data_list:
            is_valid, missing = validate_task(task)
            if is_valid:
                task['_source_pdf'] = pdf_filename
                task_list.append(task)
            else:
                log_message(f"  → Skipping invalid task (missing: {missing})")

        if not task_list:
            log_message(f"No valid tasks found in: {pdf_filename}")
            return False

        log_message(f"  → {len(task_list)} valid task(s) extracted")

        # Remove duplicates
        duplicates_removed, _ = remove_duplicate_tasks_from_cache()
        if duplicates_removed > 0:
            log_message(f"Removed {duplicates_removed} duplicate task(s)")

        # Deduplicate task list
        seen_keys = set()
        unique_tasks = []
        for task in task_list:
            key = (
                task.get('Title', ''),
                task.get('Model', ''),
                str(task.get('Tyre_Width', '')),
                str(task.get('Tyre_dia', '')),
                task.get('holes', ''),
                task.get('pcd', ''),
                task.get('centre_bore', ''),
                task.get('offset', ''),
                task.get('tire_size', '')
            )
            if key not in seen_keys:
                seen_keys.add(key)
                unique_tasks.append(task)
        task_list = unique_tasks

        log_message(f"Total tasks to process: {len(task_list)}")

        # Log task summary
        log_message("-" * 40)
        for i, task in enumerate(task_list, 1):
            title = task.get('Title', 'No Title')
            log_message(f"Task {i}: {title[:60]}{'...' if len(title) > 60 else ''}")
        log_message("-" * 40)

        # Start browser automation
        driver = get_normal_driver()
        login(driver)

        for task_index, task in enumerate(task_list, 1):
            if not is_driver_valid(driver):
                log_message("Browser session closed. Stopping.")
                return False

            title = task.get('Title', 'No Title')
            log_message(f"Processing task {task_index}/{len(task_list)}: {title[:50]}...")

            source_pdf = task.get('_source_pdf', 'unknown.pdf')
            task_data = {k: v for k, v in task.items() if not k.startswith('_')}

            # Process task
            result = process_single_task(driver, task)

            # Log result
            if result['premium_created'] or result['cheap_created']:
                log_message(f"Task {task_index} completed: Premium={result['premium_created']}, Cheap={result['cheap_created']}")
            else:
                log_message(f"Task {task_index}: No products created")

            # Archive task
            move_task_to_processed(source_pdf, task_data, result)

            # Handle errors
            if result.get('error'):
                log_message(f"Error: {result['error']}")
                if driver:
                    driver.quit()
                return False

        # Success
        if driver:
            driver.quit()
        log_message("All tasks processed successfully!")
        return True

    except Exception as e:
        log_message(f"Error: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False


def main():
    """
    Main function for CLI mode processing.
    Supports debug mode with hardcoded PDF path or command-line arguments.
    """
    print("=" * 50)
    print("PDF to Website Automation - CLI Mode")
    print("=" * 50)
    print()

    # Determine PDF path
    pdf_path = None

    # Priority 1: Debug configuration
    if DEBUG_PDF_PATH:
        pdf_path = DEBUG_PDF_PATH
        print(f"[DEBUG MODE] Using hardcoded PDF: {pdf_path}")
        print()

    # Priority 2: Command-line argument
    elif len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Processing PDF from argument: {pdf_path}")
        print()

    # Priority 3: Prompt user
    else:
        print("Usage:")
        print("  python -m script.main <pdf_path>")
        print()
        print("Or set DEBUG_PDF_PATH in main.py for quick testing.")
        print()
        pdf_path = input("Enter PDF path (or press Enter to exit): ").strip()
        if not pdf_path:
            print("No PDF specified. Exiting.")
            return
        print()

    # Process the PDF
    success = process_single_pdf(pdf_path)

    if success:
        print()
        print("=" * 50)
        print("Processing completed successfully!")
        print("=" * 50)
    else:
        print()
        print("=" * 50)
        print("Processing finished with errors or warnings.")
        print("=" * 50)


if __name__ == "__main__":
    main()
