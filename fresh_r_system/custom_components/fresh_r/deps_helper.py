"""
Dependency Setup Helper for Fresh-R Integration

This module helps with automatic dependency installation.
"""
import logging
import subprocess
import shutil
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

async def check_and_setup_dependencies(hass) -> tuple[bool, str]:
    """
    Check if all dependencies are available and attempt to set up if not.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    issues = []
    
    # 1. Check Python packages (these should be auto-installed by HA)
    try:
        import selenium
        _LOGGER.debug("✅ Selenium is available")
    except ImportError:
        issues.append("Python package 'selenium' not found (should auto-install)")
    
    try:
        import webdriver_manager
        _LOGGER.debug("✅ webdriver-manager is available")
    except ImportError:
        issues.append("Python package 'webdriver-manager' not found (should auto-install)")
    
    # 2. Check Chrome/Chromium (system dependency)
    chrome_path = find_chrome_executable()
    
    if chrome_path:
        _LOGGER.info(f"✅ Chrome/Chromium found at: {chrome_path}")
        return True, f"All dependencies available. Chrome: {chrome_path}"
    else:
        _LOGGER.warning("❌ Chrome/Chromium not found")
        
        # Try to auto-install for supported systems
        if hass:
            system = hass.config.components
            
            # Check OS type
            if os.path.exists("/etc/alpine-release"):
                # Alpine / HA OS
                issues.append(
                    "Chrome not found. For HA OS, install via Terminal add-on:\n"
                    "apk add --no-cache chromium chromium-chromedriver"
                )
            elif os.path.exists("/etc/debian_version"):
                # Debian/Ubuntu
                issues.append(
                    "Chrome not found. Install via SSH:\n"
                    "sudo apt-get update && sudo apt-get install -y chromium-browser"
                )
            elif os.name == "nt":
                # Windows
                issues.append(
                    "Chrome not found. Please install from https://www.google.com/chrome/"
                )
            else:
                issues.append(
                    "Chrome/Chromium not found. Please install Chrome or run setup_selenium.sh"
                )
        else:
            issues.append("Chrome/Chromium not found. Please run setup_selenium.sh")
    
    if issues:
        return False, "\n".join(issues)
    
    return True, "All dependencies available"


def find_chrome_executable() -> str | None:
    """
    Find Chrome or Chromium executable on the system.
    Returns the path if found, None otherwise.
    """
    # Common Chrome/Chromium paths
    possible_paths = [
        # Linux - Chrome
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chrome",
        "/opt/google/chrome/chrome",
        "/opt/google/chrome/google-chrome",
        
        # Linux - Chromium
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/lib/chromium/chrome",
        
        # Alpine / HA OS
        "/usr/bin/chromium",
        "/usr/lib/chromium/chromium-launcher.sh",
        
        # Mac
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        
        # Windows
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Users\\%USERNAME%\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe",
    ]
    
    # Check standard paths
    for path in possible_paths:
        expanded_path = os.path.expandvars(path)
        if os.path.isfile(expanded_path) and os.access(expanded_path, os.X_OK):
            return expanded_path
    
    # Check if in PATH
    chrome_names = ["google-chrome", "google-chrome-stable", "chrome", "chromium", "chromium-browser"]
    for name in chrome_names:
        chrome_path = shutil.which(name)
        if chrome_path:
            return chrome_path
    
    return None


def get_chrome_version(chrome_path: str) -> str | None:
    """Get Chrome version string."""
    try:
        result = subprocess.run(
            [chrome_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        _LOGGER.warning(f"Could not get Chrome version: {e}")
    return None


def setup_chrome_environment():
    """
    Set environment variables for Chrome/ChromeDriver.
    This helps webdriver-manager find the right binaries.
    """
    chrome_path = find_chrome_executable()
    
    if chrome_path:
        # Set environment variable for webdriver-manager
        os.environ["CHROME_BIN"] = chrome_path
        _LOGGER.debug(f"Set CHROME_BIN={chrome_path}")
        
        # For Alpine/HA OS, set additional options
        if os.path.exists("/etc/alpine-release"):
            os.environ["CHROMIUM_PATH"] = chrome_path
            _LOGGER.debug("Detected Alpine Linux, set CHROMIUM_PATH")
    
    return chrome_path
