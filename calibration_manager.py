#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Calibration Manager module for the Multi-Chamber Test application.

This module provides a CalibrationManager class that handles the calibration
of pressure sensors, including guiding the calibration process, calculating
calibration parameters, and storing calibration results.
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import numpy as np
from dataclasses import dataclass

from multi_chamber_test.config.constants import CALIBRATION_POINTS, ADC_CONVERSION
from multi_chamber_test.database.calibration_db import CalibrationDatabase, CalibrationPoint, CalibrationResult
from multi_chamber_test.hardware.valve_controller import ValveController
from multi_chamber_test.hardware.pressure_sensor import PressureSensor
from multi_chamber_test.hardware.printer import PrinterManager


class CalibrationManager:
    """
    Manager for pressure sensor calibration.
    
    This class provides methods to guide the user through the calibration process,
    calculate calibration parameters based on reference measurements, and store
    calibration results for future use.
    """
    
    def __init__(self, 
                 pressure_sensor: PressureSensor,
                 valve_controller: ValveController,
                 calibration_db: Optional[CalibrationDatabase] = None,
                 printer_manager: Optional[PrinterManager] = None):
        """
        Initialize the CalibrationManager with required components.
        
        Args:
            pressure_sensor: Pressure sensor instance for taking readings
            valve_controller: Valve controller for emptying chambers
            calibration_db: Optional calibration database for storing results
            printer_manager: Optional printer manager for printing reports
        """
        self.logger = logging.getLogger('CalibrationManager')
        self._setup_logger()
        
        self.pressure_sensor = pressure_sensor
        self.valve_controller = valve_controller
        self.calibration_db = calibration_db or CalibrationDatabase()
        self.printer_manager = printer_manager
        
        # Calibration state
        self.current_chamber = None
        self.calibration_points = []
        self.current_point_index = 0
        self.target_pressures = CALIBRATION_POINTS
        
        # Default calibration parameters
        self.voltage_offset = ADC_CONVERSION['VOLTAGE_OFFSET']
        self.voltage_multiplier = ADC_CONVERSION['VOLTAGE_MULTIPLIER']
        
        # Load existing calibration if available
        self._load_active_calibrations()
    
    def _setup_logger(self):
        """Configure logging for the calibration manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _load_active_calibrations(self):
        """Load the active calibration parameters for all chambers."""
        for chamber_id in range(3):  # 0-based index for chambers
            cal_result = self.calibration_db.get_active_calibration(chamber_id)
            if cal_result:
                self.logger.info(f"Loaded calibration for chamber {chamber_id + 1}: "
                                f"multiplier={cal_result.multiplier:.4f}, "
                                f"offset={cal_result.offset:.4f}")
                
                # Apply to pressure sensor if it's the global calibration (chamber 0)
                if chamber_id == 0:
                    self.voltage_multiplier = cal_result.multiplier
                    self.voltage_offset = cal_result.offset
                    self.pressure_sensor.set_conversion_parameters(cal_result.offset, cal_result.multiplier)
    
    def start_calibration(self, chamber_id: int) -> bool:
        """
        Start the calibration process for a chamber.
        
        Args:
            chamber_id: Chamber ID (0-2) to calibrate
            
        Returns:
            bool: True if calibration started successfully, False otherwise
        """
        if not 0 <= chamber_id <= 2:
            self.logger.error(f"Invalid chamber ID: {chamber_id}")
            return False
        
        try:
            self.current_chamber = chamber_id
            self.calibration_points = []
            self.current_point_index = 0
            
            # Empty the chamber to prepare for calibration
            self._empty_chamber()
            
            self.logger.info(f"Started calibration for chamber {chamber_id + 1}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting calibration: {e}")
            return False
    
    def _empty_chamber(self) -> bool:
        """
        Empty the current chamber.
        
        Returns:
            bool: True if emptying was successful, False otherwise
        """
        if self.current_chamber is None:
            self.logger.error("No chamber selected for calibration")
            return False
        
        try:
            # Use the valve controller to empty the chamber
            self.logger.info(f"Emptying chamber {self.current_chamber + 1}")
            success = self.valve_controller.empty_chamber(self.current_chamber)
            
            # Wait for chamber to empty
            time.sleep(10)  # Allow time for chamber to fully empty
            
            # Close all valves
            self.valve_controller.stop_chamber(self.current_chamber)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error emptying chamber: {e}")
            return False
    
    def record_calibration_point(self) -> Tuple[bool, float, float]:
        """
        Record a calibration point at the current target pressure.
        
        Returns:
            Tuple of (success, measured_pressure, measured_voltage)
        """
        if self.current_chamber is None:
            self.logger.error("No chamber selected for calibration")
            return False, 0.0, 0.0
        
        if self.current_point_index >= len(self.target_pressures):
            self.logger.error("All calibration points have been recorded")
            return False, 0.0, 0.0
        
        target = self.target_pressures[self.current_point_index]
        
        try:
            # Take multiple readings to ensure stability
            is_stable, avg_pressure, std_dev = self.pressure_sensor.check_sensor_stability(
                self.current_chamber, num_samples=20, delay=0.05, tolerance=2.0
            )
            
            if not is_stable:
                self.logger.warning(f"Pressure reading is not stable: {avg_pressure:.1f} mbar ±{std_dev:.1f}")
                return False, avg_pressure, 0.0
            
            # Get current voltage reading
            voltage = self.pressure_sensor.read_voltage(self.current_chamber)
            if voltage is None:
                self.logger.error("Failed to read voltage")
                return False, 0.0, 0.0
            
            # Validate pressure is near target (if not zero point)
            if target > 0 and abs(avg_pressure - target) > 20:
                self.logger.warning(f"Pressure ({avg_pressure:.1f} mbar) too far from target ({target} mbar)")
                return False, avg_pressure, voltage
            
            # Create and store calibration point
            point = CalibrationPoint(
                pressure=target,  # Use target value as the reference
                voltage=voltage,
                timestamp=datetime.now()
            )
            
            self.calibration_points.append(point)
            self.current_point_index += 1
            
            self.logger.info(f"Recorded calibration point {len(self.calibration_points)}: "
                           f"pressure={target} mbar, voltage={voltage:.4f}V")
            
            return True, target, voltage
            
        except Exception as e:
            self.logger.error(f"Error recording calibration point: {e}")
            return False, 0.0, 0.0
    
    def calculate_calibration(self) -> Optional[CalibrationResult]:
        """
        Calculate calibration parameters from the recorded points.
        
        Returns:
            CalibrationResult object or None if calculation failed
        """
        if self.current_chamber is None:
            self.logger.error("No chamber selected for calibration")
            return None
        
        if len(self.calibration_points) < 2:
            self.logger.error("Need at least two calibration points")
            return None
        
        try:
            # Calculate linear regression using NumPy
            # For pressure = multiplier * voltage + offset
            x = np.array([point.voltage for point in self.calibration_points])
            y = np.array([point.pressure for point in self.calibration_points])
            
            # Calculate means
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            
            # Calculate slope (multiplier)
            numerator = np.sum((x - x_mean) * (y - y_mean))
            denominator = np.sum((x - x_mean) ** 2)
            
            if denominator == 0:
                self.logger.error("Calculation error: division by zero")
                return None
                
            multiplier = numerator / denominator
            
            # Calculate y-intercept (offset)
            offset = y_mean - multiplier * x_mean
            
            # Calculate R-squared value to measure fit quality
            y_pred = multiplier * x + offset
            ss_total = np.sum((y - y_mean) ** 2)
            ss_residual = np.sum((y - y_pred) ** 2)
            
            if ss_total == 0:
                r_squared = 0  # Avoid division by zero
            else:
                r_squared = 1 - (ss_residual / ss_total)
            
            # Create calibration result
            result = CalibrationResult(
                chamber_id=self.current_chamber,
                multiplier=multiplier,
                offset=offset,
                r_squared=r_squared,
                calibration_date=datetime.now(),
                points=self.calibration_points.copy()
            )
            
            self.logger.info(f"Calculated calibration for chamber {self.current_chamber + 1}: "
                           f"multiplier={multiplier:.4f}, offset={offset:.4f}, R²={r_squared:.4f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating calibration: {e}")
            return None
    
    def save_calibration(self, calibration: CalibrationResult) -> bool:
        """
        Save the calibration result to the database and apply settings.
        
        Args:
            calibration: Calibration result to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Save to database
            self.calibration_db.save_calibration(calibration)
            
            # Apply to pressure sensor if it's the global calibration (chamber 0)
            if calibration.chamber_id == 0:
                self.voltage_multiplier = calibration.multiplier
                self.voltage_offset = calibration.offset
                self.pressure_sensor.set_conversion_parameters(calibration.offset, calibration.multiplier)
            
            # Set chamber-specific offset if not chamber 0
            else:
                # Chamber-specific offsets are handled differently
                # They typically adjust the final pressure value rather than the voltage conversion
                pass
            
            # Print calibration report if printer is available
            if self.printer_manager:
                calibration_data = {
                    'chamber_number': calibration.chamber_id + 1,  # Convert to 1-based for display
                    'date': calibration.calibration_date.strftime("%Y-%m-%d %H:%M:%S"),
                    'voltage_offset': f"{calibration.offset:.4f}",
                    'voltage_multiplier': f"{calibration.multiplier:.4f}",
                    'points': [
                        {
                            'pressure': point.pressure,
                            'voltage': f"{point.voltage:.3f}"
                        }
                        for point in calibration.points
                    ]
                }
                self.printer_manager.print_calibration_report(calibration_data)
            
            self.logger.info(f"Saved calibration for chamber {calibration.chamber_id + 1}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving calibration: {e}")
            return False
    
    def complete_calibration(self) -> bool:
        """
        Complete the calibration process by calculating and saving results.
        
        Returns:
            bool: True if calibration was completed successfully, False otherwise
        """
        if self.current_chamber is None:
            self.logger.error("No chamber selected for calibration")
            return False
        
        try:
            # Calculate calibration parameters
            calibration = self.calculate_calibration()
            if not calibration:
                self.logger.error("Failed to calculate calibration")
                return False
            
            # Verify calibration quality
            if calibration.r_squared < 0.95:
                self.logger.warning(f"Poor calibration quality (R-squared = {calibration.r_squared:.3f})")
                # Could still save, but warn the user
            
            # Save calibration
            success = self.save_calibration(calibration)
            
            # Reset calibration state
            if success:
                self.current_chamber = None
                self.calibration_points = []
                self.current_point_index = 0
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error completing calibration: {e}")
            return False
    
    def abort_calibration(self) -> bool:
        """
        Abort the current calibration process.
        
        Returns:
            bool: True if abort was successful, False otherwise
        """
        if self.current_chamber is None:
            return True  # Nothing to abort
        
        try:
            # Close all valves for the current chamber
            if self.valve_controller:
                self.valve_controller.stop_chamber(self.current_chamber)
            
            # Reset calibration state
            self.current_chamber = None
            self.calibration_points = []
            self.current_point_index = 0
            
            self.logger.info("Calibration aborted")
            return True
            
        except Exception as e:
            self.logger.error(f"Error aborting calibration: {e}")
            return False
    
    def get_calibration_history(self, chamber_id: int, limit: int = 10) -> List[CalibrationResult]:
        """
        Get the calibration history for a chamber.
        
        Args:
            chamber_id: Chamber ID to get history for
            limit: Maximum number of history entries to return
            
        Returns:
            List of CalibrationResult objects
        """
        try:
            return self.calibration_db.get_calibration_history(chamber_id, limit)
        except Exception as e:
            self.logger.error(f"Error getting calibration history: {e}")
            return []
    
    def get_active_calibration(self, chamber_id: int) -> Optional[CalibrationResult]:
        """
        Get the active calibration for a chamber.
        
        Args:
            chamber_id: Chamber ID to get calibration for
            
        Returns:
            CalibrationResult object or None if no active calibration
        """
        try:
            return self.calibration_db.get_active_calibration(chamber_id)
        except Exception as e:
            self.logger.error(f"Error getting active calibration: {e}")
            return None
    
    def get_next_calibration_point(self) -> Optional[int]:
        """
        Get the next calibration point target pressure.
        
        Returns:
            Target pressure in mbar or None if no more points
        """
        if self.current_chamber is None:
            return None
            
        if self.current_point_index >= len(self.target_pressures):
            return None
            
        return self.target_pressures[self.current_point_index]
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """
        Get the current status of the calibration process.
        
        Returns:
            Dictionary with calibration status information
        """
        return {
            'current_chamber': self.current_chamber,
            'current_point_index': self.current_point_index,
            'total_points': len(self.target_pressures),
            'points_recorded': len(self.calibration_points),
            'next_target': self.get_next_calibration_point(),
            'in_progress': self.current_chamber is not None
        }
    
    def run_guided_calibration(self, chamber_id: int, 
                              status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                              completion_callback: Optional[Callable[[Optional[CalibrationResult]], None]] = None) -> bool:
        """
        Run a guided calibration process with callbacks for UI feedback.
        
        Args:
            chamber_id: Chamber ID to calibrate
            status_callback: Function to call with status updates
            completion_callback: Function to call when calibration is complete
            
        Returns:
            bool: True if calibration started successfully, False otherwise
        """
        if not 0 <= chamber_id <= 2:
            self.logger.error(f"Invalid chamber ID: {chamber_id}")
            if status_callback:
                status_callback("error", {"message": f"Invalid chamber ID: {chamber_id}"})
            return False
        
        try:
            # Start calibration
            success = self.start_calibration(chamber_id)
            if not success:
                if status_callback:
                    status_callback("error", {"message": "Failed to start calibration"})
                return False
            
            if status_callback:
                status_callback("started", {
                    "chamber_id": chamber_id,
                    "total_points": len(self.target_pressures)
                })
            
            # Empty the chamber
            if status_callback:
                status_callback("emptying", {
                    "chamber_id": chamber_id
                })
            
            # Let the UI take over from here - it will call methods like:
            # - record_calibration_point()
            # - complete_calibration()
            # - abort_calibration()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error running guided calibration: {e}")
            if status_callback:
                status_callback("error", {"message": str(e)})
            return False
