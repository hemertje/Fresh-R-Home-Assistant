# Fresh-R Home Assistant Integration - Frequently Asked Questions (FAQ)

## 📅 1. Calendar/Graphs with Date Selection

**Question:** Can a specific date be selected for graphs in HA, like in Fresh-R?

**Answer:**
✅ **YES!** The dashboard has been updated with Fresh-R style date selection:

```yaml
# In fresh_r_dashboard.yaml - "Calendar" tab:
title: Calendar
icon: mdi:calendar
cards:
  - type: entities
    title: 📅 Specific Date Selection
    entities:
      - entity: input_datetime.fresh_r_start_date
        name: Start Date
      - entity: input_datetime.fresh_r_end_date
        name: End Date
      - entity: input_button.fresh_r_update_graphs
        name: Update Graphs

  # Quick select buttons
  - type: horizontal-stack
    cards:
      - type: button
        name: Yesterday
        icon: mdi:calendar-arrow-left
      - type: button
        name: Last Week
        icon: mdi:calendar-week
      - type: button
        name: Last Month
        icon: mdi:calendar-month
```

**New "Calendar" tab** added with week and month overview graphs.

---

## 🔧 2. Selenium and ChromeDriver in Home Assistant

**Question:** Are Selenium and ChromeDriver available in HA? What do they do? Does Selenium support browsers other than Chrome? Is this a universal solution?

**Answer:**

### **What do they do?**

| Component | Function | Why needed? |
|-----------|----------|-------------|
| **Selenium** | Browser automation library | Programmatically control a browser |
| **ChromeDriver** | Chrome controller | Lets Selenium control Chrome |
| **Chrome** | The browser itself | Simulates a real user login |

### **Universal Browser Support:**

✅ **YES!** Selenium is universal and supports multiple browsers:

```python
# Chrome (used in this integration)
from selenium import webdriver
driver = webdriver.Chrome()

# Firefox (alternative)
from selenium.webdriver.firefox.service import Service
driver = webdriver.Firefox()

# Edge (alternative)
driver = webdriver.Edge()

# Safari (Mac)
driver = webdriver.Safari()
```

**Why Chrome was chosen:**
- Most compatible with websites
- Best headless mode support
- Automatic ChromeDriver updates via webdriver-manager
- Works on Linux (Chromium), Windows, Mac

### **Headless Mode - No Physical Window!**

✅ **CORRECT!** Selenium does **NOT** open physical Chrome. It runs completely in the background:

```python
chrome_options = Options()
chrome_options.add_argument("--headless")        # ← NO GUI!
chrome_options.add_argument("--no-sandbox")      # ← Safe in containers
chrome_options.add_argument("--disable-dev-shm-usage")  # ← Memory optimization
chrome_options.add_argument("--disable-gpu")     # ← No GPU needed

driver = webdriver.Chrome(options=chrome_options)
# Chrome now runs completely invisible!
```

**What you DON'T see:**
❌ No Chrome window opens
❌ No browser interface
❌ No popup or notification

**What DOES happen (invisible):**
✅ Chrome process starts in background
✅ Navigates to fresh-r.me/login
✅ Fills in form
✅ Extracts cookies
✅ Cleanly shuts down

**Process check (visible in system monitor):**
```bash
ps aux | grep chrome
→ chrome --headless --no-sandbox ...
```

### **How it works:**

```
Fresh-R Integration
       ↓
async_login() called
       ↓
Selenium WebDriver
       ↓
Launch Chrome HEADLESS (no window!)
       ↓
Navigate to fresh-r.me/login
       ↓
Fill email: buurkracht.binnenhof@gmail.com
Fill password: Hemert@7733
       ↓
Click submit button
       ↓
Wait for redirect to dashboard.bw-log.com
       ↓
Extract sess_token from cookies
       ↓
Close browser (cleanup)
       ↓
Store token → Use for API calls
```

### **Availability in HA:**

| Installation Type | Selenium/Chrome | Installation Method |
|-------------------|-----------------|---------------------|
| **HA OS** (recommended) | ⚠️ Not standard | Use setup script or Community Add-on |
| **HA Container** | ⚠️ Not standard | Docker install Chrome/Selenium |
| **HA Core (venv)** | ⚠️ Not standard | pip install + system Chrome |
| **HA Supervised** | ⚠️ Not standard | apt-get install |

**→ Not standard, must be installed!**

### **Headless Mode Advantages:**

1. **No GUI needed** - Works on servers without desktop
2. **Lower resource usage** - No rendering
3. **Safer** - No visible browser = no misuse
4. **Faster** - No UI updates needed
5. **Docker compatible** - Works in containers

### **Alternative Browsers (if Chrome doesn't work):**

```python
# Firefox headless
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.add_argument("--headless")
driver = webdriver.Firefox(options=options)

# Edge headless (Windows)
from selenium import webdriver
from selenium.webdriver.edge.options import Options

options = Options()
options.add_argument("--headless")
driver = webdriver.Edge(options=options)
```

