#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Constants module for the Multi-Chamber Test application.

This module contains all global constants used throughout the application,
including GPIO pin mappings, file paths, color definitions, and role definitions.
"""

import os

# =============================================================================
# File Paths
# =============================================================================
# Base directory is user's desktop for common access
BASE_DIR = os.path.expanduser("~/Desktop")
SETTINGS_FILE = os.path.join(BASE_DIR, "techmac_settings.csv")
REFERENCE_DB = os.path.join(BASE_DIR, "techmac_references.db")
PASSWORD_FILE = os.path.join(BASE_DIR, "techmac_password.txt")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
RESULTS_DIR = os.path.join(BASE_DIR, "test_results")

# =============================================================================
# GPIO Pin Definitions
# =============================================================================
# Pin assignments follow BCM numbering scheme
GPIO_PINS = {
    # Chamber control solenoids
    "INLET_PINS": [4, 24, 23],        # Inlet valve pins for chambers 1-3
    "OUTLET_PINS": [27, 17, 22],      # Outlet valve pins for chambers 1-3
    "EMPTY_TANK_PINS": [27, 17, 22],  # Empty tank pins for chambers 1-3 (same as outlet pins)
    
    # Optional physical controls (not in original code but useful for physical interface)
    "START_BTN": 5,                   # Physical start button
    "STOP_BTN": 6,                    # Physical stop button
    "STATUS_LED_GREEN": 12,           # Status LED - Green
    "STATUS_LED_RED": 13,             # Status LED - Red
    "STATUS_LED_YELLOW": 16,          # Status LED - Yellow
}

# ADC Configuration
ADC_ADDRESS = 0x48
ADC_BUS_NUM = 1

# =============================================================================
# Control Parameters
# =============================================================================
# Pressure and control constants
PRESSURE_DEFAULTS = {
    "TARGET": 160,          # Default target pressure in mbar
    "THRESHOLD": 150,         # Default minimum pressure threshold in mbar
    "TOLERANCE": 5,         # Default acceptable pressure variation in mbar
    "UNIT": "mbar",         # Pressure unit
    "MAX_PRESSURE": 250,    # Maximum allowable pressure in mbar
}

# Test durations
TIME_DEFAULTS = {
    "TEST_DURATION": 90,    # Default test duration in seconds
    "STABILIZATION_TIME": 25, # Default stabilization time in seconds
    "EMPTY_TIME": 10,       # Default emptying time in seconds
}

# PID Controller Parameters
PID_PARAMS = {
    "KP": 0.3,              # Proportional gain
    "KI": 0.05,             # Integral gain
    "KD": 0.02,             # Derivative gain
    "MIN_VALVE_TIME": 0.6,  # Minimum time between valve switches
}

# ADC to Pressure Conversion
ADC_CONVERSION = {
    "VOLTAGE_OFFSET": -0.579,  # Default voltage offset for ADC readings
    "VOLTAGE_MULTIPLIER": 1.286,  # Default multiplier for voltage to pressure conversion
}

# =============================================================================
# User Interface Constants
# =============================================================================
# Color scheme based on interface.py
UI_COLORS = {
    "PRIMARY": "#00A7E1",       # Primary blue color
    "SECONDARY": "#FFFFFF",     # Secondary color (white)
    "BACKGROUND": "#FFFFFF",    # Background color (white)
    "TEXT_PRIMARY": "#1E293B",  # Primary text color (dark)
    "TEXT_SECONDARY": "#64748b", # Secondary text color
    "BORDER": "#E2E8F0",        # Border color
    "GAUGE": "#1E293B",         # Gauge color
    "SUCCESS": "#4CAF50",       # Success color (green)
    "WARNING": "#FFA500",       # Warning color (orange/amber)
    "ERROR": "#F44336",         # Error color (red)
    "BUTTON_HOVER": "#F8FAFC",  # Button hover color
    "STATUS_BG": "#e0f2f7",     # Status background color
}

# Sizes and dimensions
UI_DIMENSIONS = {
    "WINDOW_WIDTH": 1920,       # Full HD width
    "WINDOW_HEIGHT": 1080,      # Full HD height
    "GAUGE_SIZE": 250,          # Larger gauge size for better visibility
    "TIMELINE_HEIGHT": 90,      # Taller timeline
    "BUTTON_WIDTH": 20,         # Wider buttons
    "BUTTON_HEIGHT": 2,         # Standard button height
}

# Font configurations
UI_FONTS = {
    "HEADER": ("Helvetica", 24, "bold"),
    "SUBHEADER": ("Helvetica", 20, "bold"),
    "LABEL": ("Helvetica", 16, "normal"),
    "BUTTON": ("Helvetica", 18, "normal"),
    "VALUE": ("Helvetica", 20, "bold"),
    "GAUGE_VALUE": ("Helvetica", 24, "bold"),
    "GAUGE_UNIT": ("Helvetica", 14, "normal"),
}

# =============================================================================
# Test State Definitions
# =============================================================================
# Test state descriptions for UI display
# Note: For ERROR state, this is just a template - actual error messages 
# will be generated dynamically with specific error details
TEST_STATES = {
    "IDLE": "System Ready",
    "FILLING": "Filling Tank...",
    "STABILIZING": "Stabilizing Pressure...",
    "TESTING": "Test in Progress...",
    "EMPTYING": "Emptying Tank...",
    "COMPLETE": "Test Complete",
    "ERROR": "Error: {message}",  # Template for error messages - will be formatted with specifics
    "REGULATING": "Regulating Pressure...",
    "STOPPED": "Test Stopped",
}

# =============================================================================
# Access Control and Security
# =============================================================================
# User role definitions
USER_ROLES = {
    "OPERATOR": {
        "level": 1,
        "default_password": "5673",
        "permissions": ["run_test",]
    },
    "MAINTENANCE": {
        "level": 2,
        "default_password": "5678",
        "permissions": ["run_test", "view_history", "edit_settings", "calibrate"]
    },
    "ADMIN": {
        "level": 3,
        "default_password": "9012",
        "permissions": ["run_test", "view_history", "edit_settings", "calibrate", "manage_users"]
    }
}


PERMISSIONS = {
    "run_test": "Ability to start and monitor tests",
    "view_history": "Ability to view test history and results",
    "edit_settings": "Ability to modify system settings",
    "calibrate": "Ability to perform system calibration",
    "manage_users": "Ability to manage user accounts"
}
# Default admin password
DEFAULT_PASSWORD = "9012"

# =============================================================================
# Printer Configuration
# =============================================================================
# Zebra printer USB configuration
PRINTER_CONFIG = {
    "VENDOR_ID": 0x1ff2,
    "PRODUCT_ID": 0x0001,
    "TEAR_OFFSET": 120,  # Default tear-off position adjustment
}

# =============================================================================
# Calibration Settings
# =============================================================================
# Calibration points for pressure sensors
CALIBRATION_POINTS = [0, 300, 600]  # Default calibration points in mbar
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Constants module for the Multi-Chamber Test application.

This module contains all global constants used throughout the application,
including GPIO pin mappings, file paths, color definitions, and role definitions.
"""

