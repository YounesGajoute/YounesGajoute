#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Manager module for the Multi-Chamber Test application.

This module provides a TestManager class that coordinates the execution
of pressure leak tests, managing the test phases, pressure regulation,
and result reporting across multiple chambers.
"""

import logging
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
import numpy as np

from multi_chamber_test.config.constants import TIME_DEFAULTS, PRESSURE_DEFAULTS, TEST_STATES
from multi_chamber_test.hardware.valve_controller import ValveController
from multi_chamber_test.hardware.pressure_sensor import PressureSensor
from multi_chamber_test.hardware.printer import PrinterManager
from multi_chamber_test.utils.pid_controller import PIDControllerWrapper
from multi_chamber_test.database.reference_db import ReferenceDatabase
from multi_chamber_test.core.logger import TestLogger

class ChamberTestState:
    """
    State container for an individual chamber during testing.
    
    This class maintains the state and test parameters for a single
    chamber during the testing process.
    """
    
    def __init__(self, chamber_index: int):
        """
        Initialize the chamber state.
        
        Args:
            chamber_index: Index of the chamber (0-2)
        """
        self.chamber_index = chamber_index  # 0-based index
        
        # Chamber parameters
        self.enabled = True
        self.pressure_target = PRESSURE_DEFAULTS['TARGET']
        self.pressure_threshold = PRESSURE_DEFAULTS['THRESHOLD']
        self.pressure_tolerance = PRESSURE_DEFAULTS['TOLERANCE']
        
        # Test state
        self.current_pressure = 0.0
        self.pressure_readings = []
        self.start_pressure = 0.0
        self.final_pressure = 0.0
        self.result = False
        
        # Phase tracking
        self.filled = False
        self.regulated = False
        self.stabilized = False
        self.tested = False
        self.pid_controller = None

    def reset(self):
        """Reset the chamber state for a new test."""
        self.current_pressure = 0.0
        self.pressure_readings = []
        self.start_pressure = 0.0
        self.final_pressure = 0.0
        self.result = False
        
        self.filled = False
        self.regulated = False
        self.stabilized = False
        self.tested = False
        
        # Reinitialize PID controller with current parameters
        if self.pid_controller:
            self.pid_controller.reset()
    
    def init_pid_controller(self):
        """Initialize PID controller with chamber parameters."""
        self.pid_controller = PIDControllerWrapper(
            setpoint=self.pressure_target,
            output_limits=(0.0, 1.0)
        )
        

class TestManager:
    """
    Manager for multi-chamber pressure leakage testing.
    
    This class coordinates the multi-phase test process across all chambers,
    including pressure regulation, stabilization, and result evaluation.
    """
    
    def __init__(self, 
                 valve_controller: ValveController,
                 pressure_sensor: PressureSensor,
                 printer_manager: Optional[PrinterManager] = None,
                 reference_db: Optional[ReferenceDatabase] = None,
                 test_logger: Optional[TestLogger] = None):
        """
        Initialize the TestManager with required components.
        
        Args:
            valve_controller: Controller for chamber valves
            pressure_sensor: Sensor for pressure readings
            printer_manager: Optional manager for result printing
            reference_db: Optional database for reference profiles
            test_logger: Optional logger for test results
        """
        self.logger = logging.getLogger('TestManager')
        self._setup_logger()
        
        self.valve_controller = valve_controller
        self.pressure_sensor = pressure_sensor
        self.printer_manager = printer_manager
        self.reference_db = reference_db
        self.test_logger = test_logger or TestLogger()
        
        # Test parameters
        self.test_mode = "manual"  # "manual" or "reference"
        self.current_reference = None
        self.test_duration = TIME_DEFAULTS['TEST_DURATION']
        
        # Test state
        self.chamber_states = [ChamberTestState(i) for i in range(3)]
        self.test_state = "IDLE"
        self.test_phase = None
        self.elapsed_time = 0.0
        self.running_test = False
        self._stop_requested = False
        
        # Monitoring thread
        self.monitoring_thread = None
        self._monitoring_running = False
        
        # Callbacks for UI updates
        self.status_callback = None
        self.progress_callback = None
        self.result_callback = None
    
    def _setup_logger(self):
        """Configure logging for the test manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def set_callbacks(self, status_callback: Optional[Callable] = None,
                     progress_callback: Optional[Callable] = None,
                     result_callback: Optional[Callable] = None):
        """
        Set callbacks for UI updates.
        
        Args:
            status_callback: Function to call with test state changes
            progress_callback: Function to call with test progress updates
            result_callback: Function to call with test results
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.result_callback = result_callback
    
    def set_test_mode(self, mode: str, reference: Optional[str] = None) -> bool:
        """
        Set the test mode and reference.
        
        Args:
            mode: Test mode ("manual" or "reference")
            reference: Reference barcode for reference mode
            
        Returns:
            bool: True if mode was set successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot change mode during active test")
            return False
            
        if mode not in ["manual", "reference"]:
            self.logger.error(f"Invalid test mode: {mode}")
            return False
            
        self.test_mode = mode
        
        if mode == "reference":
            if not reference:
                self.logger.error("Reference barcode required for reference mode")
                return False
                
            if self.reference_db:
                # Load reference from database
                ref_data = self.reference_db.load_reference(reference)
                if not ref_data:
                    self.logger.error(f"Reference not found: {reference}")
                    return False
                    
                # Apply reference parameters
                self.current_reference = reference
                self.test_duration = ref_data.get('test_duration', TIME_DEFAULTS['TEST_DURATION'])
                
                # Apply chamber-specific parameters
                chamber_data = ref_data.get('chambers', [])
                for i, chamber in enumerate(chamber_data):
                    if i < len(self.chamber_states):
                        self.chamber_states[i].enabled = chamber.get('enabled', True)
                        self.chamber_states[i].pressure_target = chamber.get('pressure_target', PRESSURE_DEFAULTS['TARGET'])
                        self.chamber_states[i].pressure_threshold = chamber.get('pressure_threshold', PRESSURE_DEFAULTS['THRESHOLD'])
                        self.chamber_states[i].pressure_tolerance = chamber.get('pressure_tolerance', PRESSURE_DEFAULTS['TOLERANCE'])
            else:
                self.logger.warning("Reference database not available, can't load reference")
                return False
                
        else:  # manual mode
            self.current_reference = None
        
        self.logger.info(f"Test mode set to {mode}" + (f" with reference {reference}" if reference else ""))
        return True
    
    def set_chamber_parameters(self, chamber_index: int, params: Dict[str, Any]) -> bool:
        """
        Set parameters for a specific chamber.
        
        Args:
            chamber_index: Index of the chamber (0-2)
            params: Dictionary of parameters to set
            
        Returns:
            bool: True if parameters were set successfully, False otherwise
        """
        if not 0 <= chamber_index <= 2:
            self.logger.error(f"Invalid chamber index: {chamber_index}")
            return False
            
        if self.running_test:
            self.logger.error("Cannot change parameters during active test")
            return False
            
        chamber = self.chamber_states[chamber_index]
        
        if 'enabled' in params:
            chamber.enabled = bool(params['enabled'])
            
        if 'pressure_target' in params:
            target = float(params['pressure_target'])
            if 0 <= target <= PRESSURE_DEFAULTS['MAX_PRESSURE']:
                chamber.pressure_target = target
            else:
                self.logger.error(f"Invalid target pressure: {target}")
                return False
                
        if 'pressure_threshold' in params:
            threshold = float(params['pressure_threshold'])
            if threshold >= 0:
                chamber.pressure_threshold = threshold
            else:
                self.logger.error(f"Invalid threshold pressure: {threshold}")
                return False
                
        if 'pressure_tolerance' in params:
            tolerance = float(params['pressure_tolerance'])
            if tolerance >= 0:
                chamber.pressure_tolerance = tolerance
            else:
                self.logger.error(f"Invalid pressure tolerance: {tolerance}")
                return False
        
        self.logger.info(f"Updated parameters for chamber {chamber_index + 1}")
        return True
    
    def set_test_duration(self, duration: int) -> bool:
        """
        Set the test duration.
        
        Args:
            duration: Test duration in seconds
            
        Returns:
            bool: True if duration was set successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot change duration during active test")
            return False
            
        if duration <= 0:
            self.logger.error(f"Invalid test duration: {duration}")
            return False
            
        self.test_duration = duration
        self.logger.info(f"Test duration set to {duration} seconds")
        return True
    
    def get_test_status(self) -> Dict[str, Any]:
        """
        Get the current test status.
        
        Returns:
            Dictionary with test status information
        """
        chamber_info = []
        for chamber in self.chamber_states:
            chamber_info.append({
                'index': chamber.chamber_index,
                'enabled': chamber.enabled,
                'pressure_target': chamber.pressure_target,
                'pressure_threshold': chamber.pressure_threshold,
                'pressure_tolerance': chamber.pressure_tolerance,
                'current_pressure': chamber.current_pressure,
                'result': chamber.result if self.test_state == 'COMPLETE' else None
            })
            
        return {
            'test_mode': self.test_mode,
            'reference': self.current_reference,
            'test_state': self.test_state,
            'test_phase': self.test_phase,
            'elapsed_time': self.elapsed_time,
            'total_duration': self.test_duration,
            'running': self.running_test,
            'chambers': chamber_info
        }
    
    def start_test(self) -> bool:
        """
        Start a test with the current parameters.
        
        Returns:
            bool: True if test started successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Test already in progress")
            return False
            
        if self.test_mode == "reference" and not self.current_reference:
            self.logger.error("No reference loaded for reference mode")
            return False
            
        # Check if any chambers are enabled
        enabled_chambers = [ch for ch in self.chamber_states if ch.enabled]
        if not enabled_chambers:
            self.logger.error("No chambers enabled for testing")
            return False
        
        # Check if the current user has permission to run tests
        from multi_chamber_test.core.roles import get_role_manager
        role_manager = get_role_manager()
        if not role_manager.has_permission("run_test"):
            self.logger.error("Current user does not have permission to run tests")
            self._update_status("ERROR", "Login required to run tests")
            return False
        
        # Initialize test state
        self._stop_requested = False
        self.running_test = True
        self.test_state = "IDLE"
        self.test_phase = None
        self.elapsed_time = 0.0
        
        for chamber in self.chamber_states:
            chamber.reset()
            chamber.init_pid_controller()
        
        # Start test in a separate thread
        self.test_thread = threading.Thread(target=self._run_test, daemon=True)
        self.test_thread.start()
        
        self.logger.info("Test started")
        return True
    
    def stop_test(self) -> bool:
        """
        Stop the current test.
        
        Returns:
            bool: True if stop was requested successfully, False otherwise
        """
        if not self.running_test:
            self.logger.info("No test running")
            return True
            
        self._stop_requested = True
        self.test_state = "STOPPING"
        self._update_status("Stopping test...")
        
        self.logger.info("Test stop requested")
        return True
    
    def _update_status(self, message: str, update_ui: bool = True):
        """
        Update test status with the given message.
        
        Args:
            message: Status message
            update_ui: Whether to trigger UI update callback
        """
        self.logger.info(message)
        
        if update_ui and self.status_callback:
            self.status_callback(self.test_state, message)
    
    def _update_progress(self, phase: str, progress: float, phase_progress: Dict[str, Any] = None):
        """
        Update test progress information.
        
        Args:
            phase: Current test phase
            progress: Overall progress (0-1)
            phase_progress: Phase-specific progress information
        """
        if self.progress_callback:
            self.progress_callback(phase, progress, phase_progress or {})
    
    def _check_stop_requested(self) -> bool:
        """
        Check if stop has been requested and update state if needed.
        
        Returns:
            bool: True if stop has been requested, False otherwise
        """
        if self._stop_requested:
            if self.test_state != "STOPPING" and self.test_state != "EMPTYING":
                self.test_state = "STOPPING"
                self._update_status("Test stop requested")
            return True
        return False
    
    def _run_test(self):
        """Main test execution method that runs in a separate thread."""
        try:
            # Start pressure monitoring
            self._start_monitoring()
            
            # Run the test phases
            result = False
            try:
                if not self._run_filling_phase():
                    raise Exception("Fill phase failed")
                    
                if not self._run_regulation_phase():
                    raise Exception("Regulation phase failed")
                    
                if not self._run_stabilization_phase():
                    raise Exception("Stabilization phase failed")
                    
                if not self._run_testing_phase():
                    raise Exception("Testing phase failed")
                    
                # If all phases completed, the test is successful
                result = True
                
            except Exception as e:
                self.logger.error(f"Test error: {e}")
                self.test_state = "ERROR"
                self._update_status(f"Error: {str(e)}")
            
            finally:
                # Always run emptying phase
                self._run_emptying_phase()
                
                # Process and log results
                self._process_results(result)
                
                # Stop monitoring
                self._stop_monitoring()
                
        except Exception as e:
            self.logger.error(f"Unhandled test error: {e}")
            self.test_state = "ERROR"
            self._update_status(f"Unhandled error: {str(e)}")
            
        finally:
            # Ensure test is marked as not running
            self.running_test = False
            
            if self.test_state not in ["COMPLETE", "ERROR", "STOPPED"]:
                self.test_state = "IDLE"
                self._update_status("Test idle")
    
    def _run_filling_phase(self) -> bool:
        """
        Execute the fill phase for all enabled chambers.
        
        Returns:
            bool: True if fill phase was successful, False otherwise
        """
        self.test_phase = "filling"
        self.test_state = "FILLING"
        self._update_status("Filling chambers...")
        
        # Track chambers that need filling
        chambers_filling = [ch for ch in self.chamber_states if ch.enabled]
        
        # Fill all chambers concurrently with timeout
        start_time = time.time()
        phase_timeout = 60  # Maximum 60 seconds for filling phase
        
        while chambers_filling and not self._check_stop_requested():
            # Calculate phase progress for UI
            elapsed = time.time() - start_time
            if elapsed > phase_timeout:
                self.logger.error("Fill phase timeout")
                return False
                
            phase_progress = elapsed / phase_timeout
            self._update_progress("filling", 0.1 * phase_progress, {
                "chambers_remaining": len(chambers_filling),
                "elapsed_time": elapsed
            })
            
            # Update chambers list
            chambers_filling = [ch for ch in chambers_filling if not ch.filled]
            if not chambers_filling:
                break
                
            # Control valves for each chamber still filling
            for chamber in chambers_filling:
                current_pressure = chamber.current_pressure
                target_pressure = chamber.pressure_target
                
                if current_pressure >= target_pressure:
                    # Target reached, mark as filled
                    self.valve_controller.set_chamber_valves(chamber.chamber_index, False, False)
                    chamber.filled = True
                    self.logger.info(f"Chamber {chamber.chamber_index + 1} filled to {current_pressure:.1f} mbar")
                else:
                    # Continue filling
                    self.valve_controller.set_chamber_valves(chamber.chamber_index, True, False)
            
            # Short delay between iterations
            time.sleep(0.1)
        
        # Check if filling was successful
        if self._check_stop_requested():
            return False
            
        all_filled = all(ch.filled for ch in self.chamber_states if ch.enabled)
        
        self.logger.info("Fill phase complete" if all_filled else "Fill phase incomplete")
        return all_filled
    
    def _run_regulation_phase(self) -> bool:
        """
        Execute the pressure regulation phase for all enabled chambers.
        
        Returns:
            bool: True if regulation was successful, False otherwise
        """
        self.test_phase = "regulating"
        self.test_state = "REGULATING"
        self._update_status("Regulating pressure...")
        
        # Track chambers that need regulation
        chambers_regulating = [ch for ch in self.chamber_states if ch.enabled and ch.filled]
        
        # Regulate all chambers concurrently with timeout
        start_time = time.time()
        phase_timeout = 120  # Maximum 120 seconds for regulation phase
        
        # Adaptive control parameters for different regulation modes
        fast_mode = {
            "threshold": 10.0,  # mbar from target for fast mode
            "pulse_on": 0.1,    # seconds
            "pulse_off": 0.05   # seconds
        }
        
        medium_mode = {
            "threshold": 5.0,   # mbar from target for medium mode
            "pulse_on": 0.05,   # seconds
            "pulse_off": 0.1    # seconds
        }
        
        fine_mode = {
            "threshold": 1.0,   # mbar from target for fine mode
            "pulse_on": 0.02,   # seconds
            "pulse_off": 0.2    # seconds
        }
        
        # Track the regulation state for each chamber
        regulation_states = {ch.chamber_index: "fast" for ch in chambers_regulating}
        pressure_rates = {ch.chamber_index: [] for ch in chambers_regulating}
        last_pressures = {ch.chamber_index: None for ch in chambers_regulating}
        stable_counts = {ch.chamber_index: 0 for ch in chambers_regulating}
        
        while chambers_regulating and not self._check_stop_requested():
            # Calculate phase progress for UI
            elapsed = time.time() - start_time
            if elapsed > phase_timeout:
                self.logger.error("Regulation phase timeout")
                return False
                
            phase_progress = elapsed / phase_timeout
            self._update_progress("regulating", 0.1 + 0.2 * phase_progress, {
                "chambers_remaining": len(chambers_regulating),
                "elapsed_time": elapsed
            })
            
            # Update chambers list
            chambers_regulating = [ch for ch in chambers_regulating if not ch.regulated]
            if not chambers_regulating:
                break
                
            # Apply PID control for each chamber still regulating
            for chamber in chambers_regulating:
                chamber_index = chamber.chamber_index
                current_pressure = chamber.current_pressure
                target_pressure = chamber.pressure_target
                
                # Calculate error and tolerance
                error = target_pressure - current_pressure
                abs_error = abs(error)
                tolerance = chamber.pressure_tolerance
                
                # Calculate pressure change rate
                if last_pressures[chamber_index] is not None:
                    rate = (current_pressure - last_pressures[chamber_index]) / 0.1  # Rate per second
                    pressure_rates[chamber_index].append(rate)
                    if len(pressure_rates[chamber_index]) > 10:
                        pressure_rates[chamber_index].pop(0)
                last_pressures[chamber_index] = current_pressure
                
                # Check if within tolerance
                if abs_error <= tolerance:
                    stable_counts[chamber_index] += 1
                    if stable_counts[chamber_index] >= 5:  # Stable for 0.5 seconds within tolerance
                        # Mark as regulated
                        self.valve_controller.set_chamber_valves(chamber_index, False, False)
                        chamber.regulated = True
                        self.logger.info(f"Chamber {chamber_index + 1} regulated to {current_pressure:.1f} mbar")
                        continue
                else:
                    stable_counts[chamber_index] = 0
                
                # Determine control mode based on error magnitude
                if abs_error > fast_mode["threshold"]:
                    control_mode = fast_mode
                    mode_name = "FAST"
                elif abs_error > medium_mode["threshold"]:
                    control_mode = medium_mode
                    mode_name = "MEDIUM"
                else:
                    control_mode = fine_mode
                    mode_name = "FINE"
                
                # Calculate average rate of change if available
                avg_rate = 0
                if pressure_rates[chamber_index]:
                    avg_rate = sum(pressure_rates[chamber_index]) / len(pressure_rates[chamber_index])
                
                # Adaptive pulse timing based on rate of change
                rate_factor = min(1.0, abs(avg_rate) / 10.0)  # Normalize rate impact
                adjusted_pulse_on = control_mode["pulse_on"] * (1 - rate_factor)
                adjusted_pulse_off = control_mode["pulse_off"] * (1 + rate_factor)
                
                # Apply control action
                if error > tolerance:  # Need to increase pressure
                    if regulation_states[chamber_index] != "filling":
                        self.logger.debug(f"Chamber {chamber_index + 1} - {mode_name} increase: "
                                        f"{current_pressure:.1f}/{target_pressure:.1f} mbar "
                                        f"(rate: {avg_rate:.2f} mbar/s)")
                        regulation_states[chamber_index] = "filling"
                    self.valve_controller.set_chamber_valves(chamber_index, True, False)
                    time.sleep(adjusted_pulse_on)
                    self.valve_controller.set_chamber_valves(chamber_index, False, False)
                    time.sleep(adjusted_pulse_off)
                    
                elif error < -tolerance:  # Need to decrease pressure
                    if regulation_states[chamber_index] != "venting":
                        self.logger.debug(f"Chamber {chamber_index + 1} - {mode_name} decrease: "
                                        f"{current_pressure:.1f}/{target_pressure:.1f} mbar "
                                        f"(rate: {avg_rate:.2f} mbar/s)")
                        regulation_states[chamber_index] = "venting"
                    self.valve_controller.set_chamber_valves(chamber_index, False, True)
                    time.sleep(adjusted_pulse_on * 1.5)  # Longer pulse for venting
                    self.valve_controller.set_chamber_valves(chamber_index, False, False)
                    time.sleep(adjusted_pulse_off)
                    
                else:
                    regulation_states[chamber_index] = "stable"
                    self.valve_controller.set_chamber_valves(chamber_index, False, False)
            
            # Short delay between iterations
            time.sleep(0.1)
        
        # Ensure all valves are closed after regulation
        for chamber in self.chamber_states:
            if chamber.enabled:
                self.valve_controller.set_chamber_valves(chamber.chamber_index, False, False)
        
        # Check if regulation was successful
        if self._check_stop_requested():
            return False
            
        all_regulated = all(ch.regulated for ch in self.chamber_states if ch.enabled)
        
        self.logger.info("Regulation phase complete" if all_regulated else "Regulation phase incomplete")
        return all_regulated
    
    def _run_stabilization_phase(self) -> bool:
        """
        Execute the pressure stabilization phase for all enabled chambers.
        
        Returns:
            bool: True if stabilization was successful, False otherwise
        """
        self.test_phase = "stabilizing"
        self.test_state = "STABILIZING"
        self._update_status("Stabilizing pressure...")
        
        # Initialize stabilization readings for all chambers
        stabilization_readings = {ch.chamber_index: [] for ch in self.chamber_states if ch.enabled}
        
        # Stabilize all chambers concurrently
        start_time = time.time()
        stability_duration = TIME_DEFAULTS['STABILIZATION_TIME']
        
        all_stable = False
        
        while not all_stable and not self._check_stop_requested():
            # Calculate phase progress for UI
            elapsed = time.time() - start_time
            if elapsed > stability_duration:
                break  # Continue to test phase even if not all chambers are perfectly stable
                
            phase_progress = elapsed / stability_duration
            self._update_progress("stabilizing", 0.3 + 0.1 * phase_progress, {
                "elapsed_time": elapsed,
                "duration": stability_duration
            })
            
            # Check stability for all enabled chambers
            all_stable = True
            for chamber in self.chamber_states:
                if not chamber.enabled or not chamber.regulated:
                    continue
                    
                chamber_index = chamber.chamber_index
                current_pressure = chamber.current_pressure
                
                # Store reading for stability calculation
                readings = stabilization_readings[chamber_index]
                readings.append(current_pressure)
                if len(readings) > 50:
                    readings.pop(0)
                
                # Calculate stability once we have enough readings
                if len(readings) >= 20:
                    mean_pressure = sum(readings[-20:]) / 20
                    max_deviation = max(abs(p - mean_pressure) for p in readings[-20:])
                    if max_deviation > chamber.pressure_tolerance:
                        all_stable = False
                else:
                    all_stable = False
            
            # Short delay between iterations
            time.sleep(0.1)
        
        # Mark all chambers as stabilized
        for chamber in self.chamber_states:
            if chamber.enabled and chamber.regulated:
                chamber.stabilized = True
                chamber.start_pressure = chamber.current_pressure
        
        # Proceed even if not perfectly stable
        self.logger.info("Stabilization phase complete" + (" (all stable)" if all_stable else " (timeout)"))
        return True
    
    def _run_testing_phase(self) -> bool:
        """
        Execute the main testing phase for all enabled chambers.
        
        Returns:
            bool: True if testing was successful, False otherwise
        """
        self.test_phase = "testing"
        self.test_state = "TESTING"
        self._update_status("Test in progress...")
        
        # Start test timer
        start_time = time.time()
        test_duration = self.test_duration
        
        # Main test loop
        while self.elapsed_time < test_duration and not self._check_stop_requested():
            # Update elapsed time
            current_time = time.time()
            self.elapsed_time = current_time - start_time
            
            # Calculate phase progress for UI
            phase_progress = self.elapsed_time / test_duration
            self._update_progress("testing", 0.4 + 0.4 * phase_progress, {
                "elapsed_time": self.elapsed_time,
                "total_time": test_duration
            })
            
            # Monitor all enabled chambers
            for chamber in self.chamber_states:
                if not chamber.enabled or not chamber.stabilized:
                    continue
                    
                # Record pressure reading
                chamber.pressure_readings.append(chamber.current_pressure)
                
                # Check if pressure is below threshold
                if chamber.current_pressure < chamber.pressure_threshold:
                    chamber.result = False
            
            # Short delay between iterations
            time.sleep(0.1)
        
        # Calculate final result for each chamber
        for chamber in self.chamber_states:
            if chamber.enabled and chamber.stabilized:
                chamber.tested = True
                chamber.final_pressure = chamber.current_pressure
                
                # Default result is pass unless pressure dropped below threshold
                if not hasattr(chamber, 'result') or chamber.result is None:
                    chamber.result = True
        
        # Check if test was successful (not stopped)
        result = not self._check_stop_requested()
        
        self.logger.info("Testing phase complete" if result else "Testing phase interrupted")
        return result
    
    def _run_emptying_phase(self) -> bool:
        """
        Execute the emptying phase for all chambers.
        
        Returns:
            bool: True if emptying was successful, False otherwise
        """
        self.test_phase = "emptying"
        self.test_state = "EMPTYING"
        self._update_status("Emptying chambers...")
        
        emptying_start = time.time()
        empty_timeout = TIME_DEFAULTS['EMPTY_TIME']  # Maximum time for emptying
        
        # First close all inlet valves to prevent refilling
        for chamber in self.chamber_states:
            if chamber.enabled:
                # Safety first - close inlet valve
                try:
                    self.valve_controller.set_inlet_valve(chamber.chamber_index, False)
                except Exception as e:
                    self.logger.error(f"Error closing inlet valve for chamber {chamber.chamber_index + 1}: {e}")
        
        time.sleep(0.2)  # Short delay to ensure inlets are closed
        
        # Now open all outlet valves
        for chamber in self.chamber_states:
            if chamber.enabled:
                try:
                    # Open outlet and empty valves to empty the chamber
                    self.valve_controller.empty_chamber(chamber.chamber_index)
                except Exception as e:
                    self.logger.error(f"Error opening outlet valves for chamber {chamber.chamber_index + 1}: {e}")
        
        # Monitor emptying progress
        while time.time() - emptying_start < empty_timeout:
            # Calculate phase progress for UI
            elapsed = time.time() - emptying_start
            phase_progress = elapsed / empty_timeout
            self._update_progress("emptying", 0.8 + 0.2 * phase_progress, {
                "elapsed_time": elapsed,
                "total_time": empty_timeout
            })
            
            # Check if all chambers are emptied
            all_empty = True
            for chamber in self.chamber_states:
                if chamber.enabled and chamber.current_pressure > 10:  # 10 mbar threshold
                    all_empty = False
                    break
            
            if all_empty:
                self.logger.info("All chambers emptied successfully")
                break
                
            time.sleep(0.1)
        
        # Ensure all valves are closed (cleanup)
        for chamber in self.chamber_states:
            if chamber.enabled:
                try:
                    self.valve_controller.stop_chamber(chamber.chamber_index)
                except Exception as e:
                    self.logger.error(f"Error closing valves for chamber {chamber.chamber_index + 1}: {e}")
        
        return True
    
    def _process_results(self, success: bool) -> None:
        """
        Process and report test results.
        
        Args:
            success: Whether the test process was successful
        """
        # Check if any results to process
        if not success:
            self.test_state = "STOPPED" if self._stop_requested else "ERROR"
            self._update_status("Test stopped" if self._stop_requested else "Test error")
            return
        
        # Calculate overall result
        overall_result = True
        for chamber in self.chamber_states:
            if chamber.enabled:
                if not chamber.tested or not chamber.result:
                    overall_result = False
                    break
        
        # Update test state
        self.test_state = "COMPLETE"
        result_text = "PASS" if overall_result else "FAIL"
        self._update_status(f"Test complete - {result_text}")
        
        # Prepare result data
        test_data = []
        for chamber in self.chamber_states:
            if chamber.enabled:
                chamber_data = {
                    'chamber_id': chamber.chamber_index,
                    'enabled': chamber.enabled,
                    'pressure_target': chamber.pressure_target,
                    'pressure_threshold': chamber.pressure_threshold,
                    'pressure_tolerance': chamber.pressure_tolerance,
                    'final_pressure': chamber.final_pressure,
                    'result': 'PASS' if chamber.result else 'FAIL',
                    'reference': self.current_reference if self.test_mode == "reference" else "N/A"
                }
                test_data.append(chamber_data)
        
        # Log the results
        if self.test_logger:
            log_data = {
                'timestamp': datetime.now(),
                'reference': self.current_reference if self.test_mode == "reference" else "N/A",
                'test_mode': self.test_mode,
                'test_duration': self.test_duration,
                'overall_result': overall_result,
                'chambers': []
            }
            
            for chamber in self.chamber_states:
                if chamber.enabled:
                    chamber_log = {
                        'chamber_id': chamber.chamber_index,
                        'enabled': chamber.enabled,
                        'pressure_target': chamber.pressure_target,
                        'pressure_threshold': chamber.pressure_threshold,
                        'pressure_tolerance': chamber.pressure_tolerance,
                        'final_pressure': chamber.final_pressure,
                        'result': chamber.result
                    }
                    
                    # Add pressure log (down-sampled if needed)
                    if chamber.pressure_readings:
                        if len(chamber.pressure_readings) > 100:
                            # Sample the pressure log to reduce size
                            sample_step = len(chamber.pressure_readings) // 100
                            chamber_log['pressure_log'] = chamber.pressure_readings[::sample_step][:100]
                        else:
                            chamber_log['pressure_log'] = chamber.pressure_readings
                    
                    log_data['chambers'].append(chamber_log)
            
            self.test_logger.log_test_result(log_data)
        
        # Print results if printer is available and all chambers passed
        if self.printer_manager and overall_result:
            self.printer_manager.print_test_results(test_data)
        
        # Notify UI of results
        if self.result_callback:
            self.result_callback(overall_result, test_data)
        
        self.logger.info(f"Test completed with result: {result_text}")
    
    def _start_monitoring(self) -> None:
        """Start the pressure monitoring thread."""
        if self._monitoring_running:
            return
            
        self._monitoring_running = True
        self.monitoring_thread = threading.Thread(target=self._monitor_pressure, daemon=True)
        self.monitoring_thread.start()
        self.logger.debug("Pressure monitoring started")
    
    def _stop_monitoring(self) -> None:
        """Stop the pressure monitoring thread."""
        self._monitoring_running = False
        if self.monitoring_thread:
            try:
                self.monitoring_thread.join(timeout=1.0)
            except:
                pass
            self.monitoring_thread = None
            self.logger.debug("Pressure monitoring stopped")
    
    def _monitor_pressure(self) -> None:
        """Continuous pressure monitoring thread function."""
        while self._monitoring_running and self.running_test:
            try:
                # Read pressures from sensor
                pressures = self.pressure_sensor.read_all_pressures()
                
                # Update chamber states
                for i, pressure in enumerate(pressures):
                    if i < len(self.chamber_states):
                        if pressure is not None:
                            self.chamber_states[i].current_pressure = pressure
            except Exception as e:
                self.logger.error(f"Error monitoring pressure: {e}")
            
            # Short delay between readings
            time.sleep(0.1)
    
    def get_enabled_chambers(self) -> List[int]:
        """
        Get the indices of all enabled chambers.
        
        Returns:
            List of chamber indices (0-based)
        """
        return [ch.chamber_index for ch in self.chamber_states if ch.enabled]
    
    def reset_test(self) -> None:
        """Reset test state to prepare for a new test."""
        # Stop any running test
        if self.running_test:
            self.stop_test()
            # Wait for test to stop
            while self.running_test:
                time.sleep(0.1)
        
        # Reset state variables
        self.test_state = "IDLE"
        self.test_phase = None
        self.elapsed_time = 0.0
        self._stop_requested = False
        
        # Reset chamber states
        for chamber in self.chamber_states:
            chamber.reset()
        
        self._update_status("System ready")
        self.logger.info("Test reset")
    
    def serialize_test_config(self) -> Dict[str, Any]:
        """
        Serialize the current test configuration.
        
        Returns:
            Dictionary with test configuration
        """
        chamber_configs = []
        for chamber in self.chamber_states:
            chamber_configs.append({
                'index': chamber.chamber_index,
                'enabled': chamber.enabled,
                'pressure_target': chamber.pressure_target,
                'pressure_threshold': chamber.pressure_threshold,
                'pressure_tolerance': chamber.pressure_tolerance
            })
            
        return {
            'test_mode': self.test_mode,
            'reference': self.current_reference,
            'test_duration': self.test_duration,
            'chambers': chamber_configs
        }
    
    def load_test_config(self, config: Dict[str, Any]) -> bool:
        """
        Load test configuration from serialized dictionary.
        
        Args:
            config: Dictionary with test configuration
            
        Returns:
            bool: True if configuration was loaded successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot load configuration during active test")
            return False
            
        try:
            # Load test mode and duration
            if 'test_mode' in config:
                mode = config['test_mode']
                if mode in ["manual", "reference"]:
                    self.test_mode = mode
                else:
                    self.logger.error(f"Invalid test mode in config: {mode}")
                    return False
            
            if 'reference' in config:
                self.current_reference = config['reference']
            
            if 'test_duration' in config:
                duration = int(config['test_duration'])
                if duration > 0:
                    self.test_duration = duration
                else:
                    self.logger.error(f"Invalid test duration in config: {duration}")
                    return False
            
            # Load chamber configurations
            if 'chambers' in config:
                chamber_configs = config['chambers']
                for chamber_config in chamber_configs:
                    index = chamber_config.get('index')
                    if not 0 <= index <= 2:
                        self.logger.error(f"Invalid chamber index in config: {index}")
                        continue
                        
                    chamber = self.chamber_states[index]
                    
                    if 'enabled' in chamber_config:
                        chamber.enabled = bool(chamber_config['enabled'])
                        
                    if 'pressure_target' in chamber_config:
                        target = float(chamber_config['pressure_target'])
                        if target > 0:
                            chamber.pressure_target = target
                        else:
                            self.logger.error(f"Invalid target pressure in config: {target}")
                            return False
                            
                    if 'pressure_threshold' in chamber_config:
                        threshold = float(chamber_config['pressure_threshold'])
                        if threshold > 0:
                            chamber.pressure_threshold = threshold
                        else:
                            self.logger.error(f"Invalid threshold pressure in config: {threshold}")
                            return False
                            
                    if 'pressure_tolerance' in chamber_config:
                        tolerance = float(chamber_config['pressure_tolerance'])
                        if tolerance > 0:
                            chamber.pressure_tolerance = tolerance
                        else:
                            self.logger.error(f"Invalid pressure tolerance in config: {tolerance}")
                            return False
            
            self.logger.info("Test configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading test configuration: {e}")
            return False
    
    def reload_reference(self) -> bool:
        """
        Reload current reference from database.
        
        Returns:
            bool: True if reference was reloaded successfully, False otherwise
        """
        if self.test_mode != "reference" or not self.current_reference:
            return False
            
        return self.set_test_mode("reference", self.current_reference)
    
    def get_last_test_result(self) -> Optional[Dict[str, Any]]:
        """
        Get the result of the last test.
        
        Returns:
            Dictionary with test result or None if no test has been run
        """
        if not self.test_logger:
            return None
            
        recent_tests = self.test_logger.get_recent_tests(1)
        if not recent_tests:
            return None
            
        return recent_tests[0]
    
    def update_settings_from_dict(self, settings: Dict[str, Any]) -> bool:
        """
        Update test settings from a dictionary.
        
        Args:
            settings: Dictionary with settings to update
            
        Returns:
            bool: True if settings were updated successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot update settings during active test")
            return False
            
        try:
            # Update test duration if provided
            if 'test_duration' in settings:
                duration = int(settings['test_duration'])
                if duration > 0:
                    self.test_duration = duration
                else:
                    self.logger.error(f"Invalid test duration: {duration}")
                    return False
            
            # Update chamber settings if provided
            for i in range(3):
                chamber_key = f'chamber{i+1}'
                if chamber_key in settings:
                    chamber_settings = settings[chamber_key]
                    chamber = self.chamber_states[i]
                    
                    if 'enabled' in chamber_settings:
                        chamber.enabled = bool(chamber_settings['enabled'])
                        
                    if 'pressure_target' in chamber_settings:
                        target = float(chamber_settings['pressure_target'])
                        if 0 < target <= PRESSURE_DEFAULTS['MAX_PRESSURE']:
                            chamber.pressure_target = target
                        else:
                            self.logger.error(f"Invalid target pressure for {chamber_key}: {target}")
                            return False
                            
                    if 'pressure_threshold' in chamber_settings:
                        threshold = float(chamber_settings['pressure_threshold'])
                        if threshold > 0:
                            chamber.pressure_threshold = threshold
                        else:
                            self.logger.error(f"Invalid threshold pressure for {chamber_key}: {threshold}")
                            return False
                            
                    if 'pressure_tolerance' in chamber_settings:
                        tolerance = float(chamber_settings['pressure_tolerance'])
                        if tolerance > 0:
                            chamber.pressure_tolerance = tolerance
                        else:
                            self.logger.error(f"Invalid pressure tolerance for {chamber_key}: {tolerance}")
                            return False
            
            self.logger.info("Test settings updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating test settings: {e}")
            return False
    
    def manual_control_chamber(self, chamber_index: int, control_action: str) -> bool:
        """
        Manually control a specific chamber (for maintenance and calibration).
        
        Args:
            chamber_index: Index of the chamber (0-2)
            control_action: Control action ('fill', 'empty', 'stop')
            
        Returns:
            bool: True if control action was performed successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot perform manual control during active test")
            return False
            
        if not 0 <= chamber_index <= 2:
            self.logger.error(f"Invalid chamber index: {chamber_index}")
            return False
            
        try:
            if control_action == 'fill':
                return self.valve_controller.fill_chamber(chamber_index)
            elif control_action == 'empty':
                return self.valve_controller.empty_chamber(chamber_index)
            elif control_action == 'stop':
                return self.valve_controller.stop_chamber(chamber_index)
            else:
                self.logger.error(f"Unknown control action: {control_action}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error controlling chamber {chamber_index}: {e}")
            return False
    
    def pulse_valve(self, chamber_index: int, valve_type: str, duration: float = 0.1) -> bool:
        """
        Pulse a valve open for a short duration (for fine control during calibration).
        
        Args:
            chamber_index: Index of the chamber (0-2)
            valve_type: Type of valve ('inlet', 'outlet')
            duration: Duration to keep the valve open in seconds
            
        Returns:
            bool: True if pulse was performed successfully, False otherwise
        """
        if self.running_test:
            self.logger.error("Cannot pulse valve during active test")
            return False
            
        if not 0 <= chamber_index <= 2:
            self.logger.error(f"Invalid chamber index: {chamber_index}")
            return False
            
        if valve_type not in ['inlet', 'outlet']:
            self.logger.error(f"Invalid valve type: {valve_type}")
            return False
            
        try:
            return self.valve_controller.pulse_valve(chamber_index, valve_type, duration)
        except Exception as e:
            self.logger.error(f"Error pulsing {valve_type} valve for chamber {chamber_index}: {e}")
            return False
    
    def export_test_results(self, path: Optional[str] = None) -> bool:
        """
        Export test results to CSV file.
        
        Args:
            path: Optional path to save the CSV file
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        if not self.test_logger:
            self.logger.error("Test logger not available for export")
            return False
            
        try:
            return self.test_logger.save_to_csv(path)
        except Exception as e:
            self.logger.error(f"Error exporting test results: {e}")
            return False
    
    def get_detailed_test_report(self, include_pressure_logs: bool = True) -> Dict[str, Any]:
        """
        Generate a detailed test report for the last completed test.
        
        Args:
            include_pressure_logs: Whether to include pressure log data
            
        Returns:
            Dictionary with detailed test report
        """
        if self.test_state != "COMPLETE":
            return {"error": "No completed test available"}
        
        try:
            # Build detailed report
            report = {
                'test_mode': self.test_mode,
                'reference': self.current_reference if self.test_mode == "reference" else "N/A",
                'test_duration': self.test_duration,
                'timestamp': datetime.now().isoformat(),
                'chambers': []
            }
            
            # Calculate overall result
            overall_result = True
            for chamber in self.chamber_states:
                if chamber.enabled:
                    if not chamber.tested or not chamber.result:
                        overall_result = False
                        break
            
            report['overall_result'] = "PASS" if overall_result else "FAIL"
            
            # Add chamber-specific details
            for chamber in self.chamber_states:
                if not chamber.enabled:
                    continue
                    
                chamber_report = {
                    'chamber_id': chamber.chamber_index + 1,  # 1-based for display
                    'pressure_target': chamber.pressure_target,
                    'pressure_threshold': chamber.pressure_threshold,
                    'pressure_tolerance': chamber.pressure_tolerance,
                    'start_pressure': chamber.start_pressure,
                    'final_pressure': chamber.final_pressure,
                    'pressure_drop': chamber.start_pressure - chamber.final_pressure,
                    'result': "PASS" if chamber.result else "FAIL"
                }
                
                # Add pressure logs if requested
                if include_pressure_logs and chamber.pressure_readings:
                    chamber_report['pressure_readings'] = chamber.pressure_readings
                
                report['chambers'].append(chamber_report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating test report: {e}")
            return {"error": str(e)}
    
    def emergency_stop(self) -> bool:
        """
        Perform an emergency stop of the test system.
        
        Returns:
            bool: True if emergency stop was successful, False otherwise
        """
        try:
            # First request normal stop
            self._stop_requested = True
            self.test_state = "EMERGENCY"
            self.running_test = False
            
            # Immediately close all valves
            for chamber_index in range(3):
                try:
                    self.valve_controller.stop_chamber(chamber_index)
                except Exception as e:
                    self.logger.error(f"Error stopping chamber {chamber_index} during emergency: {e}")
            
            # Stop monitoring thread
            self._stop_monitoring()
            
            self.logger.warning("Emergency stop executed")
            self._update_status("Emergency stop executed")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
            return False