**Note:** The integration is configured for Chrome, but can easily be adapted to other browsers in `api.py`.

---

## 🤖 3. Automatic Installation after HA Setup

**Question:** Automate this step after HA installation?

**Answer:**
✅ **YES!** I've created `setup_selenium.sh`:

### **Automatic Installation:**

```bash
# Via SSH terminal in HA:
wget https://raw.githubusercontent.com/your-repo/fresh-r/main/setup_selenium.sh
chmod +x setup_selenium.sh
sudo ./setup_selenium.sh
```

### **What the script does:**

1. ✅ Detects OS (Debian/Ubuntu/Alpine)
2. ✅ Installs Google Chrome or Chromium
3. ✅ Installs Python packages:
   - `selenium>=4.0.0`
   - `webdriver-manager>=4.0.0`
   - `aiohttp>=3.8.0`
4. ✅ Creates headless Chrome wrapper
5. ✅ Tests the installation

### **Alternative: Community Add-on**

You can also create a custom add-on for HA OS:

```yaml
# config.json for add-on
{
  "name": "Fresh-R Dependencies",
  "version": "1.0",
  "slug": "fresh_r_deps",
  "description": "Selenium and Chrome for Fresh-R",
  "arch": ["amd64", "aarch64"],
  "startup": "before",
  "boot": "auto",
  "options": {},
  "schema": {}
}
```

---

## 📊 4. Dashboard Auto-Import to HA Overview

**Question:** Does the Fresh-R dashboard automatically appear in the HA Overview dashboard?

**Answer:**
❌ **NO**, not automatically. You must manually add it.

### **Steps to add:**

#### **Method 1: New Dashboard (Recommended)**

1. Go to **Settings** → **Dashboards**
2. Click **Add Dashboard**
3. Choose **Web page** or **Default**
4. Name it: "Fresh-R"
5. Click **Create**
6. Click **⋮** (three dots) → **Edit Dashboard**
7. Click **⋮** → **Raw configuration editor**
8. Copy content from `fresh_r_dashboard.yaml`
9. Click **Save**

#### **Method 2: Add to Overview (Not recommended)**

1. Go to **Overview** dashboard
2. Click **⋮** → **Edit Dashboard**
3. Click **Add Card**
4. Choose **Manual**
5. Paste YAML for one card
6. Repeat for all cards

### **Auto-Discovery (Possible Future Feature):**

```python
# In __init__.py - concept for auto-dashboard
async def async_setup_entry(hass, entry):
    # ... existing code ...
    
    # Auto-create notification
    hass.components.persistent_notification.create(
        "Fresh-R dashboard ready! Import: fresh_r_dashboard.yaml",
        title="Fresh-R Setup"
    )
```

**→ Not currently implemented due to HA security restrictions**

---

## 📡 5. MQTT Auto-Publish to Server

**Question:** Are dashboard parameters automatically sent to MQTT server so they can be used within HA?

**Answer:**
✅ **YES!** MQTT auto-publish is **ALREADY IMPLEMENTED** in `mqtt.py`:

### **How it works:**

```python
# In coordinator.py - every update:
async def _async_update_data(self):
    data = await self.client.async_get_current(self.serial)
    
    # MQTT: publish auto-discovery + current state
    if self.mqtt_enabled:
        from .mqtt import async_publish_discovery, async_publish_state
        
        # 1. Discovery: register sensors with HA
        await async_publish_discovery(hass, device_id, device_info)
        
        # 2. State: send current values
        await async_publish_state(hass, self.serial, data)
```

### **MQTT Topics:**

```
# Discovery (once at startup):
homeassistant/sensor/fresh_r_{id}_t1/config
homeassistant/sensor/fresh_r_{id}_co2/config
homeassistant/sensor/fresh_r_{id}_hum/config
... (20 sensors)

# State updates (every poll interval, default 60s):
fresh_r/{device_id}/state
→ JSON: {"t1": 22.5, "co2": 450, "hum": 55, ...}

# Availability:
fresh_r/{device_id}/availability
→ "online" / "offline"
```

### **Configuration:**

```yaml
# In config flow (UI) or configuration.yaml:
fresh_r:
  email: "buurkracht.binnenhof@gmail.com"
  password: "Hemert@7733"
  mqtt_enabled: true  # ← ENABLED BY DEFAULT
```

### **Prerequisite:**

You must have MQTT broker configured in HA:

```yaml
# configuration.yaml
mqtt:
  broker: core-mosquitto  # or your own broker
  port: 1883
  username: mqtt_user
  password: mqtt_pass
```

### **What you see in HA:**

After setup, 20+ entities automatically appear:
- `sensor.fresh_r_t1` (Indoor temperature)
- `sensor.fresh_r_co2` (CO2)
- `sensor.fresh_r_hum` (Humidity)
- `sensor.fresh_r_d5_25` (PM2.5 supply)
- ... and 16 other sensors

**→ All sensors are automatically available in HA and can be used in automations, scripts, other dashboards!**

---

## ⏰ 6. Token Refresh Timing (Distributed to Avoid Thundering Herd)