import os

# =============================================================================
# File Paths
# =============================================================================
# Base directory is user's desktop for common access
BASE_DIR = os.path.expanduser("~/Desktop")
SETTINGS_FILE = os.path.join(BASE_DIR, "techmac_settings.csv")
REFERENCE_DB = os.path.join(BASE_DIR, "techmac_references.db")
PASSWORD_FILE = os.path.join(BASE_DIR, "techmac_password.txt")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
RESULTS_DIR = os.path.join(BASE_DIR, "test_results")

# =============================================================================
# GPIO Pin Definitions
# =============================================================================
# Pin assignments follow BCM numbering scheme
GPIO_PINS = {
    # Chamber control solenoids
    "INLET_PINS": [4, 24, 23],        # Inlet valve pins for chambers 1-3
    "OUTLET_PINS": [27, 17, 22],      # Outlet valve pins for chambers 1-3
    "EMPTY_TANK_PINS": [27, 17, 22],  # Empty tank pins for chambers 1-3 (same as outlet pins)
    
    # Optional physical controls (not in original code but useful for physical interface)
    "START_BTN": 5,                   # Physical start button
    "STOP_BTN": 6,                    # Physical stop button
    "STATUS_LED_GREEN": 12,           # Status LED - Green
    "STATUS_LED_RED": 13,             # Status LED - Red
    "STATUS_LED_YELLOW": 16,          # Status LED - Yellow
}

# ADC Configuration
ADC_ADDRESS = 0x48
ADC_BUS_NUM = 1

# =============================================================================
# Control Parameters
# =============================================================================
# Pressure and control constants
PRESSURE_DEFAULTS = {
    "TARGET": 150,          # Default target pressure in mbar
    "THRESHOLD": 5,         # Default minimum pressure threshold in mbar
    "TOLERANCE": 2,         # Default acceptable pressure variation in mbar
    "UNIT": "mbar",         # Pressure unit
    "MAX_PRESSURE": 600,    # Maximum allowable pressure in mbar
}

# Test durations
TIME_DEFAULTS = {
    "TEST_DURATION": 90,    # Default test duration in seconds
    "STABILIZATION_TIME": 25, # Default stabilization time in seconds
    "EMPTY_TIME": 10,       # Default emptying time in seconds
}

