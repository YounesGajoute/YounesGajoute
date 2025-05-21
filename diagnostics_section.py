#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnostics Section module for the Multi-Chamber Test application.

This module provides the DiagnosticsSection class that implements system
diagnostic features including hardware tests, resource monitoring,
and peripheral verification.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import time
import weakref
import os
import platform
import queue
import psutil
from typing import Dict, Any, List, Optional, Callable, Union, Tuple

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS, GPIO_PINS
from multi_chamber_test.hardware.pressure_sensor import PressureSensor
from multi_chamber_test.hardware.printer import PrinterManager
from multi_chamber_test.hardware.gpio_manager import GPIOManager
from multi_chamber_test.ui.settings.base_section import BaseSection


class DiagnosticsSection(BaseSection):
    """
    Diagnostics interface section for hardware testing and system monitoring.
    
    This class implements various diagnostic features including ADC/pressure sensor 
    testing, I2C bus verification, system memory monitoring, printer testing,
    and GPIO testing with visual feedback.
    """
    
    def __init__(self, parent, master_tab, pressure_sensor=None, gpio_manager=None, printer_manager=None):
        """
        Initialize the DiagnosticsSection with parent frame and hardware components.
        
        Args:
            parent: Parent frame to contain the section
            master_tab: Master tab controlling this section
            pressure_sensor: Optional PressureSensor instance for ADC tests
            gpio_manager: Optional GPIOManager for GPIO testing
            printer_manager: Optional PrinterManager for printer tests
        """
        super().__init__(parent, master_tab, "Diagnostics & Testing")
        
        # Store hardware components (with weak references to avoid circular references)
        self.pressure_sensor = weakref.proxy(pressure_sensor) if pressure_sensor else None
        self.gpio_manager = weakref.proxy(gpio_manager) if gpio_manager else None
        self.printer_manager = weakref.proxy(printer_manager) if printer_manager else None
        
        # Status variables
        self.adc_status = tk.StringVar(value="Not Tested")
        self.i2c_status = tk.StringVar(value="Not Tested")
        self.memory_status = tk.StringVar(value="Not Tested")
        self.printer_status = tk.StringVar(value="Not Tested")
        self.gpio_status = tk.StringVar(value="Not Tested")
        
        # Resource monitoring
        self.system_load = tk.StringVar(value="--")
        self.memory_usage = tk.StringVar(value="--")
        self.disk_usage = tk.StringVar(value="--")
        
        # Thread management
        self._monitoring_active = False
        self._monitoring_thread = None
        self._ui_update_queue = queue.Queue()
        
        # GPIO testing
        self.gpio_pins = {}
        self.selected_pin = tk.StringVar()
        self.pin_mode = tk.StringVar(value="output")
        self.output_state = tk.BooleanVar(value=False)
        self.input_state = tk.StringVar(value="--")
        
        # Build the interface
        self._build_interface()
        
    def _build_interface(self):
        """Build the diagnostic section interface."""
        # Main container with scrolling
        self.scrollable_frame = ttk.Frame(self.content_frame)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System Info Card
        self._build_system_info_card()
        
        # Hardware tests cards
        self._build_adc_test_card()
        self._build_i2c_test_card()
        self._build_printer_test_card()
        self._build_gpio_test_card()
        
        # Memory and resource monitor card
        self._build_resource_monitor_card()
        
    def _build_system_info_card(self):
        """Build the system information card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="System Information")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # System info container
        info_frame = ttk.Frame(card, padding=10)
        info_frame.pack(fill=tk.X)
        
        # Populate with system information
        system_info = self._get_system_info()
        
        row = 0
        for label, value in system_info.items():
            ttk.Label(
                info_frame, 
                text=f"{label}:", 
                style="Bold.TLabel"
            ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            
            ttk.Label(
                info_frame, 
                text=value
            ).grid(row=row, column=1, sticky="w", pady=2)
            
            row += 1
    
    def _build_adc_test_card(self):
        """Build the ADC/pressure sensor test card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="ADC/Pressure Sensor Test")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # ADC test container
        test_frame = ttk.Frame(card, padding=10)
        test_frame.pack(fill=tk.X)
        
        # Status and test control
        ttk.Label(
            test_frame, 
            text="Status:"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            test_frame, 
            textvariable=self.adc_status,
            width=20
        ).grid(row=0, column=1, sticky="w", pady=5)
        
        # Create a frame for ADC readings
        self.adc_readings_frame = ttk.Frame(test_frame)
        self.adc_readings_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        
        # Readings will be populated during testing
        self.adc_value_labels = []
        for i in range(3):  # For 3 chambers
            ttk.Label(
                self.adc_readings_frame,
                text=f"Chamber {i+1}:"
            ).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=2)
            
            value_label = ttk.Label(
                self.adc_readings_frame,
                text="--"
            )
            value_label.grid(row=i, column=1, sticky="w", pady=2)
            self.adc_value_labels.append(value_label)
        
        # Test button
        ttk.Button(
            test_frame,
            text="Test ADC",
            command=self.run_adc_test,
            width=15
        ).grid(row=0, column=2, rowspan=1, padx=10, pady=5)
        
    def _build_i2c_test_card(self):
        """Build the I2C bus test card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="I2C Bus Test")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # I2C test container
        test_frame = ttk.Frame(card, padding=10)
        test_frame.pack(fill=tk.X)
        
        # Status and test control
        ttk.Label(
            test_frame, 
            text="Status:"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            test_frame, 
            textvariable=self.i2c_status,
            width=20
        ).grid(row=0, column=1, sticky="w", pady=5)
        
        # Results frame
        self.i2c_results_frame = ttk.Frame(test_frame)
        self.i2c_results_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        
        # Initially hide results
        self.i2c_device_labels = []
        
        # Test button
        ttk.Button(
            test_frame,
            text="Scan I2C Bus",
            command=self.run_i2c_test,
            width=15
        ).grid(row=0, column=2, padx=10, pady=5)
    
    def _build_printer_test_card(self):
        """Build the printer test card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="Printer Test")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # Printer test container
        test_frame = ttk.Frame(card, padding=10)
        test_frame.pack(fill=tk.X)
        
        # Status and test control
        ttk.Label(
            test_frame, 
            text="Status:"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            test_frame, 
            textvariable=self.printer_status,
            width=20
        ).grid(row=0, column=1, sticky="w", pady=5)
        
        # Test connection button
        ttk.Button(
            test_frame,
            text="Test Connection",
            command=self.test_printer_connection,
            width=15
        ).grid(row=0, column=2, padx=10, pady=5)
        
        # Print test page button
        ttk.Button(
            test_frame,
            text="Print Test Page",
            command=self.print_test_page,
            width=15
        ).grid(row=0, column=3, padx=10, pady=5)
        
    def _build_gpio_test_card(self):
        """Build the GPIO test card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="GPIO Test")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # GPIO test container
        test_frame = ttk.Frame(card, padding=10)
        test_frame.pack(fill=tk.X)
        
        # Status and test control
        ttk.Label(
            test_frame, 
            text="Status:"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            test_frame, 
            textvariable=self.gpio_status,
            width=20
        ).grid(row=0, column=1, sticky="w", pady=5)
        
        # PIN selection
        ttk.Label(
            test_frame, 
            text="Select PIN:"
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        
        # Create pin selection dropdown with all available pins
        if self.gpio_manager:
            pin_labels = []
            self.gpio_pins = {}
            
            # Add inlet pins
            for i, pin in enumerate(GPIO_PINS["INLET_PINS"]):
                pin_label = f"INLET {i+1} (BCM {pin})"
                pin_labels.append(pin_label)
                self.gpio_pins[pin_label] = pin

            # Add outlet pins
            for i, pin in enumerate(GPIO_PINS["OUTLET_PINS"]):
                pin_label = f"OUTLET {i+1} (BCM {pin})"
                pin_labels.append(pin_label)
                self.gpio_pins[pin_label] = pin
                
            # Add other pins if they exist
            for pin_name in ["START_BTN", "STOP_BTN", "STATUS_LED_GREEN", "STATUS_LED_RED", "STATUS_LED_YELLOW"]:
                if pin_name in GPIO_PINS:
                    pin = GPIO_PINS[pin_name]
                    pin_label = f"{pin_name} (BCM {pin})"
                    pin_labels.append(pin_label)
                    self.gpio_pins[pin_label] = pin
                
            # Create dropdown
            self.pin_dropdown = ttk.Combobox(
                test_frame,
                textvariable=self.selected_pin,
                values=pin_labels,
                state="readonly",
                width=25
            )
            self.pin_dropdown.grid(row=1, column=1, sticky="w", pady=5)
            
            # Default selection
            if pin_labels:
                self.selected_pin.set(pin_labels[0])
                
            # Mode selection (Input/Output)
            ttk.Label(
                test_frame, 
                text="Pin Mode:"
            ).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
            
            ttk.Radiobutton(
                test_frame,
                text="Output",
                variable=self.pin_mode,
                value="output",
                command=self._on_pin_mode_changed
            ).grid(row=2, column=1, sticky="w", pady=5)
            
            ttk.Radiobutton(
                test_frame,
                text="Input",
                variable=self.pin_mode,
                value="input",
                command=self._on_pin_mode_changed
            ).grid(row=2, column=1, sticky="e", pady=5)
            
            # Output state (for output mode)
            self.output_frame = ttk.Frame(test_frame)
            self.output_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
            
            ttk.Label(
                self.output_frame, 
                text="Output State:"
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Checkbutton(
                self.output_frame,
                text="HIGH",
                variable=self.output_state,
                command=self._set_output_state
            ).pack(side=tk.LEFT)
            
            # Input state (for input mode)
            self.input_frame = ttk.Frame(test_frame)
            self.input_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
            
            ttk.Label(
                self.input_frame, 
                text="Input State:"
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Label(
                self.input_frame,
                textvariable=self.input_state,
                width=8
            ).pack(side=tk.LEFT)
            
            # Initially show/hide based on selected mode
            self._on_pin_mode_changed()
            
            # Test button
            ttk.Button(
                test_frame,
                text="Initialize Test",
                command=self.initialize_gpio_test,
                width=15
            ).grid(row=1, column=2, padx=10, pady=5)
            
        else:
            # GPIO manager not available
            ttk.Label(
                test_frame,
                text="GPIO Manager not available",
                foreground=UI_COLORS["ERROR"]
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
    
    def _build_resource_monitor_card(self):
        """Build the resource monitoring card."""
        card = ttk.LabelFrame(self.scrollable_frame, text="System Resources")
        card.pack(fill=tk.X, pady=(0, 10))
        
        # Resource monitor container
        monitor_frame = ttk.Frame(card, padding=10)
        monitor_frame.pack(fill=tk.X)
        
        # System load
        ttk.Label(
            monitor_frame, 
            text="System Load:"
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            monitor_frame, 
            textvariable=self.system_load,
            width=20
        ).grid(row=0, column=1, sticky="w", pady=5)
        
        # Memory usage
        ttk.Label(
            monitor_frame, 
            text="Memory Usage:"
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            monitor_frame, 
            textvariable=self.memory_usage,
            width=20
        ).grid(row=1, column=1, sticky="w", pady=5)
        
        # Disk usage
        ttk.Label(
            monitor_frame, 
            text="Disk Usage:"
        ).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        
        ttk.Label(
            monitor_frame, 
            textvariable=self.disk_usage,
            width=20
        ).grid(row=2, column=1, sticky="w", pady=5)
        
        # Update button
        ttk.Button(
            monitor_frame,
            text="Update Now",
            command=self.update_resource_monitor,
            width=15
        ).grid(row=0, column=2, rowspan=3, padx=10, pady=5)
    
    def _get_system_info(self) -> Dict[str, str]:
        """
        Get system information for display.
        
        Returns:
            Dictionary of system information
        """
        info = {}
        
        # Basic system info
        info["System"] = platform.system()
        info["Platform"] = platform.platform()
        info["Python Version"] = platform.python_version()
        
        # CPU info
        try:
            if platform.system() == "Linux":
                # Try to get CPU info from /proc/cpuinfo
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            info["CPU"] = line.split(":", 1)[1].strip()
                            break
            else:
                # Fallback
                import multiprocessing
                info["CPU"] = f"{multiprocessing.cpu_count()} cores"
        except Exception:
            info["CPU"] = "Unknown"
        
        # Try to get Raspberry Pi-specific info
        try:
            if os.path.exists("/sys/firmware/devicetree/base/model"):
                with open("/sys/firmware/devicetree/base/model", "r") as f:
                    info["Device"] = f.read().strip('\0')
        except Exception:
            pass
        
        # Application info
        info["Application"] = "Multi-Chamber Test"
        
        try:
            # Get uptime
            uptime_seconds = int(time.time() - psutil.boot_time())
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                info["Uptime"] = f"{days}d {hours}h {minutes}m"
            else:
                info["Uptime"] = f"{hours}h {minutes}m {seconds}s"
        except Exception:
            pass
            
        return info
    
    def run_adc_test(self):
        """Run ADC/pressure sensor test."""
        if not self.pressure_sensor:
            self.adc_status.set("Sensor Not Available")
            return
            
        # Start test in a separate thread to avoid blocking UI
        threading.Thread(target=self._run_adc_test_thread, daemon=True).start()
        
    def _run_adc_test_thread(self):
        """Background thread for ADC testing."""
        try:
            self.adc_status.set("Testing...")
            
            # Check if pressure sensor is initialized
            if not self.pressure_sensor.ensure_initialized():
                self._update_ui(lambda: self.adc_status.set("Failed: Not Initialized"))
                return
            
            # Check all three ADC channels (for the three chambers)
            success = True
            values = []
            
            for channel in range(3):
                # Read raw voltage
                voltage = self.pressure_sensor.read_voltage(channel)
                
                if voltage is None:
                    success = False
                    values.append("Error")
                else:
                    # Convert to pressure
                    pressure = self.pressure_sensor.read_pressure(channel)
                    values.append(f"{voltage:.3f}V ({pressure:.1f} mbar)")
            
            # Update UI
            def update_ui():
                for i, value in enumerate(values):
                    if i < len(self.adc_value_labels):
                        self.adc_value_labels[i].config(text=value)
                
                if success:
                    self.adc_status.set("OK")
                else:
                    self.adc_status.set("Failed")
            
            self._update_ui(update_ui)
                
        except Exception as e:
            # Update UI with error
            self._update_ui(lambda: self.adc_status.set(f"Error: {str(e)}"))
            
    def run_i2c_test(self):
        """Run I2C bus test."""
        # Start test in a separate thread to avoid blocking UI
        threading.Thread(target=self._run_i2c_test_thread, daemon=True).start()
        
    def _run_i2c_test_thread(self):
        """Background thread for I2C testing."""
        try:
            self.i2c_status.set("Scanning...")
            
            # Clear existing device labels
            self._update_ui(lambda: self._clear_i2c_results())
            
            # Try to access I2C bus and scan for devices
            import smbus
            
            # Try both bus 0 and 1 (RPi typically uses 1)
            devices = []
            
            for bus_num in [1, 0]:
                try:
                    bus = smbus.SMBus(bus_num)
                    
                    # Scan address range (3-119 is the valid 7-bit address range)
                    for addr in range(3, 120):
                        try:
                            bus.read_byte(addr)
                            # If no error, device exists
                            devices.append((bus_num, addr))
                        except:
                            # No device at this address
                            pass
                            
                    bus.close()
                except:
                    # Can't access this bus
                    pass
            
            # Update UI
            def update_ui():
                if not devices:
                    self.i2c_status.set("No Devices Found")
                    return
                    
                self.i2c_status.set(f"Found {len(devices)} device(s)")
                
                # Add devices to results frame
                for i, (bus_num, addr) in enumerate(devices):
                    label = ttk.Label(
                        self.i2c_results_frame,
                        text=f"Bus {bus_num}, Address 0x{addr:02X} ({addr})"
                    )
                    label.grid(row=i, column=0, sticky="w", pady=2)
                    self.i2c_device_labels.append(label)
                    
                    # Check for known devices
                    device_name = self._get_i2c_device_name(addr)
                    if device_name:
                        name_label = ttk.Label(
                            self.i2c_results_frame,
                            text=f"({device_name})"
                        )
                        name_label.grid(row=i, column=1, sticky="w", padx=10, pady=2)
                        self.i2c_device_labels.append(name_label)
            
            self._update_ui(update_ui)
                
        except Exception as e:
            # Update UI with error
            self._update_ui(lambda: self.i2c_status.set(f"Error: {str(e)}"))
            
    def _clear_i2c_results(self):
        """Clear I2C results display."""
        for label in self.i2c_device_labels:
            label.destroy()
        self.i2c_device_labels = []
            
    def _get_i2c_device_name(self, address: int) -> Optional[str]:
        """
        Get name of known I2C device at the given address.
        
        Args:
            address: I2C address
            
        Returns:
            Device name or None if unknown
        """
        # Common I2C addresses
        known_devices = {
            0x48: "ADS1115 ADC",
            0x49: "ADS1115 ADC (alt)",
            0x68: "DS1307 RTC / MPU6050",
            0x76: "BME280 Sensor",
            0x77: "BMP280 Sensor",
            0x3C: "SSD1306 OLED Display",
            0x20: "PCF8574 I/O Expander",
            0x70: "HT16K33 LED Driver"
        }
        
        return known_devices.get(address)
        
    def test_printer_connection(self):
        """Test printer connection."""
        if not self.printer_manager:
            self.printer_status.set("Printer Not Available")
            return
            
        # Start test in a separate thread to avoid blocking UI
        threading.Thread(target=self._test_printer_thread, daemon=True).start()
        
    def _test_printer_thread(self):
        """Background thread for printer connection testing."""
        try:
            self.printer_status.set("Testing...")
            
            # Check if printer is available
            if self.printer_manager.is_printer_available():
                # Try to connect
                if self.printer_manager.connect():
                    self._update_ui(lambda: self.printer_status.set("Connected"))
                    
                    # Clean up connection
                    self.printer_manager.close()
                else:
                    self._update_ui(lambda: self.printer_status.set("Connection Failed"))
            else:
                self._update_ui(lambda: self.printer_status.set("Not Found"))
                
        except Exception as e:
            # Update UI with error
            self._update_ui(lambda: self.printer_status.set(f"Error: {str(e)}"))
            
    def print_test_page(self):
        """Print a test page."""
        if not self.printer_manager:
            self.printer_status.set("Printer Not Available")
            return
        
        # Confirm print
        if not messagebox.askyesno("Print Test Page", "Do you want to print a test page?"):
            return
            
        # Start printing in a separate thread
        threading.Thread(target=self._print_test_page_thread, daemon=True).start()
        
    def _print_test_page_thread(self):
        """Background thread for printing test page."""
        try:
            self.printer_status.set("Printing...")
            
            # Print test page
            success = self.printer_manager.test_connection()
            
            if success:
                self._update_ui(lambda: self.printer_status.set("Print Complete"))
            else:
                self._update_ui(lambda: self.printer_status.set("Print Failed"))
                
        except Exception as e:
            # Update UI with error
            self._update_ui(lambda: self.printer_status.set(f"Error: {str(e)}"))
            
    def initialize_gpio_test(self):
        """Initialize and start GPIO test."""
        if not self.gpio_manager:
            self.gpio_status.set("GPIO Not Available")
            return
            
        # Get selected pin
        pin_label = self.selected_pin.get()
        if not pin_label or pin_label not in self.gpio_pins:
            messagebox.showerror("GPIO Test", "Please select a valid GPIO pin")
            return
            
        pin = self.gpio_pins[pin_label]
        mode = self.pin_mode.get()
        
        try:
            # Initialize GPIO
            if not self.gpio_manager.initialized:
                self.gpio_manager.initialize()
                
            # Set up pin based on selected mode
            if mode == "output":
                self.gpio_status.set("Setting up output...")
                self.gpio_manager.setup_pin(pin, self.gpio_manager.OUT, initial=self.output_state.get())
                self.gpio_status.set("Output Ready")
                
                # Update output state to match
                self._set_output_state()
                
            else:  # input mode
                self.gpio_status.set("Setting up input...")
                self.gpio_manager.setup_pin(pin, self.gpio_manager.IN, pull_up_down=self.gpio_manager.PUD_UP)
                self.gpio_status.set("Input Ready")
                
                # Start input monitoring
                self._start_input_monitoring(pin)
                
        except Exception as e:
            self.gpio_status.set(f"Error: {str(e)}")
            
    def _on_pin_mode_changed(self):
        """Handle pin mode change between input and output."""
        mode = self.pin_mode.get()
        
        if mode == "output":
            self.output_frame.grid()
            self.input_frame.grid_remove()
        else:  # input mode
            self.output_frame.grid_remove()
            self.input_frame.grid()
            
    def _set_output_state(self):
        """Set the output state of the selected pin."""
        if not self.gpio_manager or not self.gpio_manager.initialized:
            return
            
        pin_label = self.selected_pin.get()
        if not pin_label or pin_label not in self.gpio_pins:
            return
            
        pin = self.gpio_pins[pin_label]
        state = self.output_state.get()
        
        try:
            # Set output state
            self.gpio_manager.set_output(pin, state)
            self.gpio_status.set(f"Set to {'HIGH' if state else 'LOW'}")
        except Exception as e:
            self.gpio_status.set(f"Error: {str(e)}")
            
    def _start_input_monitoring(self, pin):
        """Start monitoring input state of the selected pin."""
        if not self.gpio_manager or not self.gpio_manager.initialized:
            return
            
        # Start in a separate thread
        threading.Thread(target=self._monitor_input_thread, args=(pin,), daemon=True).start()
        
    def _monitor_input_thread(self, pin):
        """Background thread for monitoring input state."""
        try:
            last_state = None
            
            while self._monitoring_active and self.pin_mode.get() == "input":
                # Read input state
                state = self.gpio_manager.read_input(pin)
                
                # Only update UI if state has changed
                if state != last_state:
                    last_state = state
                    state_text = "HIGH" if state else "LOW"
                    self._update_ui(lambda: self.input_state.set(state_text))
                
                # Short sleep to prevent high CPU usage
                time.sleep(0.1)
                
        except Exception as e:
            self._update_ui(lambda: self.input_state.set(f"Error: {str(e)}"))
            
    def update_resource_monitor(self):
        """Update system resource monitor display."""
        # Start in a separate thread to avoid blocking UI
        threading.Thread(target=self._update_resources_thread, daemon=True).start()
        
    def _update_resources_thread(self):
        """Background thread for resource monitoring updates."""
        try:
            # CPU load
            cpu_percent = psutil.cpu_percent(interval=0.5)
            self._update_ui(lambda: self.system_load.set(f"{cpu_percent:.1f}%"))
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used / (1024 * 1024)  # Convert to MB
            memory_total = memory.total / (1024 * 1024)  # Convert to MB
            
            self._update_ui(lambda: self.memory_usage.set(
                f"{memory_percent:.1f}% ({memory_used:.0f}/{memory_total:.0f} MB)"
            ))
            
            # Disk usage
            try:
                # Check root file system
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                disk_used = disk.used / (1024 * 1024 * 1024)  # Convert to GB
                disk_total = disk.total / (1024 * 1024 * 1024)  # Convert to GB
                
                self._update_ui(lambda: self.disk_usage.set(
                    f"{disk_percent:.1f}% ({disk_used:.1f}/{disk_total:.1f} GB)"
                ))
            except:
                self._update_ui(lambda: self.disk_usage.set("Not available"))
                
        except Exception as e:
            self._update_ui(lambda: self.system_load.set(f"Error: {str(e)}"))
    
    def _update_ui(self, update_func):
        """
        Queue UI update to be performed in the main thread.
        
        Args:
            update_func: Function to perform UI update
        """
        self._ui_update_queue.put(update_func)
        
        # If we're the main thread, process the update now
        if threading.current_thread() is threading.main_thread():
            self._process_ui_updates()
    
    def _process_ui_updates(self):
        """Process all pending UI updates from queue."""
        try:
            # Process all queued updates
            while not self._ui_update_queue.empty():
                update_func = self._ui_update_queue.get_nowait()
                update_func()
                self._ui_update_queue.task_done()
        except Exception as e:
            logging.error(f"Error processing UI updates: {e}")
    
    def _start_background_monitoring(self):
        """Start background monitoring thread for continuous updates."""
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            return  # Already running
            
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitoring_thread.start()
        
    def _monitoring_loop(self):
        """Background monitoring loop for continuous updates."""
        try:
            while self._monitoring_active:
                # Update resources periodically
                self._update_resources_thread()
                
                # Sleep between updates to prevent excessive resource usage
                time.sleep(5.0)
                
        except Exception as e:
            logging.error(f"Error in monitoring loop: {e}")
            
    def _stop_background_monitoring(self):
        """Stop background monitoring thread."""
        self._monitoring_active = False
        
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            try:
                self._monitoring_thread.join(timeout=1.0)
            except:
                pass
            
        self._monitoring_thread = None
    
    def on_section_selected(self):
        """Called when section is selected and becomes visible."""
        super().on_section_selected()
        
        # Start processing UI updates
        self.content_frame.after(100, self._process_ui_updates)
        
        # Schedule periodic UI update processing
        self._schedule_ui_processing()
        
        # Start background monitoring
        self._start_background_monitoring()
        
        # Update resources immediately
        self.update_resource_monitor()
        
    def _schedule_ui_processing(self):
        """Schedule periodic UI update processing."""
        if not self.is_selected:
            return
            
        # Process any pending UI updates
        self._process_ui_updates()
        
        # Schedule next update
        self.content_frame.after(100, self._schedule_ui_processing)
    
    def on_section_deselected(self):
        """Called when section is deselected and becomes hidden."""
        super().on_section_deselected()
        
        # Stop background monitoring
        self._stop_background_monitoring()
        
        # Clean up any ongoing tests
        self._cleanup_tests()
    
    def _cleanup_tests(self):
        """Clean up any ongoing tests when leaving the section."""
        # Stop input monitoring
        self._monitoring_active = False
        
        # Reset status displays
        self.adc_status.set("Not Tested")
        self.i2c_status.set("Not Tested")
        self.printer_status.set("Not Tested")
        self.gpio_status.set("Not Tested")
        
        # Clear test results
        for label in self.adc_value_labels:
            label.config(text="--")
            
        self._clear_i2c_results()
        
        # Reset GPIO pins used in testing
        if self.gpio_manager and self.gpio_manager.initialized:
            try:
                # Get the current pin if any
                pin_label = self.selected_pin.get()
                if pin_label and pin_label in self.gpio_pins:
                    pin = self.gpio_pins[pin_label]
                    
                    # Reset pin to safe state
                    if self.pin_mode.get() == "output":
                        self.gpio_manager.set_output(pin, False)
            except:
                pass
    
    def cleanup(self):
        """Clean up resources when closing the application."""
        # Stop monitoring
        self._stop_background_monitoring()
        
        # Clean up tests
        self._cleanup_tests()
        
        # Clear UI update queue
        while not self._ui_update_queue.empty():
            try:
                self._ui_update_queue.get_nowait()
                self._ui_update_queue.task_done()
            except:
                pass