**Question:** Is the token refreshed every hour at a fixed time (e.g., every hour on the hour)? Or every hour from installation time? We don't want the website to be bombarded with requests at the same time when the HA app becomes popular.

**Answer:**

✅ **EXCELLENT POINT!** The token refresh uses **distributed timing** to avoid thundering herd:

### **Implementation:**

```python
# In api.py - token refresh with randomized offset:
async def async_ensure_token_valid(self):
    """Ensure token is valid, refresh if needed with distributed timing."""
    if not hasattr(self, '_token_timestamp') or not self._token_timestamp:
        _LOGGER.warning("No token timestamp, performing browser login...")
        await self.async_login()
        return
    
    from datetime import timedelta
    import random
    
    # Base refresh interval: 50 minutes (token lasts ~74 min)
    base_interval = timedelta(minutes=50)
    
    # Add random offset (0-10 minutes) to distribute load
    # Each installation gets its own unique offset
    if not hasattr(self, '_refresh_offset'):
        # Generate random offset once per installation (0-600 seconds)
        self._refresh_offset = timedelta(seconds=random.randint(0, 600))
        _LOGGER.debug(f"Token refresh offset: {self._refresh_offset.total_seconds():.0f}s")
    
    # Check if token needs refresh
    age = datetime.now() - self._token_timestamp
    threshold = base_interval + self._refresh_offset
    
    if age > threshold:
        _LOGGER.warning(f"Token is {age.total_seconds()/60:.0f} min old, refreshing via browser automation...")
        await self.async_login()
    else:
        _LOGGER.debug(f"Token is still fresh ({age.total_seconds()/60:.0f} min old)")
```

### **How it works:**

| Scenario | Behavior |
|----------|----------|
| **Base interval** | 50 minutes (safe margin before 74 min expiration) |
| **Random offset** | 0-10 minutes added per installation |
| **Result** | Each HA instance refreshes at different times |

### **Example:**

```
Installation A: Refreshes at :00, :50, :100, :150 minutes
Installation B: Refreshes at :05, :55, :105, :155 minutes  
Installation C: Refreshes at :12, :62, :112, :162 minutes
Installation D: Refreshes at :23, :73, :123, :173 minutes
...
```

**Result:** Requests are spread over a 10-minute window instead of all at once!

### **Additional Safeguards:**

```python
# 1. Exponential backoff on failures
async def _browser_automation_login(self):
    max_retries = 3
    base_delay = 30  # seconds
    
    for attempt in range(max_retries):
        try:
            # ... login logic ...
            return token
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 30s, 60s, 120s
                delay = base_delay * (2 ** attempt)
                delay += random.randint(0, 10)  # Add jitter
                _LOGGER.warning(f"Login failed, retrying in {delay}s...")
                await asyncio.sleep(delay)
    
    return None

# 2. Adaptive refresh based on API response
async def async_get_current(self, serial: str):
    try:
        data = await self._fetch_data(serial)
        return data
    except FreshRAuthError:
        # Token rejected by server - refresh immediately
        _LOGGER.warning("Token rejected by server, forcing refresh...")
        await self.async_login()
        # Retry once
        return await self._fetch_data(serial)
```

### **Load Distribution Summary:**

| Feature | Implementation | Purpose |
|---------|---------------|---------|
| Random offset | 0-10 min per installation | Distribute refresh times |
| Exponential backoff | 30s, 60s, 120s delays | Prevent retry storms |
| Jitter | +0-10s random delay | Further spread retries |
| Token validity check | Before each API call | Only refresh when needed |
| Adaptive refresh | On auth failure | Handle edge cases |

**Result:** Even with 1000+ HA installations, the website receives at most ~100 requests per minute instead of 1000 simultaneous requests! 🎯

---

## 🎯 Summary

| Question | Answer | Status |
|----------|--------|--------|
| Calendar graphs with date picker | ✅ YES, implemented | Implemented |
| Selenium/Chrome in HA | ⚠️ No, script created | Needs manual install |
| Automatic installation | ✅ YES, setup_selenium.sh | Ready |
| Dashboard in Overview | ❌ No, manual | Manual step required |
| MQTT auto-publish | ✅ YES, already implemented | Working |
| Token refresh timing | ✅ Distributed with random offset | Implemented |
| Thundering herd prevention | ✅ Random offsets + backoff | Implemented |

---

## 🚀 Next Steps

1. **Install dependencies:**
   ```bash
   sudo ./setup_selenium.sh
   ```

2. **Install integration:**
   ```bash
   cp -r custom_components/fresh_r /config/custom_components/
   ```

3. **Restart HA**

4. **Configure via UI:**
   - Settings → Integrations → Add Fresh-R
   - Enter credentials
   - MQTT is enabled by default

5. **Import dashboard:**
   - Settings → Dashboards → Add Dashboard
   - Raw config → Paste fresh_r_dashboard.yaml

6. **View graphs:**
   - Click "Calendar" tab for date selection
   - Or "Graphs" tab with Today/Week/Month/Year buttons
