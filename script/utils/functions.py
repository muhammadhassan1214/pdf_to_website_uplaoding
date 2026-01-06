import os
import re
import json
import time
import shutil
import pdfplumber
import pandas as pd
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Rate limiting configuration
LAST_API_CALL_TIME = 0
MIN_API_INTERVAL = 3  # Minimum seconds between API calls

# Cache configuration
CACHE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ai_extraction_cache.json")
PROCESSED_TASKS_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "processed_tasks.json")
PROCESSED_DOCS_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "processed_documents")


# ============================================
# Rate Limiting Functions
# ============================================

def wait_for_rate_limit():
    """
    Enforce rate limiting between API calls.
    Waits if not enough time has passed since the last API call.
    """
    global LAST_API_CALL_TIME

    current_time = time.time()
    elapsed = current_time - LAST_API_CALL_TIME

    if elapsed < MIN_API_INTERVAL:
        wait_time = MIN_API_INTERVAL - elapsed
        print(f"Rate limiting: waiting {wait_time:.2f} seconds before next API call...")
        time.sleep(wait_time)

    LAST_API_CALL_TIME = time.time()


def update_last_api_call_time():
    """
    Update the timestamp of the last API call.
    """
    global LAST_API_CALL_TIME
    LAST_API_CALL_TIME = time.time()


# ============================================
# Cache Management Functions
# ============================================

def load_cache():
    """
    Load the cache from the JSON file.

    Returns:
        dict: Cache data with structure:
            {
                "pdf_filename": {
                    "data": [...extracted data...],
                    "processed_at": "ISO timestamp",
                    "source_path": "original path"
                }
            }
    """
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load cache file: {e}")
            return {}
    return {}


def save_cache(cache_data):
    """
    Save the cache to the JSON file.

    Args:
        cache_data: Dictionary containing cached extraction results
    """
    try:
        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving cache: {e}")


def get_cached_result(pdf_filename):
    """
    Get cached extraction result for a PDF file.

    Args:
        pdf_filename: Name of the PDF file (not full path)

    Returns:
        list or None: Cached data if exists, None otherwise
    """
    cache = load_cache()
    if pdf_filename in cache:
        print(f"Cache hit: Using cached data for '{pdf_filename}'")
        return cache[pdf_filename].get('data')
    return None


def cache_result(pdf_filename, data, source_path):
    """
    Cache the extraction result for a PDF file.

    Args:
        pdf_filename: Name of the PDF file
        data: Extracted data to cache
        source_path: Original path of the PDF file
    """
    cache = load_cache()
    cache[pdf_filename] = {
        'data': data,
        'processed_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source_path': source_path
    }
    save_cache(cache)
    print(f"Cached extraction results for '{pdf_filename}'")


def delete_from_cache(pdf_filename):
    """
    Delete a specific entry from the cache.

    Args:
        pdf_filename: Name of the PDF file to remove from cache

    Returns:
        bool: True if entry was deleted, False if not found
    """
    cache = load_cache()
    if pdf_filename in cache:
        del cache[pdf_filename]
        save_cache(cache)
        print(f"Deleted '{pdf_filename}' from cache")
        return True
    return False


def clear_cache():
    """
    Clear all entries from the cache.
    """
    save_cache({})
    print("Cache cleared")


def delete_cache_file():
    """
    Delete the cache JSON file completely.
    Called at the start of each run to ensure fresh processing.

    Returns:
        bool: True if file was deleted, False if it didn't exist
    """
    if os.path.exists(CACHE_FILE_PATH):
        try:
            os.remove(CACHE_FILE_PATH)
            print("Cache file deleted for fresh run")
            return True
        except OSError as e:
            print(f"Warning: Could not delete cache file: {e}")
            return False
    return False


def get_all_cached_files():
    """
    Get a list of all cached PDF filenames.

    Returns:
        list: List of cached PDF filenames
    """
    cache = load_cache()
    return list(cache.keys())


# ============================================
# Processed Tasks Management Functions
# ============================================

