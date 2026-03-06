#!/bin/bash
#
# Fresh-R Selenium Auto-Setup Script for Home Assistant
# This script automatically installs Selenium and ChromeDriver after HA installation
#

set -e

echo "======================================================"
echo "Fresh-R Integration - Dependency Auto-Setup"
echo "======================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Detect OS
if [ -f /etc/debian_version ]; then
    OS="debian"
    print_status "Detected Debian/Ubuntu system"
elif [ -f /etc/alpine-release ]; then
    OS="alpine"
    print_status "Detected Alpine Linux (Home Assistant OS)"
else
    print_warning "Unknown OS, attempting generic installation"
    OS="generic"
fi

echo ""
echo "Step 1: Installing Google Chrome..."
echo "------------------------------------------------------"

if [ "$OS" = "debian" ]; then
    # Install dependencies
    apt-get update
    apt-get install -y wget gnupg
    
    # Install Chrome
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
    apt-get update
    apt-get install -y google-chrome-stable
    
    print_status "Google Chrome installed successfully"
    
elif [ "$OS" = "alpine" ]; then
    # For Alpine/Home Assistant OS
    apk add --no-cache chromium chromium-chromedriver
    print_status "Chromium and ChromeDriver installed via apk"
    
else
    print_warning "Attempting to install Chrome via snap..."
    snap install chromium
    print_status "Chromium installed via snap"
fi

echo ""
echo "Step 2: Installing Python dependencies..."
echo "------------------------------------------------------"

# Find Python installation (HA typically uses /usr/local/bin/python3 or /usr/bin/python3)
PYTHON_PATH=$(which python3 || which python)

if [ -z "$PYTHON_PATH" ]; then
    print_error "Python not found!"
    exit 1
fi

print_status "Using Python: $PYTHON_PATH"

# Install Selenium and webdriver-manager
$PYTHON_PATH -m pip install --upgrade pip
$PYTHON_PATH -m pip install selenium>=4.0.0 webdriver-manager>=4.0.0 aiohttp>=3.8.0

print_status "Python packages installed successfully"

echo ""
echo "Step 3: Verifying installation..."
echo "------------------------------------------------------"

# Test Chrome installation
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    print_status "Chrome found: $CHROME_VERSION"
elif command -v chromium &> /dev/null; then
    CHROME_VERSION=$(chromium --version)
    print_status "Chromium found: $CHROME_VERSION"
else
    print_warning "Chrome/Chromium not found in PATH"
fi

# Test Python packages
$PYTHON_PATH -c "import selenium; print(f'Selenium version: {selenium.__version__}')" && print_status "Selenium imported successfully"
$PYTHON_PATH -c "import webdriver_manager; print('WebDriver Manager available')" && print_status "WebDriver Manager imported successfully"
$PYTHON_PATH -c "import aiohttp; print(f'aiohttp version: {aiohttp.__version__}')" && print_status "aiohttp imported successfully"

echo ""
echo "Step 4: Setting up Chrome for headless operation..."
echo "------------------------------------------------------"

# Create Chrome wrapper script for headless mode
mkdir -p /usr/local/bin
cat > /usr/local/bin/chrome-headless << 'EOF'
#!/bin/bash
# Chrome headless wrapper for Fresh-R integration
exec google-chrome --headless --no-sandbox --disable-dev-shm-usage "$@"
EOF
chmod +x /usr/local/bin/chrome-headless
print_status "Headless Chrome wrapper created"

# Create systemd service for auto-refresh (optional)
if command -v systemctl &> /dev/null; then
    echo ""
    echo "Step 5: Creating systemd service for monitoring..."
    echo "------------------------------------------------------"
    
    cat > /etc/systemd/system/fresh-r-deps.service << EOF
[Unit]
Description=Fresh-R Integration Dependencies Check
After=homeassistant.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fresh-r-setup check
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    print_status "Systemd service created (not enabled by default)"
fi

echo ""
echo "======================================================"
echo "INSTALLATION COMPLETE!"
echo "======================================================"
echo ""
echo "Summary:"
echo "  ✓ Google Chrome/Chromium installed"
echo "  ✓ Selenium Python package installed"
echo "  ✓ WebDriver Manager installed"
echo "  ✓ aiohttp installed"
echo "  ✓ Headless Chrome wrapper created"
echo ""
echo "What Selenium and ChromeDriver do:"
echo "  • Selenium: Browser automation library"
echo "  • ChromeDriver: Controls Chrome browser programmatically"
echo "  • Together: Automatically login to fresh-r.me and extract session token"
echo ""
echo "The integration will:"
echo "  1. Launch Chrome in headless mode (no GUI)"
echo "  2. Navigate to fresh-r.me/login"
echo "  3. Fill in your email and password"
echo "  4. Submit the login form"
echo "  5. Wait for redirect to dashboard"
echo "  6. Extract the session token from cookies"
echo "  7. Use the token for API calls"
echo "  8. Refresh the token every 50 minutes"
echo ""
echo "To enable auto-start with HA:"
echo "  sudo systemctl enable fresh-r-deps.service"
echo ""
echo "To test the installation:"
echo "  python3 -c 'from selenium import webdriver; print(\"OK\")'"
echo ""
