#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Settings manager for the Multi-Chamber Test application.

This module provides an improved SettingsManager class with consistent
observer notifications for all settings changes.
"""

import csv
import os
import logging
from typing import Callable, Any, Dict, List, Optional, Union
from .constants import SETTINGS_FILE, PRESSURE_DEFAULTS, TIME_DEFAULTS

class SettingsManager:
    """
    Manager for application settings with comprehensive change notifications.
    
    The SettingsManager maintains settings for the application, including:
    - Global test parameters (test duration)
    - Per-chamber settings (pressure target, threshold, tolerance, enabled state)
    - Calibration offsets
    
    Settings are stored in a CSV file with two columns: 'setting' and 'value'.
    All settings changes trigger observer notifications to keep the system in sync.
    """
    
    def __init__(self, settings_file: str = SETTINGS_FILE):
        """
        Initialize the SettingsManager with default settings.
        
        Args:
            settings_file: Path to the settings CSV file. Defaults to the value in constants.
        """
        self.settings_file = settings_file
        self.logger = logging.getLogger('SettingsManager')
        self._setup_logger()
        
        # Initialize with default settings
        self.settings = {}
        self._init_default_settings()
        self._observers = []
        # Load settings from file if available
        self.load_settings()
    
    def _setup_logger(self):
        """Configure logging for the settings manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _init_default_settings(self):
        """Initialize settings with default values."""
        # Global test settings
        self.settings['test_duration'] = TIME_DEFAULTS['TEST_DURATION']
        self.settings['test_mode'] = "reference"  # Default to reference mode
        
        # Per-chamber settings
        for i in range(1, 4):  # Chambers 1-3
            prefix = f'chamber{i}_'
            self.settings[f'{prefix}pressure_target'] = PRESSURE_DEFAULTS['TARGET']
            self.settings[f'{prefix}pressure_threshold'] = PRESSURE_DEFAULTS['THRESHOLD']
            self.settings[f'{prefix}pressure_tolerance'] = PRESSURE_DEFAULTS['TOLERANCE']
            self.settings[f'{prefix}enabled'] = 1  # Enabled by default
            self.settings[f'{prefix}offset'] = 0  # No offset by default
        
        # Login requirements
        self.settings['require_login'] = False
        self.settings['session_timeout'] = 600  # 10 minutes default
    
    def load_settings(self) -> bool:
        """
        Load settings from the settings file.
        
        Returns:
            bool: True if settings were loaded successfully, False otherwise.
        """
        try:
            if not os.path.exists(self.settings_file):
                self.logger.info("Settings file not found. Using default settings.")
                return False
            
            with open(self.settings_file, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames or 'setting' not in reader.fieldnames or 'value' not in reader.fieldnames:
                    self.logger.error("Invalid settings file format. Using default settings.")
                    return False
                
                for row in reader:
                    setting = row.get('setting')
                    value = row.get('value')
                    
                    if not setting or value is None:
                        continue
                    
                    # Convert value to appropriate type based on the setting name
                    if 'enabled' in setting:
                        self.settings[setting] = bool(int(value))
                    elif any(keyword in setting for keyword in ['duration', 'target', 'threshold', 'tolerance']):
                        self.settings[setting] = int(float(value))
                    elif 'offset' in setting:
                        self.settings[setting] = float(value)
                    else:
                        self.settings[setting] = value
                
                self.logger.info("Settings loaded successfully.")
                return True
                
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            return False
    
    def save_settings(self) -> bool:
        """
        Save current settings to the settings file.
        
        Returns:
            bool: True if settings were saved successfully, False otherwise.
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            
            with open(self.settings_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['setting', 'value'])
                
                for setting, value in self.settings.items():
                    # Convert boolean to int (1/0)
                    if isinstance(value, bool):
                        value = int(value)
                    
                    writer.writerow([setting, value])
            
            self.logger.info("Settings saved successfully.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def register_observer(self, callback: Callable[[str, Any], None]):
        """
        Register a callback to be called when settings are changed.
        The callback should accept (key, value) as arguments.
        """
        if callback not in self._observers:
            self._observers.append(callback)
            self.logger.debug(f"Registered observer {callback.__qualname__}")
    
    def unregister_observer(self, callback: Callable[[str, Any], None]):
        """
        Unregister a previously registered callback.
        
        Args:
            callback: The callback function to unregister
        """
        if callback in self._observers:
            self._observers.remove(callback)
            self.logger.debug(f"Unregistered observer {callback.__qualname__}")
    
    def _notify_observers(self, key: str, value: Any):
        """
        Notify all observers of a setting change.
        
        Args:
            key: The setting key that changed
            value: The new value of the setting
        """
        self.logger.debug(f"Notifying observers of change to {key}")
        for callback in self._observers:
            try:
                callback(key, value)
            except Exception as e:
                self.logger.error(f"Error in observer callback {callback.__qualname__}: {e}")
    
    def set_setting(self, key: str, value: Any, notify: bool = True):
        """
        Set a setting and optionally notify observers.
        
        Args:
            key: Setting key to update
            value: New value to set
            notify: Whether to notify observers (default: True)
        """
        old_value = self.settings.get(key)
        self.settings[key] = value
        
        # Only notify if the value actually changed
        if notify and old_value != value:
            self._notify_observers(key, value)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting by key.
        
        Args:
            key: Setting key to retrieve
            default: Default value if setting doesn't exist
            
        Returns:
            The setting value or default if not found
        """
        return self.settings.get(key, default)
    
    def get_test_duration(self) -> int:
        """Get the current test duration setting in seconds."""
        return int(self.settings.get('test_duration', TIME_DEFAULTS['TEST_DURATION']))
    
    def set_test_duration(self, duration: int, notify: bool = True) -> None:
        """
        Set the test duration with observer notification.
        
        Args:
            duration: Test duration in seconds
            notify: Whether to notify observers (default: True)
        """
        # Ensure positive value
        duration = max(1, int(duration)) 
        
        # Only update if changed
        if self.settings.get('test_duration') != duration:
            self.settings['test_duration'] = duration
            
            if notify:
                self._notify_observers('test_duration', duration)
    
    def get_chamber_settings(self, chamber_index: int) -> Dict[str, Any]:
        """
        Get all settings for a specific chamber.
        
        Args:
            chamber_index: Index of the chamber (1-3)
            
        Returns:
            Dict containing chamber settings: target, threshold, tolerance, enabled, offset
        """
        if not 1 <= chamber_index <= 3:
            raise ValueError(f"Invalid chamber index: {chamber_index}. Must be 1-3.")
            
        prefix = f'chamber{chamber_index}_'
        return {
            'pressure_target': int(self.settings.get(f'{prefix}pressure_target', PRESSURE_DEFAULTS['TARGET'])),
            'pressure_threshold': int(self.settings.get(f'{prefix}pressure_threshold', PRESSURE_DEFAULTS['THRESHOLD'])),
            'pressure_tolerance': int(self.settings.get(f'{prefix}pressure_tolerance', PRESSURE_DEFAULTS['TOLERANCE'])),
            'enabled': bool(self.settings.get(f'{prefix}enabled', True)),
            'offset': float(self.settings.get(f'{prefix}offset', 0.0))
        }
    
    def set_chamber_settings(self, chamber_index: int, settings: Dict[str, Any], notify: bool = True) -> None:
        """
        Update settings for a specific chamber with observer notifications.
        
        Args:
            chamber_index: Index of the chamber (1-3)
            settings: Dictionary of settings to update
            notify: Whether to notify observers (default: True)
        """
        if not 1 <= chamber_index <= 3:
            raise ValueError(f"Invalid chamber index: {chamber_index}. Must be 1-3.")
            
        prefix = f'chamber{chamber_index}_'
        changes = {}  # Track changes for notification
        
        if 'pressure_target' in settings:
            target = max(0, min(PRESSURE_DEFAULTS['MAX_PRESSURE'], int(settings['pressure_target'])))
            if self.settings.get(f'{prefix}pressure_target') != target:
                self.settings[f'{prefix}pressure_target'] = target
                changes[f'{prefix}pressure_target'] = target
            
        if 'pressure_threshold' in settings:
            threshold = max(0, int(settings['pressure_threshold']))
            if self.settings.get(f'{prefix}pressure_threshold') != threshold:
                self.settings[f'{prefix}pressure_threshold'] = threshold
                changes[f'{prefix}pressure_threshold'] = threshold
            
        if 'pressure_tolerance' in settings:
            tolerance = max(0, int(settings['pressure_tolerance']))
            if self.settings.get(f'{prefix}pressure_tolerance') != tolerance:
                self.settings[f'{prefix}pressure_tolerance'] = tolerance
                changes[f'{prefix}pressure_tolerance'] = tolerance
            
        if 'enabled' in settings:
            enabled = bool(settings['enabled'])
            if self.settings.get(f'{prefix}enabled') != enabled:
                self.settings[f'{prefix}enabled'] = enabled
                changes[f'{prefix}enabled'] = enabled
            
        if 'offset' in settings:
            offset = float(settings['offset'])
            if self.settings.get(f'{prefix}offset') != offset:
                self.settings[f'{prefix}offset'] = offset
                changes[f'{prefix}offset'] = offset
        
        # Notify about all changes
        if notify and changes:
            # First send the individual setting changes
            for key, value in changes.items():
                self._notify_observers(key, value)
            
            # Then send a notification that the entire chamber was updated
            # This allows components to perform bulk updates if needed
            chamber_key = f'chamber{chamber_index}'
            self._notify_observers(chamber_key, settings)
    
    def set_chamber_offset(self, chamber_index: int, offset: float, notify: bool = True) -> None:
        """
        Set the calibration offset for a specific chamber with optional notification.
        
        Args:
            chamber_index: Index of the chamber (1-3)
            offset: Pressure offset value in mbar
            notify: Whether to notify observers (default: True)
        """
        if not 1 <= chamber_index <= 3:
            raise ValueError(f"Invalid chamber index: {chamber_index}. Must be 1-3.")
        
        key = f'chamber{chamber_index}_offset'    
        old_value = self.settings.get(key, 0.0)
        new_value = float(offset)
        
        # Only update if changed
        if old_value != new_value:
            self.settings[key] = new_value
            
            if notify:
                self._notify_observers(key, new_value)
    
    def get_chamber_offset(self, chamber_index: int) -> float:
        """
        Get the calibration offset for a specific chamber.
        
        Args:
            chamber_index: Index of the chamber (1-3)
            
        Returns:
            float: The offset value in mbar
        """
        if not 1 <= chamber_index <= 3:
            raise ValueError(f"Invalid chamber index: {chamber_index}. Must be 1-3.")
            
        return float(self.settings.get(f'chamber{chamber_index}_offset', 0.0))
    
    def get_all_chamber_settings(self) -> List[Dict[str, Any]]:
        """
        Get settings for all chambers.
        
        Returns:
            List of dictionaries containing settings for each chamber.
        """
        return [self.get_chamber_settings(i) for i in range(1, 4)]
    
    def set_all_chamber_settings(self, settings_list: List[Dict[str, Any]], notify: bool = True) -> None:
        """
        Update settings for all chambers at once with notifications.
        
        Args:
            settings_list: List of dictionaries with settings for each chamber.
                         The list should have 3 elements (one per chamber).
            notify: Whether to notify observers (default: True)
        """
        if len(settings_list) != 3:
            raise ValueError(f"Expected 3 chamber settings, got {len(settings_list)}")
            
        for i, chamber_settings in enumerate(settings_list, 1):
            self.set_chamber_settings(i, chamber_settings, notify=False)
            
        # Send a single notification for all chambers if needed
        if notify:
            self._notify_observers('all_chambers', settings_list)
    
    def reset_to_defaults(self, notify: bool = True) -> None:
        """
        Reset all settings to their default values with notification.
        
        Args:
            notify: Whether to notify observers (default: True)
        """
        # Store old settings for comparison
        old_settings = self.settings.copy()
        
        # Reset to defaults
        self._init_default_settings()
        self.logger.info("Settings reset to defaults.")
        
        # Notify about changes
        if notify:
            # Identify changed settings
            for key, value in self.settings.items():
                if key not in old_settings or old_settings[key] != value:
                    self._notify_observers(key, value)
            
            # Finally send a global reset notification
            self._notify_observers('settings_reset', None)