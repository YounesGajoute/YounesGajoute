#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Physical Controls module for the Multi-Chamber Test application.

This module provides a PhysicalControls class for handling the interaction
with physical buttons (start/stop) and status LEDs, synchronizing their
state with the GUI.
"""

import logging
import threading
import time
from typing import Callable, Dict, Any, Optional

import RPi.GPIO as GPIO

from multi_chamber_test.config.constants import GPIO_PINS
from multi_chamber_test.hardware.gpio_manager import GPIOManager

class PhysicalControls:
    """
    Manager for physical buttons and LEDs.
    
    This class provides methods to handle physical start/stop buttons
    and status LEDs, synchronizing their state with the GUI and
    registering callbacks for button press events.
    """
    
    def __init__(self, gpio_manager: GPIOManager):
        """
        Initialize the PhysicalControls with a GPIO manager.
        
        Args:
            gpio_manager: Initialized GPIOManager instance
        """
        self.logger = logging.getLogger('PhysicalControls')
        self._setup_logger()
        
        self.gpio_manager = gpio_manager
        
        # Button pin definitions
        self.start_btn_pin = GPIO_PINS.get("START_BTN")
        self.stop_btn_pin = GPIO_PINS.get("STOP_BTN")
        
        # LED pin definitions
        self.start_led_pin = GPIO_PINS.get("STATUS_LED_GREEN")
        self.stop_led_pin = GPIO_PINS.get("STATUS_LED_RED")
        self.status_led_pin = GPIO_PINS.get("STATUS_LED_YELLOW")
        
        # Button press callbacks
        self.start_callback = None
        self.stop_callback = None
        
        # Button state
        self.start_btn_enabled = True
        self.stop_btn_enabled = False
        
        # Status LED states
        self.status_led_mode = None  # None, 'solid', 'blink-slow', 'blink-fast'
        self._blink_thread = None
        self._blink_running = False
        
        # Initialize if all required pins are available
        self.initialized = (self.start_btn_pin is not None and self.stop_btn_pin is not None and
                           self.start_led_pin is not None and self.stop_led_pin is not None)
    
    def _setup_logger(self):
        """Configure logging for the physical controls."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def setup(self) -> bool:
        """
        Set up the physical controls.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        if not self.initialized:
            self.logger.warning("One or more required GPIO pins not defined in constants. Physical controls not initialized.")
            return False
        
        try:
            # Set up button pins as inputs with pull-up
            self.gpio_manager.setup_pin(self.start_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.gpio_manager.setup_pin(self.stop_btn_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Set up LED pins as outputs
            self.gpio_manager.setup_pin(self.start_led_pin, GPIO.OUT, initial=GPIO.LOW)
            self.gpio_manager.setup_pin(self.stop_led_pin, GPIO.OUT, initial=GPIO.LOW)
            
            if self.status_led_pin:
                self.gpio_manager.setup_pin(self.status_led_pin, GPIO.OUT, initial=GPIO.LOW)
            
            # Update LED states based on initial button states
            self.sync_led_states()
            
            self.logger.info("Physical controls initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing physical controls: {e}")
            return False
    
    def register_start_callback(self, callback: Callable) -> bool:
        """
        Register a callback function for the start button press event.
        
        Args:
            callback: Function to call when start button is pressed
            
        Returns:
            bool: True if registration was successful, False otherwise
        """
        if not self.initialized:
            self.logger.warning("Physical controls not initialized. Cannot register callback.")
            return False
        
        try:
            self.start_callback = callback
            
            # Add event detection for falling edge (button press)
            success = self.gpio_manager.add_event_detect(
                self.start_btn_pin, 
                GPIO.FALLING, 
                callback=self._handle_start_button,
                bouncetime=300
            )
            
            if success:
                self.logger.info("Start button callback registered successfully")
            else:
                self.logger.error("Failed to register start button callback")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error registering start button callback: {e}")
            return False
    
    def register_stop_callback(self, callback: Callable) -> bool:
        """
        Register a callback function for the stop button press event.
        
        Args:
            callback: Function to call when stop button is pressed
            
        Returns:
            bool: True if registration was successful, False otherwise
        """
        if not self.initialized:
            self.logger.warning("Physical controls not initialized. Cannot register callback.")
            return False
        
        try:
            self.stop_callback = callback
            
            # Add event detection for falling edge (button press)
            success = self.gpio_manager.add_event_detect(
                self.stop_btn_pin, 
                GPIO.FALLING, 
                callback=self._handle_stop_button,
                bouncetime=300
            )
            
            if success:
                self.logger.info("Stop button callback registered successfully")
            else:
                self.logger.error("Failed to register stop button callback")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error registering stop button callback: {e}")
            return False
    
    def _handle_start_button(self, channel):
        """
        Internal handler for start button press events.
        
        Args:
            channel: GPIO channel that triggered the event
        """
        if not self.start_btn_enabled:
            self.logger.debug("Start button pressed but currently disabled")
            return
        
        self.logger.debug("Start button pressed")
        if self.start_callback:
            try:
                self.start_callback()
            except Exception as e:
                self.logger.error(f"Error in start button callback: {e}")
    
    def _handle_stop_button(self, channel):
        """
        Internal handler for stop button press events.
        
        Args:
            channel: GPIO channel that triggered the event
        """
        if not self.stop_btn_enabled:
            self.logger.debug("Stop button pressed but currently disabled")
            return
        
        self.logger.debug("Stop button pressed")
        if self.stop_callback:
            try:
                self.stop_callback()
            except Exception as e:
                self.logger.error(f"Error in stop button callback: {e}")
    
    def set_start_button_enabled(self, enabled: bool) -> bool:
        """
        Set the enabled state of the start button and update its LED.
        
        Args:
            enabled: Whether the start button should be enabled
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        if not self.initialized:
            return False
        
        try:
            self.start_btn_enabled = enabled
            
            # Update start button LED (ON when enabled, OFF when disabled)
            self.gpio_manager.set_output(
                self.start_led_pin, 
                GPIO.HIGH if enabled else GPIO.LOW
            )
            
            self.logger.debug(f"Start button {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting start button state: {e}")
            return False
    
    def set_stop_button_enabled(self, enabled: bool) -> bool:
        """
        Set the enabled state of the stop button and update its LED.
        
        Args:
            enabled: Whether the stop button should be enabled
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        if not self.initialized:
            return False
        
        try:
            self.stop_btn_enabled = enabled
            
            # Update stop button LED (ON when enabled, OFF when disabled)
            self.gpio_manager.set_output(
                self.stop_led_pin, 
                GPIO.HIGH if enabled else GPIO.LOW
            )
            
            self.logger.debug(f"Stop button {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting stop button state: {e}")
            return False
    
    def sync_led_states(self) -> bool:
        """
        Synchronize LED states with current button enabled states.
        
        Returns:
            bool: True if synchronization was successful, False otherwise
        """
        if not self.initialized:
            return False
        
        try:
            # Update start and stop LEDs to match button states
            self.gpio_manager.set_output(
                self.start_led_pin, 
                GPIO.HIGH if self.start_btn_enabled else GPIO.LOW
            )
            
            self.gpio_manager.set_output(
                self.stop_led_pin, 
                GPIO.HIGH if self.stop_btn_enabled else GPIO.LOW
            )
            
            self.logger.debug("LED states synchronized with button states")
            return True
            
        except Exception as e:
            self.logger.error(f"Error synchronizing LED states: {e}")
            return False
    
    def set_status_led(self, mode: Optional[str] = None) -> bool:
        """
        Set the status LED mode.
        
        Args:
            mode: LED mode ('solid', 'blink-slow', 'blink-fast', or None to turn off)
            
        Returns:
            bool: True if operation was successful, False otherwise
        """
        if not self.initialized or not self.status_led_pin:
            return False
        
        # Stop any existing blink thread
        self._stop_blink_thread()
        
        self.status_led_mode = mode
        
        try:
            if mode is None:
                # Turn off the LED
                self.gpio_manager.set_output(self.status_led_pin, GPIO.LOW)
                
            elif mode == 'solid':
                # Turn on the LED continuously
                self.gpio_manager.set_output(self.status_led_pin, GPIO.HIGH)
                
            elif mode.startswith('blink-'):
                # Start a new blink thread
                self._start_blink_thread(mode)
                
            else:
                self.logger.warning(f"Unknown status LED mode: {mode}")
                return False
                
            self.logger.debug(f"Status LED set to mode: {mode}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting status LED mode: {e}")
            return False
    
    def _start_blink_thread(self, mode: str):
        """
        Start a thread to blink the status LED.
        
        Args:
            mode: Blink mode ('blink-slow' or 'blink-fast')
        """
        if self._blink_thread and self._blink_thread.is_alive():
            self._stop_blink_thread()
        
        self._blink_running = True
        self._blink_thread = threading.Thread(
            target=self._blink_led,
            args=(mode,),
            daemon=True
        )
        self._blink_thread.start()
    
    def _stop_blink_thread(self):
        """Stop the LED blink thread if it's running."""
        self._blink_running = False
        if self._blink_thread and self._blink_thread.is_alive():
            self._blink_thread.join(timeout=1.0)
    
    def _blink_led(self, mode: str):
        """
        Blink the status LED at the specified rate.
        
        Args:
            mode: Blink mode ('blink-slow' or 'blink-fast')
        """
        # Determine blink interval based on mode
        interval = 0.5 if mode == 'blink-slow' else 0.2
        
        while self._blink_running:
            try:
                # Toggle the LED
                self.gpio_manager.set_output(self.status_led_pin, GPIO.HIGH)
                time.sleep(interval)
                
                if not self._blink_running:
                    break
                    
                self.gpio_manager.set_output(self.status_led_pin, GPIO.LOW)
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in blink thread: {e}")
                time.sleep(1.0)  # Slow down on error
    
    def check_button_state(self, button: str) -> Optional[bool]:
        """
        Check the current state of a physical button.
        
        Args:
            button: Button to check ('start' or 'stop')
            
        Returns:
            bool: True if button is pressed (active low), False if not pressed,
                  None if error or not initialized
        """
        if not self.initialized:
            return None
        
        try:
            if button.lower() == 'start':
                pin = self.start_btn_pin
            elif button.lower() == 'stop':
                pin = self.stop_btn_pin
            else:
                self.logger.error(f"Unknown button: {button}")
                return None
            
            # Buttons are active low (pulled up to HIGH when not pressed)
            state = self.gpio_manager.read_input(pin)
            if state is not None:
                return state == GPIO.LOW  # Convert to "is pressed" boolean
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking button state: {e}")
            return None
    
    def cleanup(self):
        """Clean up resources and stop any running threads."""
        self._stop_blink_thread()
        
        if self.initialized:
            try:
                # Turn off all LEDs
                if self.start_led_pin:
                    self.gpio_manager.set_output(self.start_led_pin, GPIO.LOW)
                    
                if self.stop_led_pin:
                    self.gpio_manager.set_output(self.stop_led_pin, GPIO.LOW)
                    
                if self.status_led_pin:
                    self.gpio_manager.set_output(self.status_led_pin, GPIO.LOW)
                    
                # Remove event detection
                if self.start_btn_pin:
                    self.gpio_manager.remove_event_detect(self.start_btn_pin)
                    
                if self.stop_btn_pin:
                    self.gpio_manager.remove_event_detect(self.stop_btn_pin)
                
                self.logger.info("Physical controls cleaned up")
                
            except Exception as e:
                self.logger.error(f"Error cleaning up physical controls: {e}")
