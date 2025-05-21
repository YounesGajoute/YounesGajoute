#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pressure Sensor module for the Multi-Chamber Test application.

This module provides a PressureSensor class that interfaces with the Adafruit ADS1115
analog-to-digital converter to read voltage values from pressure sensors and convert
them to pressure values in mbar.
"""

import logging
import time
import Adafruit_ADS1x15
import numpy as np
from typing import List, Optional, Tuple, Dict, Any, Union

from multi_chamber_test.config.constants import ADC_ADDRESS, ADC_BUS_NUM, ADC_CONVERSION, PRESSURE_DEFAULTS

class PressureSensor:
    """
    Interface for pressure sensors connected to ADS1115 ADC.
    
    This class provides methods to read voltage values from pressure sensors
    connected to the Adafruit ADS1115 analog-to-digital converter, and
    convert them to pressure values in mbar using calibration parameters.
    
    The class supports up to 4 channels (0-3), with three typically used
    for the three chambers in the Multi-Chamber Test application.
    """
    
    def __init__(self, address: int = ADC_ADDRESS, bus_num: int = ADC_BUS_NUM):
        """
        Initialize the PressureSensor with the specified ADC address and bus number.
        
        Args:
            address: I2C address of the ADS1115 ADC (default: from constants)
            bus_num: I2C bus number (default: from constants)
        """
        self.logger = logging.getLogger('PressureSensor')
        self._setup_logger()
        
        # Store configuration parameters
        self.address = address
        self.bus_num = bus_num
        
        # Default conversion parameters
        self.voltage_offset = ADC_CONVERSION['VOLTAGE_OFFSET']
        self.voltage_multiplier = ADC_CONVERSION['VOLTAGE_MULTIPLIER']
        
        # Chamber-specific offsets (calibration)
        self.chamber_offsets = [0.0, 0.0, 0.0]  # Offsets in mbar for chambers 0-2
        
        # Initialize ADC
        self.adc = None
        self.initialized = False
        self.initialization_attempts = 0
        self.max_init_attempts = 3
        self.last_init_attempt = 0
        self.init_retry_interval = 5.0  # seconds between retry attempts
        
        # Filtering parameters
        self.alpha = 0.2  # Exponential moving average factor (lower = more smoothing)
        self.filtered_values = [0.0, 0.0, 0.0, 0.0]  # Filtered values for channels 0-3
        
        # Default gain
        self.gain = 1  # +/- 4.096V
        
        # Error tracking
        self.consecutive_errors = [0, 0, 0, 0]  # Track errors per channel
        self.max_consecutive_errors = 5  # Threshold before temporary disabling
        self.error_sleep_duration = 2.0  # Seconds to wait after max errors
        
        # Try initial initialization
        self.ensure_initialized()
    
    def _setup_logger(self):
        """Configure logging for the pressure sensor."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def ensure_initialized(self) -> bool:
        """
        Attempt to initialize ADC if not already initialized.
        
        Includes retry logic with backoff to avoid excessive error messages.
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        # If already initialized, return True
        if self.initialized and self.adc is not None:
            return True
            
        # Check if we should retry yet
        current_time = time.time()
        if (current_time - self.last_init_attempt < self.init_retry_interval and 
            self.initialization_attempts > 0):
            # Too soon to retry
            return False
            
        # Update attempt tracking
        self.last_init_attempt = current_time
        self.initialization_attempts += 1
        
        # Attempt initialization
        try:
            self.adc = Adafruit_ADS1x15.ADS1115(address=self.address, busnum=self.bus_num)
            self.initialized = True
            self.logger.info(f"ADC initialized at address 0x{self.address:02X} on bus {self.bus_num}")
            
            # Reset error tracking on successful init
            self.consecutive_errors = [0, 0, 0, 0]
            
            return True
            
        except Exception as e:
            self.initialized = False
            self.adc = None
            
            # Only log detailed error on first few attempts to avoid log flooding
            if self.initialization_attempts <= self.max_init_attempts:
                self.logger.error(f"Failed to initialize ADC (attempt {self.initialization_attempts}): {e}")
            elif self.initialization_attempts % 10 == 0:
                # Log less frequently after max attempts
                self.logger.warning(f"Still unable to initialize ADC after {self.initialization_attempts} attempts")
                
            return False
    
    def set_conversion_parameters(self, offset: float, multiplier: float):
        """
        Set the voltage to pressure conversion parameters.
        
        Args:
            offset: Voltage offset value
            multiplier: Voltage multiplier value
        """
        self.voltage_offset = offset
        self.voltage_multiplier = multiplier
        self.logger.info(f"Set conversion parameters: offset={offset}, multiplier={multiplier}")
    
    def set_chamber_offset(self, chamber_index: int, offset: float):
        """
        Set the calibration offset for a specific chamber.
        
        Args:
            chamber_index: Index of the chamber (0-2)
            offset: Pressure offset value in mbar
        """
        if not 0 <= chamber_index <= 2:
            self.logger.error(f"Invalid chamber index: {chamber_index}. Must be 0-2.")
            return
            
        self.chamber_offsets[chamber_index] = offset
        self.logger.info(f"Set chamber {chamber_index} offset to {offset} mbar")
    
    def read_voltage(self, channel: int) -> Optional[float]:
        """
        Read the raw voltage from the ADC channel.
        
        Args:
            channel: ADC channel to read (0-3)
            
        Returns:
            float: Voltage reading or None on error
        """
        # Check if channel is valid
        if not 0 <= channel <= 3:
            self.logger.error(f"Invalid channel: {channel}. Must be 0-3.")
            return None
            
        # Check if we're experiencing too many consecutive errors
        if self.consecutive_errors[channel] >= self.max_consecutive_errors:
            # Log only once when we hit the threshold to avoid log flooding
            if self.consecutive_errors[channel] == self.max_consecutive_errors:
                self.logger.warning(f"Channel {channel} disabled due to {self.consecutive_errors[channel]} consecutive errors")
                self.consecutive_errors[channel] += 1  # Increment to prevent repeated warnings
            return None
            
        # Try to ensure initialization before reading
        if not self.initialized or self.adc is None:
            if not self.ensure_initialized():
                # Increment error counter for this channel
                self.consecutive_errors[channel] += 1
                return None
        
        try:
            # Read raw ADC value
            raw = self.adc.read_adc(channel, gain=self.gain)
            
            # Convert to voltage (ADS1115 with gain=1 has range of +/- 4.096V)
            voltage = (raw / 32767.0) * 4.096
            
            # Reset error counter on success
            self.consecutive_errors[channel] = 0
            
            return voltage
            
        except Exception as e:
            # Handle error with backoff
            self.consecutive_errors[channel] += 1
            
            # Only log errors if not excessive to avoid log flooding
            if self.consecutive_errors[channel] <= self.max_consecutive_errors:
                self.logger.error(f"Error reading voltage from channel {channel}: {e}")
                
            # Check if we need to re-initialize the ADC
            if "No such device" in str(e) or "I/O error" in str(e):
                self.initialized = False
                self.adc = None
                
            return None
    
    def read_pressure(self, channel: int, apply_filter: bool = True) -> Optional[float]:
        """
        Read the pressure from the sensor connected to the ADC channel.
        
        Args:
            channel: ADC channel to read (0-3)
            apply_filter: Whether to apply filtering to the reading
            
        Returns:
            float: Pressure reading in mbar or None on error
        """
        # Check if channel is valid
        if not 0 <= channel <= 3:
            self.logger.error(f"Invalid channel: {channel}. Must be 0-3.")
            return None
        
        # Check if we're experiencing too many consecutive errors
        if self.consecutive_errors[channel] >= self.max_consecutive_errors:
            # Only sleep if we just hit the threshold
            if self.consecutive_errors[channel] == self.max_consecutive_errors:
                time.sleep(self.error_sleep_duration)
            return None
            
        try:
            # Read voltage
            voltage = self.read_voltage(channel)
            if voltage is None:
                return None
                
            # Convert to pressure (mbar)
            base_pressure = voltage * self.voltage_multiplier * 1000.0 + self.voltage_offset * 1000.0
            
            # Apply chamber-specific offset if applicable
            if channel <= 2:  # Chambers are mapped to channels 0-2
                adjusted_pressure = max(0, base_pressure + self.chamber_offsets[channel])
            else:
                adjusted_pressure = max(0, base_pressure)
                
            # Apply filtering if requested
            if apply_filter:
                self.filtered_values[channel] = self.alpha * adjusted_pressure + \
                                              (1 - self.alpha) * self.filtered_values[channel]
                return self.filtered_values[channel]
            else:
                return adjusted_pressure
                
        except Exception as e:
            # Increment error counter
            self.consecutive_errors[channel] += 1
            
            # Only log errors if not excessive
            if self.consecutive_errors[channel] <= self.max_consecutive_errors:
                self.logger.error(f"Error reading pressure from channel {channel}: {e}")
                
            return None
    
    def read_all_pressures(self, apply_filter: bool = True) -> List[Optional[float]]:
        """
        Read pressure values from all three chamber channels.
        
        Args:
            apply_filter: Whether to apply filtering to the readings
            
        Returns:
            List of pressure readings in mbar (None for any failed readings)
        """
        # Try to ensure initialization before reading
        if not self.initialized or self.adc is None:
            self.ensure_initialized()
            
        pressures = []
        for channel in range(3):  # Read channels 0-2 for the three chambers
            pressure = self.read_pressure(channel, apply_filter)
            pressures.append(pressure)
        return pressures
    
    def take_averaged_reading(self, channel: int, num_samples: int = 10, 
                             delay: float = 0.01) -> Optional[float]:
        """
        Take multiple pressure readings and return the average.
        
        Args:
            channel: ADC channel to read (0-3)
            num_samples: Number of samples to take
            delay: Delay between samples in seconds
            
        Returns:
            float: Average pressure reading in mbar or None on error
        """
        # Try to ensure initialization before reading
        if not self.initialized or self.adc is None:
            if not self.ensure_initialized():
                return None
            
        try:
            readings = []
            errors = 0
            max_errors = num_samples  # Allow retries up to 2x the requested samples
            
            # Keep trying until we get enough samples or hit max errors
            while len(readings) < num_samples and errors < max_errors:
                # Take reading without filtering
                pressure = self.read_pressure(channel, apply_filter=False)
                if pressure is not None:
                    readings.append(pressure)
                else:
                    errors += 1
                    
                time.sleep(delay)
                
            if not readings:
                self.logger.warning(f"Failed to get any valid samples from channel {channel}")
                return None
                
            # Calculate average
            avg_pressure = sum(readings) / len(readings)
            
            # Optionally update filtered value for this channel
            self.filtered_values[channel] = avg_pressure
            
            # Reset error counter after successful averaged reading
            self.consecutive_errors[channel] = 0
            
            return avg_pressure
            
        except Exception as e:
            self.logger.error(f"Error taking averaged reading from channel {channel}: {e}")
            return None
    
    def check_sensor_stability(self, channel: int, num_samples: int = 10, 
                              delay: float = 0.01, tolerance: float = 1.0) -> Tuple[bool, float, float]:
        """
        Check if pressure sensor readings are stable.
        
        Args:
            channel: ADC channel to read (0-3)
            num_samples: Number of samples to take
            delay: Delay between samples in seconds
            tolerance: Maximum acceptable standard deviation in mbar
            
        Returns:
            Tuple of (is_stable, average_pressure, standard_deviation)
        """
        # Try to ensure initialization before reading
        if not self.initialized or self.adc is None:
            if not self.ensure_initialized():
                return False, 0.0, 0.0
            
        try:
            readings = []
            errors = 0
            max_errors = num_samples  # Allow retries up to 2x the requested samples
            
            # Keep trying until we get enough samples or hit max errors
            while len(readings) < num_samples and errors < max_errors:
                # Take reading without filtering
                pressure = self.read_pressure(channel, apply_filter=False)
                if pressure is not None:
                    readings.append(pressure)
                else:
                    errors += 1
                    
                time.sleep(delay)
                
            if not readings:
                self.logger.warning(f"Failed to get any valid samples for stability check from channel {channel}")
                return False, 0.0, 0.0
                
            # Calculate average and standard deviation
            avg_pressure = sum(readings) / len(readings)
            std_dev = np.std(readings)
            
            is_stable = std_dev <= tolerance
            
            # Reset error counter after successful stability check
            self.consecutive_errors[channel] = 0
            
            return is_stable, avg_pressure, std_dev
            
        except Exception as e:
            self.logger.error(f"Error checking stability for channel {channel}: {e}")
            return False, 0.0, 0.0
    
    def validate_sensors(self) -> Dict[int, bool]:
        """
        Validate all pressure sensors by taking sample readings.
        
        Returns:
            Dictionary mapping channel numbers to validation results (True/False)
        """
        # Try to ensure initialization before validation
        if not self.initialized or self.adc is None:
            self.ensure_initialized()
            
        results = {}
        for channel in range(3):  # Check channels 0-2 for the three chambers
            try:
                # Attempt to take a reading
                pressure = self.read_pressure(channel, apply_filter=False)
                
                # A reading is considered valid if it's not None and within a reasonable range
                # (negative or extremely high pressures indicate sensor problems)
                is_valid = pressure is not None and 0 <= pressure <= PRESSURE_DEFAULTS['MAX_PRESSURE'] * 1.1
                
                results[channel] = is_valid
                
                if not is_valid:
                    self.logger.warning(f"Pressure sensor on channel {channel} failed validation")
                
            except Exception as e:
                self.logger.error(f"Error validating sensor on channel {channel}: {e}")
                results[channel] = False
                
        return results
    
    def set_filter_parameters(self, alpha: float):
        """
        Set the filtering parameters.
        
        Args:
            alpha: Exponential moving average factor (0-1)
                  Lower values give more smoothing, higher values respond faster to changes
        """
        if not 0 <= alpha <= 1:
            self.logger.error(f"Invalid alpha value: {alpha}. Must be between 0 and 1.")
            return
            
        self.alpha = alpha
        self.logger.info(f"Set filter alpha parameter to {alpha}")
    
    def reset_filtered_values(self):
        """Reset all filtered values to zero."""
        self.filtered_values = [0.0, 0.0, 0.0, 0.0]
        
    def reset_error_counters(self):
        """Reset all error counters, allowing retry of problematic channels."""
        self.consecutive_errors = [0, 0, 0, 0]
        self.logger.info("Reset all sensor error counters")
        
    def set_error_threshold(self, max_errors: int):
        """
        Set the threshold for consecutive errors before temporarily disabling a channel.
        
        Args:
            max_errors: Maximum number of consecutive errors allowed
        """
        if max_errors < 1:
            self.logger.error("Error threshold must be at least 1")
            return
            
        self.max_consecutive_errors = max_errors
        self.logger.info(f"Set error threshold to {max_errors} consecutive errors")