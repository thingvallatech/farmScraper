#!/usr/bin/env python3
"""
Test Setup Script
Verifies that all dependencies are installed correctly
"""
import sys
from pathlib import Path

def test_python_version():
    """Check Python version"""
    print("Testing Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✓ Python {version.major}.{version.minor}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor} (need 3.10+)")
        return False

def test_imports():
    """Test required imports"""
    packages = [
        ("playwright", "Playwright"),
        ("bs4", "BeautifulSoup4"),
        ("pdfplumber", "pdfplumber"),
        ("psycopg2", "psycopg2"),
        ("pandas", "pandas"),
        ("dotenv", "python-dotenv"),
        ("pydantic", "pydantic"),
        ("loguru", "loguru"),
        ("httpx", "httpx"),
    ]

    all_ok = True
    for module, name in packages:
        print(f"Testing {name}...", end=" ")
        try:
            __import__(module)
            print("✓")
        except ImportError:
            print("✗ NOT INSTALLED")
            all_ok = False

    return all_ok

def test_spacy():
    """Test Spacy and model"""
    print("Testing Spacy...", end=" ")
    try:
        import spacy
        print("✓")

        print("Testing Spacy model (en_core_web_sm)...", end=" ")
        try:
            nlp = spacy.load("en_core_web_sm")
            print("✓")
            return True
        except OSError:
            print("✗ Model not installed")
            print("  Run: python -m spacy download en_core_web_sm")
            return False
    except ImportError:
        print("✗ NOT INSTALLED")
        return False

def test_playwright_browsers():
    """Test Playwright browser installation"""
    print("Testing Playwright browsers...", end=" ")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("✓")
                return True
            except Exception as e:
                print("✗ Browsers not installed")
                print("  Run: playwright install chromium")
                return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_database():
    """Test database connection"""
    print("Testing database connection...", end=" ")
    try:
        from src.database.connection import db

        conn = db.connect()
        db.close()
        print("✓")
        return True
    except Exception as e:
        print(f"✗ Cannot connect: {e}")
        print("  Make sure PostgreSQL is running: docker-compose up -d postgres")
        return False

def test_configuration():
    """Test configuration"""
    print("Testing configuration...", end=" ")
    try:
        from src.config import settings

        if not settings.nass_api_key:
            print("⚠ NASS API key not set")
            return False

        print("✓")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_directories():
    """Test directory structure"""
    print("Testing directories...", end=" ")

    dirs = ["src", "data", "data/pdfs", "data/raw", "logs", "notebooks"]
    all_exist = True

    for d in dirs:
        if not Path(d).exists():
            print(f"✗ Missing: {d}")
            all_exist = False

    if all_exist:
        print("✓")

    return all_exist

def main():
    """Run all tests"""
    print("=" * 60)
    print("Farm Assist - Setup Verification")
    print("=" * 60)
    print()

    results = []

    # Run tests
    results.append(("Python Version", test_python_version()))
    results.append(("Package Imports", test_imports()))
    results.append(("Spacy NLP", test_spacy()))
    results.append(("Playwright Browsers", test_playwright_browsers()))
    results.append(("Directory Structure", test_directories()))
    results.append(("Configuration", test_configuration()))
    results.append(("Database Connection", test_database()))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:.<40} {status}")

    print()

    if all(r[1] for r in results):
        print("✓ All tests passed! You're ready to run the pipeline.")
        print()
        print("Run the pipeline with:")
        print("  ./run.sh          (macOS/Linux)")
        print("  run.bat           (Windows)")
        print("  python src/main.py")
        return 0
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        print()
        print("Common fixes:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
        print("  python -m spacy download en_core_web_sm")
        print("  docker-compose up -d postgres")
        return 1

if __name__ == "__main__":
    sys.exit(main())