def load_processed_tasks():
    """
    Load the processed tasks from the JSON file.

    Returns:
        dict: Processed tasks data with structure:
            {
                "pdf_filename": {
                    "tasks": [...processed task data...],
                    "processed_at": "ISO timestamp",
                    "source_path": "original path"
                }
            }
    """
    if os.path.exists(PROCESSED_TASKS_FILE_PATH):
        try:
            with open(PROCESSED_TASKS_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load processed tasks file: {e}")
            return {}
    return {}


def save_processed_tasks(processed_data):
    """
    Save the processed tasks to the JSON file.

    Args:
        processed_data: Dictionary containing processed task results
    """
    try:
        with open(PROCESSED_TASKS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving processed tasks: {e}")


def move_task_to_processed(pdf_filename, task_data, processing_result=None):
    """
    Move a specific task entry from ai_extraction_cache.json to processed_tasks.json.
    This removes the task from the cache and adds it to processed tasks.

    Args:
        pdf_filename: Name of the PDF file
        task_data: The task dictionary that was processed
        processing_result: Optional dict with processing outcome (e.g., {'premium_created': True, 'cheap_created': False})

    Returns:
        bool: True if successfully moved, False otherwise
    """
    # Load both files
    cache = load_cache()
    processed = load_processed_tasks()

    # Initialize processed entry for this PDF if not exists
    if pdf_filename not in processed:
        processed[pdf_filename] = {
            'tasks': [],
            'processed_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source_path': cache.get(pdf_filename, {}).get('source_path', '')
        }

    # Add the task to processed with its result
    task_entry = {
        'task': task_data,
        'processed_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'result': processing_result or {}
    }
    processed[pdf_filename]['tasks'].append(task_entry)

    # Remove the task from cache
    if pdf_filename in cache:
        cached_tasks = cache[pdf_filename].get('data', [])
        # Remove the matching task from cache
        updated_tasks = [t for t in cached_tasks if t != task_data]

        if updated_tasks:
            # Update cache with remaining tasks
            cache[pdf_filename]['data'] = updated_tasks
        else:
            # No more tasks for this PDF, remove the entire entry
            del cache[pdf_filename]

    # Save both files
    save_cache(cache)
    save_processed_tasks(processed)

    print(f"Moved task from cache to processed_tasks for '{pdf_filename}'")
    return True


def get_processed_tasks_count(pdf_filename):
    """
    Get the count of processed tasks for a specific PDF.

    Args:
        pdf_filename: Name of the PDF file

    Returns:
        int: Number of processed tasks
    """
    processed = load_processed_tasks()
    if pdf_filename in processed:
        return len(processed[pdf_filename].get('tasks', []))
    return 0


# ============================================
# File Management Functions
# ============================================

def ensure_processed_folder_exists():
    """
    Ensure the processed documents folder exists.
    """
    if not os.path.exists(PROCESSED_DOCS_FOLDER):
        os.makedirs(PROCESSED_DOCS_FOLDER)
        print(f"Created processed documents folder: {PROCESSED_DOCS_FOLDER}")


def move_to_processed(pdf_path):
    """
    Move a processed PDF file to the processed documents folder.

    Args:
        pdf_path: Full path to the PDF file

    Returns:
        str or None: New path of the moved file, or None if failed
    """
    ensure_processed_folder_exists()

    try:
        filename = os.path.basename(pdf_path)
        destination = os.path.join(PROCESSED_DOCS_FOLDER, filename)

        # Handle duplicate filenames
        if os.path.exists(destination):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(destination):
                destination = os.path.join(PROCESSED_DOCS_FOLDER, f"{base}_{counter}{ext}")
                counter += 1

        shutil.move(pdf_path, destination)
        print(f"Moved processed PDF to: {destination}")
        return destination
    except (IOError, shutil.Error) as e:
        print(f"Error moving file: {e}")
        return None


def cleanup_after_use(pdf_filename):
    """
    Clean up cached data after it has been used by the web automation script.
    This maintains storage efficiency and data hygiene.

    Args:
        pdf_filename: Name of the PDF file whose cache should be cleaned

    Returns:
        bool: True if cleanup was successful
    """
    return delete_from_cache(pdf_filename)


def get_unprocessed_pdfs(directory):
    """
    Get list of PDFs that haven't been processed yet (not in cache).

    Args:
        directory: Directory to scan for PDF files

    Returns:
        list: List of paths to unprocessed PDF files
    """
    all_pdfs = get_pdf_paths(directory)
    cache = load_cache()

    unprocessed = []
    for pdf_path in all_pdfs:
        filename = os.path.basename(pdf_path)
        if filename not in cache:
            unprocessed.append(pdf_path)

    return unprocessed


def get_pdf_paths(directory):
    pdf_paths = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_paths.append(os.path.join(root, file))
    return pdf_paths

def extract_model_from_text(pdf_text):
    """
    Extract the model identifier from PDF text (e.g., "Modell B44" -> "B44").

    Args:
        pdf_text: Full text extracted from the PDF

    Returns:
        str: Model identifier or None if not found
    """
    # Pattern to match "Modell" followed by the model name (e.g., "Modell B44")
    pattern = r'Modell\s+([A-Za-z0-9]+)'
    match = re.search(pattern, pdf_text)
    if match:
        return match.group(1)
    return None


def extract_wheel_size_from_text(pdf_text):
    """
    Extract the wheel size and tyre width from PDF text (e.g., "Radgröße 8,5Jx19H2" or "Radgre 8,5Jx19H2").

    Args:
        pdf_text: Full text extracted from the PDF

    Returns:
        tuple: (wheel_size_formatted, tyre_width, tyre_size) or (None, None, None) if not found
            - wheel_size_formatted: Full wheel size string with inch designation (e.g., "8,5Jx19H2 (19)")
            - tyre_width: Width as float (e.g., 8.5)
            - tyre_size: Inch size as int (e.g., 19)
    """
    # Pattern to match "Radgröße" or "Radgre" (German umlaut variations) followed by wheel size
    # Wheel size format: e.g., "8,5Jx19H2" - number, optional comma, decimal, J, x, inch size, H, number
    pattern = r'Radgr[öo]?[ße]?e?\s+(\d+[,.]?\d*Jx\d+H?\d*)'
    match = re.search(pattern, pdf_text, re.IGNORECASE)
    if match:
        wheel_size = match.group(1)

        # Extract tyre width (e.g., "8,5Jx19H2" -> 8.5)
        width_match = re.search(r'^(\d+[,.]?\d*)', wheel_size)
        tyre_width = None
        if width_match:
            width_str = width_match.group(1).replace(',', '.')
            tyre_width = float(width_str)

        # Extract inch size from wheel size (e.g., "8,5Jx19H2" -> 19)
        inch_match = re.search(r'Jx(\d+)', wheel_size)
        tyre_size = None
        if inch_match:
            tyre_size = int(inch_match.group(1))
            wheel_size_formatted = f"{wheel_size} ({tyre_size})"
            return wheel_size_formatted, tyre_width, tyre_size

        return wheel_size, tyre_width, tyre_size
    return None, None, None


def process_pdf(pdf_path):
    """
    Process a PDF file and extract text and tables.

    Returns:
        tuple: (all_text, first_table_data, merged_csv_path)
            - all_text: Full text of the PDF
            - first_table_data: List of dictionaries containing first table data (without header)
            - merged_csv_path: File path to the CSV containing merged tables (3rd onwards)
    """
    all_text = ""
    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
    
            # -------------------------------
            # 1. Extract full text from page
            # -------------------------------
            text = page.extract_text()
            if text:
                all_text += f"\n\n--- Page {page_num} ---\n"
                all_text += text
    
            # -------------------------------
            # 2. Extract tables from page
            # -------------------------------
            page_tables = page.extract_tables()
    
            for t_index, table in enumerate(page_tables, start=1):
                all_tables.append(table)

    # -------------------------------
    # 3. Process tables according to requirements
    # -------------------------------

    first_table_data = []
    merged_csv_path = None

    # Process first table (without header) - return as list of dictionaries
    if len(all_tables) >= 1:
        first_table = all_tables[0]
        if len(first_table) > 1:  # Has header and data rows
            header = first_table[0]
            data_rows = first_table[1:]  # Exclude header
            first_table_data = [dict(zip(header, row)) for row in data_rows]

    # Skip second table (index 1)

    # Process remaining tables (index 2 onwards) - merge into single CSV
    if len(all_tables) >= 3:
        merged_data = []
        header = None  # Initialize header variable

        for table_index, table in enumerate(all_tables[2:], start=3):
            if len(table) > 1:  # Has header and data rows
                # Use header from first of these tables for column names
                if table_index == 3:
                    header = table[0]
                # Exclude header from each table, only take data rows
                data_rows = table[1:]
                merged_data.extend(data_rows)

        if merged_data:
            # Create DataFrame with the header from the first merged table
            merged_df = pd.DataFrame(merged_data, columns=header)

            # Generate CSV file path based on input PDF path
            pdf_dir = os.path.dirname(pdf_path)
            pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
            merged_csv_path = os.path.join(pdf_dir, f"{pdf_basename}_merged_tables.csv")

            # Save to CSV
            merged_df.to_csv(merged_csv_path, index=False)

    return all_text, first_table_data, merged_csv_path


def extract_manufacturer(vehicle_info):
    """
    Extract the manufacturer name from the vehicle info string.

    Args:
        vehicle_info: String containing vehicle details

    Returns:
        str: Manufacturer name (e.g., 'Audi', 'Seat', 'Skoda', 'Mercedes', etc.)
    """
    if not vehicle_info or not isinstance(vehicle_info, str):
        return None

    # Clean the string - get the first line which typically contains the model name
    first_line = vehicle_info.strip().split('\n')[0].strip()

    # Define known manufacturers and their patterns
    # Order matters - more specific patterns should come first
    manufacturers = {
        'Audi': r'^Audi\b',
        'Seat': r'^Seat\b',
        'Skoda': r'^Skoda\b',
        'VW': r'^(VW|Volkswagen)\b',
        'BMW': r'^BMW\b',
        'Porsche': r'^Porsche\b',
        'Infiniti': r'^Infiniti\b',
        'Ssangyong': r'^(Ssangyong|KG\s*Mobility)\b',
        # Mercedes patterns - must match various model naming conventions
        # Including patterns like "C 63 AMG", "E 500", "EQA-Klasse", "EQB-Klasse"
        'Mercedes': r'^(Mercedes|A-Klasse|B-Klasse|C-Klasse|E-Klasse|S-Klasse|G-Klasse|R-Klasse|V-Klasse|GLA|GLB|GLC|GLE|GLK|GLS|CLA|CLE|CLS|SL\b|SLC|SLK|AMG|EQ[ABCES]?-?Klasse|Vito|Viano|Citan|Sprinter|[ABCEGSRV]\s+\d|EQ[ABCES]\b)',
    }

    for manufacturer, pattern in manufacturers.items():
        if re.search(pattern, first_line, re.IGNORECASE):
            return manufacturer

    # Additional check for Mercedes models that start with class letter followed by space and number
    # e.g., "C 63 AMG", "E 500", etc.
    if re.match(r'^[ABCEGSRV]\s*[-]?Klasse\b', first_line, re.IGNORECASE):
        return 'Mercedes'
    if re.match(r'^[ABCEGSRV]\s+\d', first_line, re.IGNORECASE):
        return 'Mercedes'
    if re.match(r'^EQ[ABCES]', first_line, re.IGNORECASE):
        return 'Mercedes'
    # Match single letter followed by space and digits (like "C 63", "E 500")
    if re.match(r'^[ABCEGSRV]\s*\d+', first_line, re.IGNORECASE):
        return 'Mercedes'

    # If no known manufacturer found, try to extract first word as manufacturer
    words = first_line.split()
    if words:
        return words[0]

    return None


def extract_model_name(vehicle_info):
    """
    Extract the model name from the vehicle info string.

    Args:
        vehicle_info: String containing vehicle details

    Returns:
        str: Model name (e.g., 'A4', 'Ibiza', 'Fabia', etc.)
    """
    if not vehicle_info or not isinstance(vehicle_info, str):
        return None

    # Get the first line which typically contains the model name
    first_line = vehicle_info.strip().split('\n')[0].strip()
    return first_line


def filter_and_group_by_manufacturer_and_tire_size(csv_path):
    """
    Filter and group vehicle data by manufacturer and tire size.

    Important principles:
    - Each vehicle model has its own approved tyre sizes.
    - Tyre sizes are manufacturer-specific and model-specific.
    - NEVER mix different manufacturers in one group.
    - A group must contain only ONE manufacturer and its models only.
    - Each model appears ONLY ONCE with its most frequent tire size (mode).
    - Models are grouped only if they share the exact same selected tire size.

    Args:
        csv_path: Path to the CSV file containing vehicle data

    Returns:
        dict: Dictionary with structure:
            {
                (manufacturer, tire_size): {
                    'manufacturer': str,
                    'tire_size': str,
                    'models': [list of model names],
                    'title': str (formatted title for the group)
                }
            }
    """
    from collections import Counter

    # Read the CSV file
    df = pd.read_csv(csv_path)

    # Get column names
    columns = df.columns.tolist()

    # Column 0 (index 0) is manufacturer/vehicle info
    # Column 2 (index 2) is tire size
    vehicle_col = columns[0]
    tire_col = columns[2]

    # Step 1: Collect all tire sizes for each (manufacturer, model) pair
    # Key: (manufacturer, model_name), Value: list of tire sizes
    model_tire_sizes = defaultdict(list)

    # Track the last known vehicle info for rows with empty first column
    last_vehicle_info = None

    for idx, row in df.iterrows():
        vehicle_info = row[vehicle_col]
        tire_size = row[tire_col]

        # Handle empty vehicle info (continuation rows)
        if pd.isna(vehicle_info) or vehicle_info == '':
            vehicle_info = last_vehicle_info
        else:
            last_vehicle_info = vehicle_info

        # Skip if no vehicle info or tire size
        if not vehicle_info or pd.isna(tire_size) or tire_size == '':
            continue

        # Extract manufacturer and model
        manufacturer = extract_manufacturer(vehicle_info)
        model_name = extract_model_name(vehicle_info)

        if manufacturer and model_name and tire_size:
            # Clean tire size (remove any extra whitespace)
            tire_size = str(tire_size).strip()

            # Collect this tire size for the model
            model_tire_sizes[(manufacturer, model_name)].append(tire_size)

    # Step 2: For each model, select the most frequent tire size (mode)
    # Key: (manufacturer, model_name), Value: most frequent tire size
    model_selected_tire = {}

    for (manufacturer, model_name), tire_sizes in model_tire_sizes.items():
        # Count occurrences of each tire size
        tire_counter = Counter(tire_sizes)
        # Get the most common tire size (mode)
        most_common_tire = tire_counter.most_common(1)[0][0]
        model_selected_tire[(manufacturer, model_name)] = most_common_tire

    # Step 3: Group models by manufacturer and their selected tire size
    # Key: (manufacturer, tire_size), Value: set of models
    grouped_data = defaultdict(set)

    for (manufacturer, model_name), tire_size in model_selected_tire.items():
        grouped_data[(manufacturer, tire_size)].add(model_name)

    # Step 4: Format the results
    results = {}
    for (manufacturer, tire_size), models in grouped_data.items():
        models_list = sorted(list(models))

        # Create a formatted title
        # Extract just the model names without manufacturer prefix for cleaner title
        clean_model_names = []
        for model in models_list:
            # Remove manufacturer name from the beginning if present
            clean_name = model
            if clean_name.lower().startswith(manufacturer.lower()):
                clean_name = clean_name[len(manufacturer):].strip()
            clean_model_names.append(clean_name)

        # Format: "18 Inch Summer Complete Wheels suitable for {Manufacturer} {Model1}, {Model2}, ..."
        # Extract inch size from tire size (e.g., "225/40R19" -> "19")
        inch_match = re.search(r'R(\d+)', tire_size)
        inch_size = inch_match.group(1) if inch_match else "Unknown"

        if len(clean_model_names) > 1:
            models_str = ', '.join(clean_model_names[:-1]) + ', ' + clean_model_names[-1]
        else:
            models_str = clean_model_names[0] if clean_model_names else ''

        title = f"{inch_size} Inch All-season Complete Wheels set for {manufacturer} {models_str}"

        results[(manufacturer, tire_size)] = {
            'manufacturer': manufacturer,
            'tire_size': tire_size,
            'models': models_list,
            'title': title
        }

    return results


def get_valid_tire_groups(csv_path):
    """
    Get valid tire groups where models share the exact same tire size within a manufacturer.

    Each model appears ONLY ONCE with its most frequent (mode) tire size.
    Models are then grouped by manufacturer + selected tire size.

    Args:
        csv_path: Path to the CSV file containing vehicle data

    Returns:
        list: List of valid groups, each containing:
            {
                'manufacturer': str,
                'tire_size': str,
                'models': [list of model names],
                'title': str (formatted title for the group)
            }
    """
    grouped_data = filter_and_group_by_manufacturer_and_tire_size(csv_path)

    # Convert to list and sort by manufacturer, then by tire size
    valid_groups = []
    for key, group in grouped_data.items():
        valid_groups.append(group)

    # Sort by manufacturer name, then by tire size
    valid_groups.sort(key=lambda x: (x['manufacturer'], x['tire_size']))

    return valid_groups


def extract_raw_text_from_pdf(pdf_path):
    """
    Extract raw text from all pages of a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        str: Concatenated text from all pages
    """
    all_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                all_text += f"\n\n--- Page {page_num} ---\n"
                all_text += text

            # Also extract table content as text for better context
            page_tables = page.extract_tables()
            for table in page_tables:
                for row in table:
                    if row:
                        row_text = ' | '.join([str(cell) if cell else '' for cell in row])
                        all_text += f"\n{row_text}"

    return all_text


def extract_data_with_ai(pdf_text):
    """
    Use OpenAI API to extract and structure data from PDF text.

    Args:
        pdf_text: Raw text extracted from the PDF

    Returns:
        list: List of dictionaries containing structured output data
    """
    # Define the JSON schema for the expected output
    system_prompt = """You are an expert at extracting and structuring data from German vehicle certification documents (ABE - Allgemeine Betriebserlaubnis).

Your task is to analyze the provided PDF text and extract the following information:

## STEP 1: Extract Basic Wheel Information (same for all entries)

1. **Model**: The wheel/rim model identifier (e.g., "B32", "B44", "KT4", "KT9", "KT3-T"). Look for patterns like "Modell" followed by the model name.

2. **Wheel Size / Radgröße**: The wheel dimensions (e.g., "8,5Jx19H2"). Look for "Radgröße" followed by the size.
   - From this, extract:
     - Tyre_Width: The width number before 'J' (e.g., 8.5 from "8,5Jx19H2"). Convert comma to decimal point.
     - Tyre_dia: The diameter number after 'Jx' (e.g., 19 from "8,5Jx19H2")
     - wheel_size: The full wheel size string (e.g., "8,5Jx19H2")

3. **From the FIRST specification table** (usually contains wheel specs like Lochzahl/Lochkreis/Mittenbohrung/Einpreßtiefe):
   - holes: Number of bolt holes (Lochzahl, e.g., "4", "5")
   - pcd: Pitch Circle Diameter (Lochkreis, e.g., "108", "112", "120")
   - centre_bore: Center bore diameter (Mittenbohrung, e.g., "66.6", "72.6", "63.4"). Convert comma to decimal point.
   - offset: Offset value (Einpreßtiefe/ET, e.g., "48", "42", "35")
   These are often in a format like "5/112/66,6" with offset separately.

## STEP 2: Process Vehicle Compatibility Tables - CRITICAL

The PDF contains vehicle compatibility tables listing vehicle manufacturers, models, and their approved tyre sizes (Reifengröße).

**IMPORTANT LOGIC - Follow these steps precisely:**

1. **Extract ALL entries from vehicle compatibility tables**: Collect every row showing manufacturer, model, and tyre size (e.g., "225/40R19", "245/40R19").

2. **Group by manufacturer first**: NEVER mix manufacturers. Each manufacturer (Audi, Mercedes, BMW, Seat, Skoda, VW, etc.) must be processed separately.

3. **For each model, find the MOST FREQUENT tyre size**: If "Audi A5" appears with 5 different tyre sizes, count how many times each size appears and select the one that appears most often (the mode).

4. **Group models by their selected tyre size within the same manufacturer**: After selecting one tyre size per model, group together all models from the same manufacturer that share the exact same tyre size.

5. **Create a SEPARATE entry for each unique (manufacturer + tyre_size) combination**: 
   - If Audi models group into 3 different tyre sizes (225/40R19, 245/40R19, 255/35R19), create 3 separate entries
   - If Mercedes models group into 2 different tyre sizes, create 2 separate entries
   - And so on for each manufacturer

## STEP 3: Generate Titles

For each unique (manufacturer + tyre_size) group, generate a title:
Format: "{inch_size} Inch All-season Complete Wheels set for {Manufacturer} {Model1}, {Model2}, {Model3}"

Where:
- inch_size = extracted from tyre size (e.g., "225/40R19" -> "19")
- Models listed are ONLY those from the same manufacturer sharing that exact tyre size

## Example Outputs Expected:

If the PDF has:
- Audi A4, A5, S4 all using 225/40R19
- Audi A5, A6 using 245/40R19  
- Mercedes C63, E63 using 255/35R19

You should return 3 entries:
1. Title: "19 Inch All-season Complete Wheels set for Audi A4, A5, S4" (for 225/40R19)
2. Title: "19 Inch All-season Complete Wheels set for Audi A5, A6" (for 245/40R19)
3. Title: "19 Inch All-season Complete Wheels set for Mercedes-Benz C63, E63" (for 255/35R19)

## Rules:
- Return MULTIPLE entries - one for each unique manufacturer+tyre_size combination found
- Each vehicle model appears with its most frequent tyre size
- Never mix manufacturers in one title
- Model, Tyre_Width, Tyre_dia, holes, pcd, centre_bore, offset, wheel_size are the SAME across all entries (from the wheel specs)
- Only the Title differs based on the vehicle grouping
- If any data point cannot be found, return null for that field
- Be precise with number formats: use decimal points (not commas) for decimal numbers

Return your response as a JSON object with a "data" key containing an array:
{
    "data": [
        {
            "Title": "Generated title for group 1",
            "Model": "Wheel model identifier",
            "Tyre_Width": numeric,
            "Tyre_dia": numeric,
            "holes": "string",
            "pcd": "string",
            "centre_bore": "string",
            "offset": "string",
            "tire_size": "string"
        },
        {
            "Title": "Generated title for group 2",
            ...same wheel specs...
        },
        ...more entries for each manufacturer+tyre_size group...
    ]
}"""

    user_prompt = f"""Please analyze this German vehicle certification PDF text and extract the structured data:

{pdf_text}

Return ONLY a valid JSON array with the extracted data. No additional text or explanation."""

    try:
        # Apply rate limiting before making API call
        wait_for_rate_limit()

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for more consistent/accurate outputs
            response_format={"type": "json_object"}
        )

        # Parse the JSON response
        response_content = response.choices[0].message.content
        parsed_response = json.loads(response_content)

        # Handle both array response and object with 'data' key
        if isinstance(parsed_response, list):
            return parsed_response
        elif isinstance(parsed_response, dict):
            # Check if it's wrapped in a key like 'data' or 'results'
            if 'data' in parsed_response:
                return parsed_response['data']
            elif 'results' in parsed_response:
                return parsed_response['results']
            else:
                # It's a single object, wrap in list
                return [parsed_response]

        return parsed_response

    except json.JSONDecodeError as e:
        print(f"Error parsing AI response: {e}")
        return []
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return []


def extract_wheel_specs_from_first_table(first_table_data):
    """
    Extract wheel specifications (holes, pcd, centre_bore, offset) from the first table.

    The first table typically contains wheel specs in formats like:
    - Lochzahl (holes): "5"
    - Lochkreis (pcd): "112"
    - Mittenbohrung (centre_bore): "66,6" or "66.6"
    - Einpreßtiefe/Einpresstiefe/ET (offset): "48"

    Or combined format like "5/112/66,6" with offset separately.

    Args:
        first_table_data: List of dictionaries from first table

    Returns:
        dict: Dictionary with holes, pcd, centre_bore, offset (or None for missing values)
    """
    specs = {
        'holes': None,
        'pcd': None,
        'centre_bore': None,
        'offset': None
    }

    if not first_table_data:
        return specs

    # Look through all rows and columns for the specs
    for row in first_table_data:
        for key, value in row.items():
            if value is None:
                continue
            value_str = str(value).strip()
            # Normalize key by removing newlines and converting to lowercase
            key_normalized = str(key).replace('\n', ' ').lower() if key else ''

            # Check for combined format like "5/112/66,6"
            combined_match = re.match(r'^(\d+)\s*/\s*(\d+)\s*/\s*(\d+[,.]?\d*)$', value_str)
            if combined_match:
                specs['holes'] = combined_match.group(1)
                specs['pcd'] = combined_match.group(2)
                specs['centre_bore'] = combined_match.group(3).replace(',', '.')
                continue

            # Check individual columns by header name patterns
            # Handle variations with newlines, spaces, and German umlauts
            if any(x in key_normalized for x in ['lochzahl', 'holes', 'bolt holes']):
                match = re.search(r'(\d+)', value_str)
                if match and specs['holes'] is None:
                    specs['holes'] = match.group(1)
            elif any(x in key_normalized for x in ['lochkreis', 'pcd', 'pitch circle']):
                match = re.search(r'(\d+)', value_str)
                if match and specs['pcd'] is None:
                    specs['pcd'] = match.group(1)
            elif any(x in key_normalized for x in ['mittenbohrung', 'mittenloch', 'centre bore', 'center bore', 'hub bore']):
                match = re.search(r'(\d+[,.]?\d*)', value_str)
                if match and specs['centre_bore'] is None:
                    specs['centre_bore'] = match.group(1).replace(',', '.')
            elif any(x in key_normalized for x in ['einpress', 'offset', ' et ', 'et(mm)', 'tiefe']):
                match = re.search(r'(\d+)', value_str)
                if match and specs['offset'] is None:
                    specs['offset'] = match.group(1)

    return specs


def validate_extracted_data(data_item):
    """
    Validate extracted data to ensure it meets quality requirements.

    Validation rules:
    - Title should start with a number (e.g., "19 Inch...")
    - Required fields should not be None or empty

    Args:
        data_item: Dictionary containing extracted data

    Returns:
        tuple: (is_valid, error_messages)
    """
    errors = []

    # Check if title starts with a number
    title = data_item.get('Title')
    if title:
        if not re.match(r'^\d+', str(title).strip()):
            errors.append("Title should start with a number (e.g., '19 Inch...')")
    else:
        errors.append("Title is missing")

    # Check required numeric fields
    if data_item.get('Tyre_dia') is None:
        errors.append("Tyre_dia is missing")

    if data_item.get('Tyre_Width') is None:
        errors.append("Tyre_Width is missing")

    # Check required string fields
    required_strings = ['Model', 'holes', 'pcd', 'centre_bore', 'offset', 'tire_size']
    for field in required_strings:
        value = data_item.get(field)
        if value is None or str(value).strip() == '':
            errors.append(f"{field} is missing")

    return len(errors) == 0, errors


def split_long_title_task(task, max_length=80):
    """
    Split a task with a long title into multiple tasks with shorter titles.

    The title format is typically:
    "{size} Inch All-season Complete Wheels set for {Manufacturer} {Model1}, {Model2}, ..."

    This function splits the models into groups that fit within the max_length limit.

    Args:
        task: Dictionary containing task data with a 'Title' key
        max_length: Maximum allowed title length (default: 80)

    Returns:
        list: List of tasks (original if title <= max_length, or split tasks)
    """
    title = task.get('Title')

    if not title or len(title) <= max_length:
        return [task]

    # Parse the title to extract the prefix and models
    # Expected format: "{size} Inch All-season Complete Wheels set for {Manufacturer} {Models}"
    # or "{size} Inch All-season Complete Wheels set for {Models}"

    match = re.match(r'^(\d+\s+Inch\s+All-season\s+Complete\s+Wheels\s+set\s+for\s+)(.+)$', title)

    if not match:
        # Can't parse the title format, return as-is
        return [task]

    prefix = match.group(1)  # e.g., "18 Inch All-season Complete Wheels set for "
    models_part = match.group(2)  # e.g., "BMW 1er-Reihe, 2er-Reihe, ..."

    # Try to extract manufacturer from the models part
    # Check if it starts with a known manufacturer
    manufacturer = None
    manufacturer_patterns = [
        (r'^(BMW)\s+', 'BMW'),
        (r'^(Audi)\s+', 'Audi'),
        (r'^(Mercedes)\s+', 'Mercedes'),
        (r'^(VW|Volkswagen)\s+', 'VW'),
        (r'^(Seat)\s+', 'Seat'),
        (r'^(Skoda)\s+', 'Skoda'),
        (r'^(Ford)\s+', 'Ford'),
        (r'^(Porsche)\s+', 'Porsche'),
        (r'^(Mini)\s+', 'Mini'),
        (r'^(Infiniti)\s+', 'Infiniti'),
        (r'^(Mazda)\s+', 'Mazda'),
        (r'^(Ssangyong)\s+', 'Ssangyong'),
    ]

    for pattern, mfr in manufacturer_patterns:
        mfr_match = re.match(pattern, models_part, re.IGNORECASE)
        if mfr_match:
            manufacturer = mfr
            models_part = models_part[len(mfr_match.group(0)):].strip()
            break

    # Split models by comma
    models = [m.strip() for m in models_part.split(',') if m.strip()]

    if not models:
        return [task]

    # Group models to fit within max_length
    split_tasks = []
    current_models = []

    for model in models:
        # Calculate what the title would be with this model added
        if manufacturer:
            test_models_str = ', '.join(current_models + [model])
            test_title = f"{prefix}{manufacturer} {test_models_str}"
        else:
            test_models_str = ', '.join(current_models + [model])
            test_title = f"{prefix}{test_models_str}"

        if len(test_title) <= max_length or not current_models:
            # Can add this model, or it's the first model (must include at least one)
            current_models.append(model)
        else:
            # Current group is full, create a task and start a new group
            if manufacturer:
                new_title = f"{prefix}{manufacturer} {', '.join(current_models)}"
            else:
                new_title = f"{prefix}{', '.join(current_models)}"

            new_task = task.copy()
            new_task['Title'] = new_title
            split_tasks.append(new_task)

            # Start new group with current model
            current_models = [model]

    # Don't forget the last group
    if current_models:
        if manufacturer:
            new_title = f"{prefix}{manufacturer} {', '.join(current_models)}"
        else:
            new_title = f"{prefix}{', '.join(current_models)}"

        new_task = task.copy()
        new_task['Title'] = new_title
        split_tasks.append(new_task)

    return split_tasks if split_tasks else [task]


def process_tasks_with_title_splitting(tasks, max_title_length=80):
    """
    Process a list of tasks and split any tasks with titles exceeding max_title_length.

    Args:
        tasks: List of task dictionaries
        max_title_length: Maximum allowed title length (default: 80)

    Returns:
        list: List of tasks with long titles split into multiple tasks
    """
    processed_tasks = []

    for task in tasks:
        split_tasks = split_long_title_task(task, max_title_length)
        processed_tasks.extend(split_tasks)

    return processed_tasks


def parse_data_from_pdf_local(pdf_path, use_cache=True, move_after_processing=True):
    """
    Process a PDF using LOCAL parsing functions to extract and structure data.

    This function uses pdfplumber to extract text and tables, then processes
    them locally without relying on external AI APIs.

    Args:
        pdf_path: Path to the PDF file
        use_cache: Whether to check/use cached results (default: True)
        move_after_processing: Whether to move PDF to processed folder after extraction (default: True)

    Returns:
        list: List of dictionaries containing output data with keys:
            - Title: Generated title for the tire group
            - Model: Extracted model from PDF
            - Tyre_Width: Extracted tire width
            - Tyre_dia: Extracted tire diameter
            - holes: Number of holes from first table
            - pcd: PCD value from first table
            - centre_bore: Centre bore value from first table
            - offset: Offset value from first table
            - tire_size: Formatted tire size string
    """
    pdf_filename = os.path.basename(pdf_path)

    # Check cache first if enabled
    if use_cache:
        cached_data = get_cached_result(pdf_filename)
        if cached_data is not None:
            return cached_data

    # Step 1: Process PDF to extract text and tables
    all_text, first_table_data, merged_csv_path = process_pdf(pdf_path)

    # Step 2: Extract wheel model from text
    model = extract_model_from_text(all_text)

    # Step 3: Extract wheel size and tyre dimensions from text
    wheel_size_formatted, tyre_width, tyre_dia = extract_wheel_size_from_text(all_text)

    # Step 4: Extract wheel specifications from first table
    wheel_specs = extract_wheel_specs_from_first_table(first_table_data)

    output_data = []

    # Step 5: Process vehicle compatibility data if merged CSV exists
    if merged_csv_path and os.path.exists(merged_csv_path):
        try:
            # Get grouped data by manufacturer and tire size
            valid_groups = get_valid_tire_groups(merged_csv_path)

            for group in valid_groups:
                data_item = {
                    'Title': group['title'],
                    'Model': model,
                    'Tyre_Width': tyre_width,
                    'Tyre_dia': tyre_dia,
                    'holes': wheel_specs['holes'],
                    'pcd': wheel_specs['pcd'],
                    'centre_bore': wheel_specs['centre_bore'],
                    'offset': wheel_specs['offset'],
                    'tire_size': group['tire_size']
                }

                # Validate the extracted data
                is_valid, validation_errors = validate_extracted_data(data_item)
                if is_valid:
                    output_data.append(data_item)
                else:
                    print(f"Validation failed for group: {validation_errors}")

            # Clean up merged CSV after processing
            try:
                os.remove(merged_csv_path)
            except OSError:
                pass

        except Exception as e:
            print(f"Error processing merged CSV: {e}")

    # If no groups were created from CSV, create a single entry
    if not output_data:
        # Create a default entry with available data
        data_item = {
            'Title': f"{tyre_dia} Inch All-season Complete Wheels set" if tyre_dia else None,
            'Model': model,
            'Tyre_Width': tyre_width,
            'Tyre_dia': tyre_dia,
            'holes': wheel_specs['holes'],
            'pcd': wheel_specs['pcd'],
            'centre_bore': wheel_specs['centre_bore'],
            'offset': wheel_specs['offset'],
            'tire_size': None
        }

        # Validate and add if valid
        is_valid, validation_errors = validate_extracted_data(data_item)
        if is_valid:
            output_data.append(data_item)
        else:
            print(f"Default entry validation failed: {validation_errors}")
            # Add anyway but mark with validation issues
            data_item['_validation_errors'] = validation_errors
            output_data.append(data_item)

    # Step 6: Split tasks with long titles (>80 characters)
    output_data = process_tasks_with_title_splitting(output_data, max_title_length=80)

    # Cache the results
    if output_data:
        cache_result(pdf_filename, output_data, pdf_path)

        # Move PDF to processed folder after successful extraction
        if move_after_processing:
            move_to_processed(pdf_path)

    return output_data


def parse_data_from_pdf(pdf_path, use_cache=True, move_after_processing=True, use_ai=False):
    """
    Process a PDF to extract and structure data.

    This function can use either local parsing or AI-powered extraction.
    By default, it uses local parsing for faster and more reliable results.

    Args:
        pdf_path: Path to the PDF file
        use_cache: Whether to check/use cached results (default: True)
        move_after_processing: Whether to move PDF to processed folder after extraction (default: True)
        use_ai: Whether to use AI extraction instead of local parsing (default: False)

    Returns:
        list: List of dictionaries containing output data with keys:
            - Title: Generated title for the tire group
            - Model: Extracted model from PDF
            - Tyre_Width: Extracted tire width
            - Tyre_dia: Extracted tire diameter
            - holes: Number of holes from first table
            - pcd: PCD value from first table
            - centre_bore: Centre bore value from first table
            - offset: Offset value from first table
            - tire_size: Formatted tire size string
    """
    if use_ai:
        # Use AI-powered extraction
        return parse_data_from_pdf_ai(pdf_path, use_cache, move_after_processing)
    else:
        # Use local parsing (default)
        return parse_data_from_pdf_local(pdf_path, use_cache, move_after_processing)


def parse_data_from_pdf_ai(pdf_path, use_cache=True, move_after_processing=True):
    """
    Process a PDF using AI to extract and structure data.

    This function extracts raw text from the PDF and sends it to OpenAI API
    for intelligent parsing and structuring. It includes caching to avoid
    reprocessing the same document.

    Args:
        pdf_path: Path to the PDF file
        use_cache: Whether to check/use cached results (default: True)
        move_after_processing: Whether to move PDF to processed folder after extraction (default: True)

    Returns:
        list: List of dictionaries containing output data with keys:
            - Title: Generated title for the tire group
            - Model: Extracted model from PDF
            - Tyre_Width: Extracted tire width
            - Tyre_dia: Extracted tire diameter
            - holes: Number of holes from first table
            - pcd: PCD value from first table
            - centre_bore: Centre bore value from first table
            - offset: Offset value from first table
            - tire_size: Formatted tire size string
    """
    pdf_filename = os.path.basename(pdf_path)

    # Check cache first if enabled
    if use_cache:
        cached_data = get_cached_result(pdf_filename)
        if cached_data is not None:
            return cached_data

    # Extract raw text from PDF (including tables)
    pdf_text = extract_raw_text_from_pdf(pdf_path)

    # Use AI to extract and structure the data
    output_data = extract_data_with_ai(pdf_text)

    # Ensure all required keys exist and handle null values
    required_keys = ['Title', 'Model', 'Tyre_Width', 'Tyre_dia', 'holes',
                     'pcd', 'centre_bore', 'offset', 'tire_size']

    for item in output_data:
        for key in required_keys:
            if key not in item:
                item[key] = None

        # Validate the extracted data
        is_valid, validation_errors = validate_extracted_data(item)
        if not is_valid:
            print(f"AI extraction validation warning: {validation_errors}")

    # Split tasks with long titles (>80 characters)
    output_data = process_tasks_with_title_splitting(output_data, max_title_length=80)

    # Cache the results
    if output_data:
        cache_result(pdf_filename, output_data, pdf_path)

        # Move PDF to processed folder after successful extraction
        if move_after_processing:
            move_to_processed(pdf_path)

    return output_data

def create_xpath(value: str) -> str:
    return f"//option[text()= '{value}']/parent::select"

def format_tire_size(tire_string):
    return re.sub(r'(\d)([a-zA-Z])', r'\1 \2', tire_string)

def get_season(season: str) -> str:
    season = season.lower()
    if 'Sommerreifen' == season:
        return 'Summer'
    elif 'Winterreifen' == season:
        return 'Winter'
    elif 'Ganzjahresreifen' == season:
        return 'All-season'
    else:
        return 'Unknown'

def validate_task(task):
    required_fields = ['Title', 'Model', 'Tyre_Width', 'Tyre_dia', 'holes', 'pcd', 'centre_bore', 'offset', 'tire_size']
    missing_fields = []

    for field in required_fields:
        value = task.get(field)
        if value is None or value == '' or value == 'null':
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields

if __name__ == "__main__":
    file_path = r"D:\fiverr\Automation\pdf_to_website\documents\1-HA-B32-9.5x19-5x112-ET48-D3-66.6.pdf"

    # Test local parsing (default, no AI)
    print("=" * 50)
    print("Testing LOCAL parsing (no AI):")
    print("=" * 50)
    output_data = parse_data_from_pdf(file_path, use_cache=False, move_after_processing=False, use_ai=False)
    for item in output_data:
        print(json.dumps(item, indent=2, ensure_ascii=False))

    # Uncomment below to test AI parsing
    # print("\n" + "=" * 50)
    # print("Testing AI parsing:")
    # print("=" * 50)
    # output_data_ai = parse_data_from_pdf(file_path, use_cache=False, move_after_processing=False, use_ai=True)
    # for item in output_data_ai:
    #     print(json.dumps(item, indent=2, ensure_ascii=False))