# PID Controller Parameters
PID_PARAMS = {
    "KP": 0.3,              # Proportional gain
    "KI": 0.05,             # Integral gain
    "KD": 0.02,             # Derivative gain
    "MIN_VALVE_TIME": 0.6,  # Minimum time between valve switches
}

# ADC to Pressure Conversion
ADC_CONVERSION = {
    "VOLTAGE_OFFSET": -0.579,  # Default voltage offset for ADC readings
    "VOLTAGE_MULTIPLIER": 1.286,  # Default multiplier for voltage to pressure conversion
}

# =============================================================================
# User Interface Constants
# =============================================================================
# Color scheme based on interface.py
UI_COLORS = {
    "PRIMARY": "#00A7E1",       # Primary blue color
    "SECONDARY": "#FFFFFF",     # Secondary color (white)
    "BACKGROUND": "#FFFFFF",    # Background color (white)
    "TEXT_PRIMARY": "#1E293B",  # Primary text color (dark)
    "TEXT_SECONDARY": "#64748b", # Secondary text color
    "BORDER": "#E2E8F0",        # Border color
    "GAUGE": "#1E293B",         # Gauge color
    "SUCCESS": "#4CAF50",       # Success color (green)
    "WARNING": "#FFA500",       # Warning color (orange/amber)
    "ERROR": "#F44336",         # Error color (red)
    "BUTTON_HOVER": "#F8FAFC",  # Button hover color
    "STATUS_BG": "#e0f2f7",     # Status background color
}

# Sizes and dimensions
UI_DIMENSIONS = {
    "WINDOW_WIDTH": 1920,       # Full HD width
    "WINDOW_HEIGHT": 1080,      # Full HD height
    "GAUGE_SIZE": 250,          # Larger gauge size for better visibility
    "TIMELINE_HEIGHT": 90,      # Taller timeline
    "BUTTON_WIDTH": 20,         # Wider buttons
    "BUTTON_HEIGHT": 2,         # Standard button height
}

# Font configurations
UI_FONTS = {
    "HEADER": ("Helvetica", 24, "bold"),
    "SUBHEADER": ("Helvetica", 20, "bold"),
    "LABEL": ("Helvetica", 16, "normal"),
    "BUTTON": ("Helvetica", 18, "normal"),
    "VALUE": ("Helvetica", 20, "bold"),
    "GAUGE_VALUE": ("Helvetica", 24, "bold"),
    "GAUGE_UNIT": ("Helvetica", 14, "normal"),
}

# =============================================================================
# Test State Definitions
# =============================================================================
# Test state descriptions for UI display
# Note: For ERROR state, this is just a template - actual error messages 
# will be generated dynamically with specific error details
TEST_STATES = {
    "IDLE": "System Ready",
    "FILLING": "Filling Tank...",
    "STABILIZING": "Stabilizing Pressure...",
    "TESTING": "Test in Progress...",
    "EMPTYING": "Emptying Tank...",
    "COMPLETE": "Test Complete",
    "ERROR": "Error: {message}",  # Template for error messages - will be formatted with specifics
    "REGULATING": "Regulating Pressure...",
    "STOPPED": "Test Stopped",
}

# =============================================================================
# Access Control and Security
# =============================================================================
# User role definitions
USER_ROLES = {
    "OPERATOR": {
        "level": 1,
        "default_password": "5673",
        "permissions": ["run_test",]
    },
    "MAINTENANCE": {
        "level": 2,
        "default_password": "5678",
        "permissions": ["run_test", "view_history", "edit_settings", "calibrate"]
    },
    "ADMIN": {
        "level": 3,
        "default_password": "9012",
        "permissions": ["run_test", "view_history", "edit_settings", "calibrate", "manage_users"]
    }
}


PERMISSIONS = {
    "run_test": "Ability to start and monitor tests",
    "view_history": "Ability to view test history and results",
    "edit_settings": "Ability to modify system settings",
    "calibrate": "Ability to perform system calibration",
    "manage_users": "Ability to manage user accounts"
}
# Default admin password
DEFAULT_PASSWORD = "9012"

# =============================================================================
# Printer Configuration
# =============================================================================
# Zebra printer USB configuration
PRINTER_CONFIG = {
    "VENDOR_ID": 0x1ff2,
    "PRODUCT_ID": 0x0001,
    "TEAR_OFFSET": 120,  # Default tear-off position adjustment
}

# =============================================================================
# Calibration Settings
# =============================================================================
# Calibration points for pressure sensors
CALIBRATION_POINTS = [0, 300, 600]  # Default calibration points in mbar
