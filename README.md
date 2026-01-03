# PDF to Website Automation Tool

This automation tool extracts data from PDF documents (German ABE - Allgemeine Betriebserlaubnis / General Operating Permit) containing vehicle wheel and tire specifications, and automatically creates products on a web platform.

---

## 📋 Table of Contents

1. [What Does This Tool Do?](#what-does-this-tool-do)
2. [Requirements](#requirements)
3. [Installation Guide](#installation-guide)
4. [Project Structure](#project-structure)
5. [Configuration](#configuration)
6. [How to Use](#how-to-use)
7. [Understanding the Workflow](#understanding-the-workflow)
8. [Troubleshooting](#troubleshooting)
9. [Important Files Explained](#important-files-explained)

---

## 🎯 What Does This Tool Do?

This tool automates the following tasks:

1. **PDF Processing**: Reads PDF files containing wheel/tire specifications
2. **Data Extraction**: Uses local parsing functions to extract and structure data from PDFs (with optional AI fallback)
3. **Data Validation**: Validates extracted data to ensure quality (e.g., title must start with a number)
4. **Web Automation**: Automatically logs into a website and creates tire/wheel products
5. **Brand Matching**: Searches for matching premium and budget tire brands
6. **Product Creation**: Generates product listings with proper titles and specifications

### Parsing Methods

The tool supports two parsing methods:

| Method | Description | Speed | Cost |
|--------|-------------|-------|------|
| **Local Parsing** (Default) | Uses pdfplumber to extract text/tables, processes locally | Fast | Free |
| **AI Parsing** (Optional) | Uses OpenAI API for intelligent extraction | Slower | API costs |

By default, the tool uses **local parsing** which is faster and doesn't require API calls.

---

## 💻 Requirements

Before you start, make sure you have:

### Software Requirements

| Software | Version | Download Link |
|----------|---------|---------------|
| Python | 3.10 or higher | [Download Python](https://www.python.org/downloads/) |
| Google Chrome | Latest version | [Download Chrome](https://www.google.com/chrome/) |
| Git (Optional) | Latest version | [Download Git](https://git-scm.com/downloads) |

### Accounts Required

- **OpenAI API Account** (Optional): Only needed if using AI parsing. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
- **Website Login Credentials**: Username and password for the target website

---

## 🔧 Installation Guide

Follow these steps carefully:

### Step 1: Download and Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download Python 3.10 or higher
3. **IMPORTANT**: During installation, check the box that says **"Add Python to PATH"**
4. Click "Install Now"

### Step 2: Verify Python Installation

Open **Command Prompt** (Windows) or **Terminal** (Mac/Linux):

```bash
python --version
```

You should see something like: `Python 3.10.x`

### Step 3: Navigate to Project Folder

```bash
cd D:\fiverr\Automation\pdf_to_website
```

### Step 4: Create a Virtual Environment

A virtual environment keeps your project dependencies separate from other Python projects.

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Mac/Linux)
source venv/bin/activate
```

After activation, you should see `(venv)` at the beginning of your command line.

### Step 5: Install Required Packages

```bash
pip install python-dotenv selenium webdriver-manager pdfplumber pandas openai
```

This installs:
- `python-dotenv` - For reading configuration files
- `selenium` - For web browser automation
- `webdriver-manager` - For automatic Chrome driver management
- `pdfplumber` - For reading PDF files
- `pandas` - For data processing
- `openai` - For AI-powered data extraction

---

## 📁 Project Structure

```
pdf_to_website/
│
├── documents/                    # 📥 PUT YOUR PDF FILES HERE
│   └── (your PDF files)
│
├── processed_documents/          # 📤 PDFs move here after processing
│   └── (processed PDFs)
│
├── script/                       # 🔧 Main script folder
│   ├── main.py                   # Main automation script
│   ├── __init__.py
│   └── utils/
│       ├── functions.py          # PDF processing & AI functions
│       ├── utils.py              # Web automation utilities
│       └── __init__.py
│
├── .env                          # ⚙️ Configuration file (YOU NEED TO EDIT THIS)
├── ai_extraction_cache.json      # Cache for AI-extracted data
├── processed_tasks.json          # Log of processed tasks
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## ⚙️ Configuration

### Step 1: Create/Edit the `.env` File

The `.env` file stores your secret credentials. Create or edit this file in the project root folder:

**File location**: `D:\fiverr\Automation\pdf_to_website\.env`

**File contents**:
```env
# OpenAI API Key (Optional - only needed if using AI parsing)
# Get it from https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-api-key-here

# Website Login Credentials (Required)
LOGIN_USERNAME=your-email@example.com
LOGIN_PASSWORD=your-password-here
```

### Step 2: Get Your OpenAI API Key (Optional)

⚠️ **Note**: This step is only needed if you want to use AI parsing instead of local parsing.

By default, the tool uses **local parsing** which doesn't require an API key.

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Go to **API Keys** section
4. Click **"Create new secret key"**
5. Copy the key and paste it in your `.env` file

⚠️ **Important**: Keep your API key secret! Never share it publicly.

---

## 🚀 How to Use

### Step 1: Prepare Your PDF Files

1. Place your PDF files in the `documents/` folder
2. Make sure the PDFs are German ABE (wheel certification) documents

### Step 2: Activate Virtual Environment

Open Command Prompt and run:

```bash
cd D:\fiverr\Automation\pdf_to_website
venv\Scripts\activate
```

### Step 3: Run the Script

```bash
python -m script.main
```

### Step 4: Watch the Automation

- A Chrome browser window will open automatically
- The script will log in to the website
- It will process each PDF and create products
- Watch the terminal for progress messages

### Step 5: Check Results

After the script finishes:
- Processed PDFs are moved to `processed_documents/`
- Processing logs are saved to `processed_tasks.json`
- Check the website for created products

---

## 🔄 Understanding the Workflow

```
┌─────────────────┐
│  PDF Files in   │
│  /documents     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Local Parsing   │
│ Extracts Data   │
│ (or AI if set)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Validated │
│ (Title starts   │
│  with number)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Cached    │
│  (saved locally)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Browser Opens  │
│  & Logs In      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Search Rims    │
│  on Website     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Try Premium    │
│  Brands First   │
│  (CONTINENTAL,  │
│   GOODYEAR,     │
│   HANKOOK)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Try Budget     │
│  Brands Next    │
│  (ARIVO,        │
│   GOODRIDE,     │
│   WESTLAKE)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Create Product │
│  with AI Title  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Move PDF to    │
│  /processed     │
└─────────────────┘
```

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### ❌ "Python is not recognized"
**Solution**: Reinstall Python and make sure to check "Add Python to PATH"

#### ❌ "ModuleNotFoundError: No module named 'xxx'"
**Solution**: Install the missing package:
```bash
pip install package-name
```

#### ❌ "Chrome driver error"
**Solution**: The script automatically downloads the correct driver. Make sure you have internet connection and Chrome is installed.

#### ❌ "API rate limit exceeded (429 error)"
**Solution**: The script has built-in rate limiting. If you still see this error, wait a few minutes and try again.

#### ❌ "No valid tasks found"
**Solution**: 
1. Check that PDF files are in the `documents/` folder
2. Or check that `ai_extraction_cache.json` has cached data

#### ❌ "Login failed"
**Solution**: 
1. Check your `.env` file has correct credentials
2. Make sure the website is accessible

#### ❌ "Element not found"
**Solution**: The website might have changed. Check the log for which element is missing.

### Viewing Logs

The script prints detailed logs to the terminal. Look for:
- `INFO` - Normal progress messages
- `WARNING` - Non-critical issues
- `ERROR` - Problems that need attention

---

## 📚 Important Files Explained

### `.env` (Configuration)
Contains your secret credentials. **Never share this file!**

### `ai_extraction_cache.json` (Cache)
Stores extracted PDF data so you don't need to re-process the same PDFs.

**Structure**:
```json
{
  "filename.pdf": {
    "data": [...extracted tasks...],
    "processed_at": "2025-12-31T12:00:00",
    "source_path": "path/to/file"
  }
}
```

**Each task in the data array has this structure**:
```json
{
  "Title": "19 Inch All-season Complete Wheels set for Mercedes-Benz E63, E63S AMG T-Modell",
  "Model": "B32",
  "Tyre_Width": 9.5,
  "Tyre_dia": 19,
  "holes": "5",
  "pcd": "112",
  "centre_bore": "66.6",
  "offset": "48",
  "tire_size": "265/40R19"
}
```

**Data Validation Rules**:
- Title must start with a number (e.g., "19 Inch...")
- All required fields (Model, Tyre_Width, Tyre_dia, holes, pcd, centre_bore, offset, tire_size) must be present
- Invalid entries are logged but still included (with a `_validation_errors` field)
```

### `processed_tasks.json` (Processing Log)
Records what happened with each processed task.

**Structure**:
```json
{
  "filename.pdf": {
    "tasks": [
      {
        "task": {...task data...},
        "processed_at": "2025-12-31T12:00:00",
        "result": {
          "element_found": true,
          "premium_created": true,
          "cheap_created": false,
          "error": null
        }
      }
    ]
  }
}
```

---

## 📞 Support

If you encounter issues:

1. **Check this README** for common solutions
2. **Review the terminal logs** for error messages
3. **Verify your `.env` configuration** is correct
4. **Ensure PDFs are valid** German ABE documents

---

## 📝 Quick Reference Commands

```bash
# Navigate to project folder
cd D:\fiverr\Automation\pdf_to_website

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install python-dotenv selenium webdriver-manager pdfplumber pandas openai

# Run the script
python -m script.main

# Deactivate virtual environment when done
deactivate
```

---

**Last Updated**: January 2, 2026

