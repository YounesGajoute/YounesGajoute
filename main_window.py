#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Window module for the Multi-Chamber Test application.

This module provides the MainWindow class that initializes and manages
the application's main window, including tab switching, authentication,
and hardware component initialization.

Optimized for performance with improved tab switching, background loading,
and hardware buffering.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
import time
import threading
import queue
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
import atexit
import functools

# Fix PIL import
try:
    from PIL import Image, ImageTk
except ImportError:
    # Provide fallback for systems without PIL
    Image = None
    ImageTk = None

# Import configuration
from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS, UI_DIMENSIONS, LOGO_PATH
from multi_chamber_test.config.settings import SettingsManager

# Import hardware components
from multi_chamber_test.hardware.gpio_manager import GPIOManager
from multi_chamber_test.hardware.valve_controller import ValveController
from multi_chamber_test.hardware.pressure_sensor import PressureSensor
from multi_chamber_test.hardware.printer import PrinterManager
from multi_chamber_test.hardware.physical_controls import PhysicalControls

# Import core components
from multi_chamber_test.core.test_manager import TestManager
from multi_chamber_test.core.calibration_manager import CalibrationManager
from multi_chamber_test.core.logger import TestLogger
from multi_chamber_test.core.roles import get_role_manager, has_access, get_current_role

# Import database components
from multi_chamber_test.database.reference_db import ReferenceDatabase
from multi_chamber_test.database.calibration_db import CalibrationDatabase

# Import observer pattern utilities
from multi_chamber_test.utils.observers import enhance_test_manager, enhance_role_manager

# Import UI tabs
from multi_chamber_test.ui.tab_main import MainTab
from multi_chamber_test.ui.tab_settings import SettingsTab
from multi_chamber_test.ui.tab_calibration import CalibrationTab
from multi_chamber_test.ui.tab_reference import ReferenceTab
from multi_chamber_test.ui.password_dialog import PasswordDialog
from multi_chamber_test.ui.login_tab import LoginTab


def profile(func):
    """Decorator to profile function execution time."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Log slow operations
        if execution_time > 0.1:  # 100ms threshold
            logger = logging.getLogger('Profiler')
            logger.warning(f"Slow operation: {func.__name__} took {execution_time:.3f}s")
        
        return result
    return wrapper


class MainWindow:
    """
    Main window class for the Multi-Chamber Test application.
    
    This class serves as the application entry point, initializing the root
    window, hardware components, and UI tabs. It manages tab switching,
    authentication, and application lifecycle events.
    
    Optimized for performance with:
    - Asynchronous tab switching
    - Background tab preloading
    - Hardware operation buffering
    - UI state caching
    - Loading indicators
    """
    
    def __init__(self, start_with_login=False):
        """
        Initialize the MainWindow and application components.
        
        Args:
            start_with_login: Whether to start with the login tab instead of main tab
        """
        self.logger = logging.getLogger('MainWindow')
        self._setup_logger()
        
        # Store if we should start with login
        self.start_with_login = start_with_login
    
        # Set up the main window
        self.root = tk.Tk()
        self.root.title("Multi-Chamber Test")
    
        # Configure for touchscreen/fullscreen use
        self.root.attributes('-fullscreen', True)
        self.root.geometry(f"{UI_DIMENSIONS['WINDOW_WIDTH']}x{UI_DIMENSIONS['WINDOW_HEIGHT']}+0+0")
        self.root.resizable(False, False)
        self.root.config(cursor="none")  # Hide cursor for touchscreen operation
    
        # Load and configure application style
        self._setup_application_style()
    
        # Initialize managers and hardware
        init_success = self.init_application_components()
        if not init_success:
            self.logger.critical("Application initialization failed. Exiting.")
            self.root.destroy()  # Destroy the Tkinter window
            return
    
        # Create the UI layout
        self.create_ui_layout()
    
        # Configure exit handling
        atexit.register(self.cleanup)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
    
        # Bind global key events
        self.bind_key_events()
    
        # Custom events for tab switching
        self._setup_custom_events()
    
        # Set up hardware buffer
        self._setup_hardware_buffer()
        
        # Tab preloading status
        self.preloaded_tabs = set()
        self.preloading_active = False
        self.current_tab = None
        
        # Hardware callbacks
        self.hardware_callbacks = {}
    
        # Initialize with appropriate tab
        if self.start_with_login:
            self.switch_tab("login")
        else:
            self.switch_tab("main")
    
        # Handle physical controls if available
        if hasattr(self, 'physical_controls') and self.physical_controls:
            self.physical_controls.register_start_callback(self.on_physical_start)
            self.physical_controls.register_stop_callback(self.on_physical_stop)
            
        # Start background tab preloading after UI is settled
        self.root.after(3000, self.preload_tabs_in_background)
    
    def _setup_logger(self):
        """Configure logging for the main window."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def _setup_application_style(self):
        """Set up application-wide styles and theme."""
        style = ttk.Style()
        
        # Use a cleaner theme as a base
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        
        # Configure common styles
        style.configure(
            'TFrame',
            background=UI_COLORS['BACKGROUND']
        )
        
        style.configure(
            'TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['LABEL']
        )
        
        style.configure(
            'TButton',
            background=UI_COLORS['PRIMARY'],
            foreground=UI_COLORS['SECONDARY'],
            font=UI_FONTS['BUTTON']
        )
        
        style.map(
            'TButton',
            background=[('active', UI_COLORS['PRIMARY'])]
        )
        
        style.configure(
            'TCheckbutton',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['LABEL']
        )
        
        style.configure(
            'TRadiobutton',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY'],
            font=UI_FONTS['LABEL']
        )
        
        # Add styles for settings sections
        style.configure(
            'Card.TFrame',
            background=UI_COLORS['BACKGROUND'],
            relief='solid',
            borderwidth=1
        )
        
        style.configure(
            'ContentTitle.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['HEADER']
        )
        
        # Loading styles
        style.configure(
            'Loading.TLabel',
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY'],
            font=UI_FONTS['HEADER']
        )
        
        style.configure(
            'LoadingFrame.TFrame',
            background=UI_COLORS['BACKGROUND'],
            relief='raised',
            borderwidth=2
        )
        
        # Tab button styles
        style.configure(
            'Nav.TButton',
            font=UI_FONTS['BUTTON'],
            padding=(15, 8)
        )
        
        style.configure(
            'Selected.Nav.TButton',
            font=UI_FONTS['BUTTON'],
            padding=(15, 8),
            background=UI_COLORS['PRIMARY'],
            foreground=UI_COLORS['SECONDARY']
        )
    
    def _setup_custom_events(self):
        """Set up custom events for tab switching."""
        # Define custom events
        custom_events = [
            "<<SwitchToLoginTab>>",
            "<<SwitchToMainTab>>",
            "<<SwitchToSettingsTab>>",
            "<<SwitchToCalibrationTab>>",
            "<<SwitchToReferenceTab>>"
        ]
        
        # Create events
        for event in custom_events:
            self.root.event_add(event, "None")
        
        # Bind event handlers
        self.root.bind("<<SwitchToLoginTab>>", lambda e: self.switch_tab("login"))
        self.root.bind("<<SwitchToMainTab>>", lambda e: self.switch_tab("main"))
        self.root.bind("<<SwitchToSettingsTab>>", lambda e: self.switch_tab("settings"))
        self.root.bind("<<SwitchToCalibrationTab>>", lambda e: self.switch_tab("calibration"))
        self.root.bind("<<SwitchToReferenceTab>>", lambda e: self.switch_tab("reference"))
    
    def _setup_hardware_buffer(self):
        """Create a buffer between hardware and UI to prevent blocking."""
        self.hardware_queue = queue.Queue()
        self.hardware_results = {}
        
        # Start worker thread
        self.hardware_thread = threading.Thread(
            target=self._hardware_worker,
            daemon=True,
            name="HardwareWorker"
        )
        self.hardware_thread.start()
        
        # Start processing results on UI thread
        self._process_hardware_results()
    
    def _hardware_worker(self):
        """Background thread to handle hardware interactions with retry logic."""
        retry_counts = {}  # Track retry attempts by task ID
        
        while True:
            try:
                # Get task from queue with timeout
                task_id, component, method, args, kwargs = self.hardware_queue.get(timeout=0.1)
                
                # Track retries
                retry_count = retry_counts.get(task_id, 0)
                
                # Execute task with retry logic
                try:
                    if hasattr(component, method):
                        result = getattr(component, method)(*args, **kwargs)
                        self.hardware_results[task_id] = (True, result)
                        # Clear retry count on success
                        if task_id in retry_counts:
                            del retry_counts[task_id]
                    else:
                        self.hardware_results[task_id] = (False, f"Method {method} not found")
                except Exception as e:
                    # Check if this is a retryable error (I/O errors often are)
                    if isinstance(e, (IOError, OSError)) and retry_count < 3:
                        # Requeue the task for retry
                        retry_counts[task_id] = retry_count + 1
                        self.logger.warning(f"Retrying hardware operation ({retry_count+1}/3): {e}")
                        self.hardware_queue.put((task_id, component, method, args, kwargs))
                    else:
                        # Max retries reached or non-retryable error
                        self.hardware_results[task_id] = (False, str(e))
                        if task_id in retry_counts:
                            del retry_counts[task_id]
                
                # Mark task as done
                self.hardware_queue.task_done()
                
            except queue.Empty:
                # No tasks in queue, just continue
                pass
            
            except Exception as e:
                self.logger.error(f"Error in hardware worker: {e}")
                time.sleep(0.1)
    
    def _process_hardware_results(self):
        """Process hardware results on the UI thread."""
        try:
            # Check if we have callbacks to process
            processed = []
            for task_id in list(self.hardware_results.keys()):
                success, result = self.hardware_results[task_id]
                
                # Call appropriate callback
                if task_id in self.hardware_callbacks:
                    callback = self.hardware_callbacks[task_id]
                    try:
                        callback(success, result)
                    except Exception as e:
                        self.logger.error(f"Error in hardware callback: {e}")
                    
                    # Remove processed callback
                    del self.hardware_callbacks[task_id]
                    processed.append(task_id)
            
            # Remove processed results
            for task_id in processed:
                del self.hardware_results[task_id]
        
        except Exception as e:
            self.logger.error(f"Error processing hardware results: {e}")
            
        finally:
            # Schedule next processing
            self.root.after(50, self._process_hardware_results)
    
    def call_hardware(self, component, method, *args, callback=None, **kwargs):
        """
        Queue a hardware call to be executed in the background.
        
        Args:
            component: Hardware component to call
            method: Method name to call
            *args: Positional arguments for the method
            callback: Optional callback to be called with result
            **kwargs: Keyword arguments for the method
            
        Returns:
            Task ID for tracking the request
        """
        # Generate unique task ID
        task_id = id(callback) if callback else time.time()
        
        # Store callback
        if callback:
            self.hardware_callbacks[task_id] = callback
            
        # Queue task
        self.hardware_queue.put((task_id, component, method, args, kwargs))
        
        return task_id

    @profile
    def init_application_components(self):
        """Initialize application managers, hardware, and databases."""
        try:
            self.logger.info("Initializing application components...")
    
            # Initialize settings manager first (required by other components)
            self.settings_manager = SettingsManager()
    
            # Initialize GPIO manager (real or mock)
            try:
                self.gpio_manager = GPIOManager()
                self.gpio_manager.initialize()
            except Exception as e:
                self.logger.warning(f"GPIO initialization failed: {e}. Using MockGPIOManager instead.")
                from multi_chamber_test.hardware.mock_gpio_manager import MockGPIOManager
                self.gpio_manager = MockGPIOManager()
                self.gpio_manager.initialize()
    
            # Initialize other hardware components
            self.pressure_sensor = PressureSensor()
            self.valve_controller = ValveController(self.gpio_manager)
            self.printer_manager = PrinterManager()
    
            # Initialize physical controls (optional)
            try:
                self.physical_controls = PhysicalControls(self.gpio_manager)
                self.physical_controls.setup()
                self.logger.info("Physical controls initialized")
            except Exception as e:
                self.logger.warning(f"Physical controls initialization failed: {e}")
                self.physical_controls = None
    
            # Initialize databases
            self.reference_db = ReferenceDatabase()
            self.calibration_db = CalibrationDatabase()
    
            # Initialize core components
            self.test_logger = TestLogger()
    
            # Create TestManager
            self.test_manager = TestManager(
                self.valve_controller,
                self.pressure_sensor,
                self.printer_manager,
                self.reference_db,
                self.test_logger
            )
    
            # Create CalibrationManager
            self.calibration_manager = CalibrationManager(
                self.pressure_sensor,
                self.valve_controller,
                self.calibration_db,
                self.printer_manager
            )
            
            # Get role manager instance
            self.role_manager = get_role_manager()
            
            # Set up observer pattern connections
            # Enhance TestManager with observer capabilities
            enhance_test_manager(self.test_manager, self.settings_manager)
            
            # Enhance RoleManager with observer capabilities
            enhance_role_manager(self.role_manager, self.settings_manager)
            
            # Log successful observer pattern setup
            self.logger.info("Observer pattern connections established")
    
            self.logger.info("Application components initialized successfully")
            return True
    
        except Exception as e:
            self.logger.error(f"Failed to initialize application components: {e}")
            messagebox.showerror(
                "Initialization Error",
                f"Failed to initialize application components: {e}\n\nThe application may not function correctly."
            )
            return False
    
    def create_ui_layout(self):
        """Create the main UI layout."""
        # Main content frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top bar with logo and title
        self.create_top_bar()
        
        # Navigation bar
        self.create_nav_bar()
        
        # Tab container frame
        self.tab_container = ttk.Frame(self.main_frame)
        self.tab_container.pack(fill=tk.BOTH, expand=True)
        
        # Initialize tabs
        self.tabs = {}
        self.tab_instances = {}
        
        # Create tab frames
        self.create_tabs()
        
        # Status bar
        self.create_status_bar()
    
    def create_top_bar(self):
        """Create the top bar with logo and title."""
        top_bar = ttk.Frame(self.main_frame)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # Load logo if available
        try:
            if Image is not None:
                logo_image = Image.open(LOGO_PATH)
                # Resize image if needed
                max_height = 120
                width, height = logo_image.size
                if height > max_height:
                    ratio = max_height / height
                    new_width = int(width * ratio)
                    logo_image = logo_image.resize((new_width, max_height), Image.LANCZOS)
                
                logo_photo = ImageTk.PhotoImage(logo_image)
                logo_label = ttk.Label(top_bar, image=logo_photo, background=UI_COLORS['BACKGROUND'])
                logo_label.image = logo_photo  # Keep a reference to prevent garbage collection
                logo_label.pack(side=tk.LEFT)
            else:
                raise ImportError("PIL not available")
        except Exception as e:
            self.logger.warning(f"Could not load logo: {e}")
            # Fallback to text if logo can't be loaded
            ttk.Label(
                top_bar,
                text="Multi-Chamber Test",
                font=UI_FONTS['HEADER'],
                foreground=UI_COLORS['PRIMARY']
            ).pack(side=tk.LEFT)
        
        # Current time display (right-aligned)
        self.time_label = ttk.Label(
            top_bar,
            text="",
            font=UI_FONTS['SUBHEADER']
        )
        self.time_label.pack(side=tk.RIGHT)
        
        # Start clock update
        self.update_clock()
    
    def create_nav_bar(self):
        """Create navigation bar with tab buttons."""
        nav_frame = ttk.Frame(self.main_frame)
        nav_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # Define tab buttons with access requirements
        self.tab_buttons = {}
        tabs_info = [
            {"name": "login", "label": "Login", "access": "OPERATOR"},
            {"name": "main", "label": "Main", "access": "OPERATOR"},
            {"name": "settings", "label": "Settings", "access": "OPERATOR"},
            {"name": "calibration", "label": "Calibration", "access": "MAINTENANCE"},
            {"name": "reference", "label": "Reference", "access": "MAINTENANCE"}
        ]
        
        # Create buttons for each tab
        for tab in tabs_info:
            button = ttk.Button(
                nav_frame,
                text=tab["label"],
                style='Nav.TButton',
                command=lambda t=tab["name"], a=tab["access"]: self.switch_tab(t, a)
            )
            button.pack(side=tk.LEFT, padx=(0, 10))
            self.tab_buttons[tab["name"]] = button
    
    def create_tabs(self):
        """Create empty placeholders for tabs, but don't initialize them yet."""
        self.tabs = {}
        self.tab_instances = {}
        
        # Create tab frames only
        for tab_name in ["login", "main", "settings", "calibration", "reference"]:
            tab_frame = ttk.Frame(self.tab_container)
            self.tabs[tab_name] = tab_frame
    
    @profile
    def initialize_tab(self, tab_name):
        """Initialize a tab only when needed."""
        if tab_name not in self.tab_instances:
            self.logger.info(f"Initializing tab: {tab_name}")
            
            if tab_name == "login":
                self.tab_instances[tab_name] = LoginTab(
                    self.tabs[tab_name],
                    on_login_success=self.handle_login_success
                )
            elif tab_name == "main":
                self.tab_instances[tab_name] = MainTab(
                    self.tabs[tab_name],
                    self.test_manager,
                    self.settings_manager
                )
            elif tab_name == "settings":
                self.tab_instances[tab_name] = SettingsTab(
                    self.tabs[tab_name], 
                    self.test_manager,
                    self.settings_manager
                )
            elif tab_name == "calibration":
                self.tab_instances[tab_name] = CalibrationTab(
                    self.tabs[tab_name],
                    self.calibration_manager,
                    self.valve_controller,
                    self.pressure_sensor
                )
            elif tab_name == "reference":
                self.tab_instances[tab_name] = ReferenceTab(
                    self.tabs[tab_name],
                    self.reference_db,
                    self.test_manager
                )
                
            # Mark this tab as preloaded
            self.preloaded_tabs.add(tab_name)
            
        return self.tab_instances.get(tab_name)
    
    def create_status_bar(self):
        """Create status bar at the bottom of the window."""
        status_frame = ttk.Frame(self.main_frame, relief=tk.SUNKEN)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Left-aligned status message
        self.status_message = ttk.Label(
            status_frame,
            text="System Ready",
            padding=(10, 2)
        )
        self.status_message.pack(side=tk.LEFT)
        
        # Right-aligned user role display
        self.role_label = ttk.Label(
            status_frame,
            text="Role: Operator",
            padding=(10, 2)
        )
        self.role_label.pack(side=tk.RIGHT)
        
        # Logout button (if not in Operator role)
        self.logout_button = ttk.Button(
            status_frame,
            text="Logout",
            command=self.logout,
            width=10
        )
        # Only show logout button when not in OPERATOR role
        if get_current_role() != "OPERATOR":
            self.logout_button.pack(side=tk.RIGHT, padx=10)
        
        # Update role display initially
        self.update_role_display()
    
    def update_clock(self):
        """Update the clock display."""
        current_time = time.strftime("%H:%M:%S")
        current_date = time.strftime("%Y-%m-%d")
        self.time_label.config(text=f"{current_date} {current_time}")
        
        # Schedule next update in 1 second
        self.root.after(1000, self.update_clock)
    
    def update_role_display(self):
        """Update the current role display in the status bar."""
        current_role = get_current_role()
        self.role_label.config(text=f"Role: {current_role.title()}")
        
        # Show logout button only if not in OPERATOR role
        if current_role != "OPERATOR":
            self.logout_button.pack(side=tk.RIGHT, padx=10)
        else:
            self.logout_button.pack_forget()
    
    def update_status_message(self, message: str):
        """Update the status bar message."""
        self.status_message.config(text=message)
    
    @profile
    def switch_tab(self, tab_name: str, required_role: str = "OPERATOR"):
        """
        Optimized tab switching with improved performance.
        
        Args:
            tab_name: Name of the tab to switch to
            required_role: Minimum role required to access the tab
        """
        # Show immediate feedback for user experience
        self.update_status_message(f"Loading {tab_name.title()} tab...")
        
        # Check if tab requires authentication
        if required_role != "OPERATOR" and not has_access(required_role):
            # Special handling for Calibration and Reference tabs - show error message instead of auth dialog
            if tab_name in ["calibration", "reference"]:
                messagebox.showwarning(
                    "Access Denied",
                    f"You don't have permission to access the {tab_name.title()} tab.\n\n"
                    f"This feature requires {required_role} privileges."
                )
                # Stay on current tab
                if hasattr(self, 'current_tab') and self.current_tab:
                    self.update_status_message(f"Tab: {self.current_tab.title()}")
                return
            
            # For other restricted tabs, use the original behavior
            if self.start_with_login:
                # Redirect to login tab with message
                self.update_status_message(f"Authentication required for {tab_name.title()}")
                tab_name = "login"
                # Store the requested tab for after login
                self.login_redirect_tab = tab_name
            else:
                # Show authentication dialog
                self.show_auth_dialog(required_role, 
                                    on_success=lambda: self.switch_tab(tab_name, "OPERATOR"))
                return
        
        # Check if tab exists
        if tab_name not in self.tabs:
            self.logger.error(f"Tab '{tab_name}' not found")
            return
        
        # Define function to be executed after a minimal delay
        def execute_tab_switch():
            # Display loading indicator
            self.show_loading_screen(f"Loading {tab_name.title()} tab...")
            
            # Hide current tab first (allows UI to update)
            if hasattr(self, 'current_tab') and self.current_tab:
                current_tab_instance = self.tab_instances.get(self.current_tab)
                if current_tab_instance and hasattr(current_tab_instance, 'on_tab_deselected'):
                    try:
                        result = current_tab_instance.on_tab_deselected()
                        if result is False:
                            # Tab refuses to be deselected
                            self.hide_loading_screen()
                            self.update_status_message(f"Tab: {self.current_tab.title()}")
                            return
                    except Exception as e:
                        self.logger.error(f"Error in on_tab_deselected: {e}")
                
                # Hide current tab without waiting for it to clean up completely
                self.tabs[self.current_tab].pack_forget()
            
            # Initialize tab if needed (lazy loading)
            if tab_name not in self.tab_instances:
                # Initialize in a separate function to allow UI to update
                def complete_initialization():
                    self.initialize_tab(tab_name)
                    self._finish_tab_switch(tab_name)
                
                # Small delay to allow loading indicator to appear
                self.root.after(10, complete_initialization)
            else:
                # Tab already initialized, just switch
                self._finish_tab_switch(tab_name)
        
        # Use a short delay to allow status message to appear
        self.root.after(10, execute_tab_switch)
    
    def _finish_tab_switch(self, tab_name):
        """Complete the tab switch process."""
        try:
            # Show the new tab
            self.tabs[tab_name].pack(fill=tk.BOTH, expand=True)
            self.current_tab = tab_name
            
            # Hide loading screen
            self.hide_loading_screen()
            
            # Call on_tab_selected in a separate event to avoid blocking
            def delayed_selection():
                tab_instance = self.tab_instances.get(tab_name)
                if tab_instance and hasattr(tab_instance, 'on_tab_selected'):
                    try:
                        tab_instance.on_tab_selected()
                    except Exception as e:
                        self.logger.error(f"Error in on_tab_selected: {e}")
            
            # Update UI state for the new tab
            self.update_tab_button_states()
            self.update_status_message(f"Tab: {tab_name.title()}")
            
            # Use a slight delay for tab selection to let the UI render first
            self.root.after(50, delayed_selection)
            
            # Start preloading other tabs if not already preloading
            if not self.preloading_active:
                self.root.after(1000, self.preload_tabs_in_background)
                
            self.logger.info(f"Successfully switched to tab {tab_name}")
            
        except Exception as e:
            self.logger.error(f"Error finishing tab switch to {tab_name}: {e}")
            self.hide_loading_screen()
            self.update_status_message("Error switching tabs")
    
    def update_tab_button_states(self):
        """Update the visual state of tab buttons based on current tab."""
        for name, button in self.tab_buttons.items():
            if name == self.current_tab:
                button.configure(style='Selected.Nav.TButton')
            else:
                button.configure(style='Nav.TButton')
    
    def preload_tabs_in_background(self):
        """Pre-initialize tabs in the background to improve switching performance."""
        if self.preloading_active:
            return  # Already preloading
            
        self.preloading_active = True
        tab_names = ["main", "settings", "calibration", "reference"]
        self.logger.info("Starting background tab initialization")
        
        def initialize_next_tab(index=0):
            try:
                if index >= len(tab_names):
                    self.logger.info("All tabs preloaded in background")
                    self.preloading_active = False
                    return
                
                tab_name = tab_names[index]
                if tab_name not in self.tab_instances and tab_name != self.current_tab:
                    self.logger.info(f"Background initializing: {tab_name}")
                    
                    # Create a separate function for initialization to avoid
                    # blocking the UI thread for too long
                    
                    # First, show a "preloading" indicator in the hidden tab
                    preload_frame = ttk.Frame(self.tabs[tab_name])
                    preload_frame.pack(fill=tk.BOTH, expand=True)
                    
                    preload_label = ttk.Label(
                        preload_frame,
                        text=f"Preloading {tab_name.title()} tab...",
                        style='Loading.TLabel'
                    )
                    preload_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                    
                    # Define actual initialization function
                    def do_initialize():
                        try:
                            # Initialize the tab
                            self.initialize_tab(tab_name)
                            # Destroy preload indicator
                            preload_frame.destroy()
                            self.logger.info(f"Background initialization of {tab_name} complete")
                        except Exception as e:
                            self.logger.error(f"Error initializing tab {tab_name} in background: {e}")
                            
                        # Schedule next tab initialization
                        self.root.after(500, lambda: initialize_next_tab(index + 1))
                    
                    # Schedule initialization after a delay
                    self.root.after(100, do_initialize)
                else:
                    # Skip to next tab
                    self.root.after(100, lambda: initialize_next_tab(index + 1))
            except Exception as e:
                    self.logger.error(f"Error preloading tab {tab_names[index]}: {e}")
                    # Continue with next tab rather than stopping the entire process
                    self.root.after(100, lambda: initialize_next_tab(index + 1))
    
    def show_loading_screen(self, message="Loading..."):
        """
        Show a loading screen overlay while switching tabs.
        
        Args:
            message: Message to display on the loading screen
        """
        # If loading frame already exists, just update message
        if hasattr(self, 'loading_toplevel') and self.loading_toplevel.winfo_exists():
            if hasattr(self, 'loading_message'):
                self.loading_message.config(text=message)
            return
        
        # Create a toplevel window for the loading screen
        self.loading_toplevel = tk.Toplevel(self.root)
        self.loading_toplevel.withdraw()  # Hide initially
        
        # Make it cover the main window
        x = self.root.winfo_rootx()
        y = self.root.winfo_rooty()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Position the toplevel
        self.loading_toplevel.geometry(f"{width}x{height}+{x}+{y}")
        
        # Remove window decorations and make it semi-transparent
        self.loading_toplevel.overrideredirect(True)
        self.loading_toplevel.attributes('-alpha', 0.7)
        
        # Set background color
        self.loading_toplevel.configure(background='#333333')
        
        # Create the loading message container
        loading_container = tk.Frame(
            self.loading_toplevel,
            background=UI_COLORS['BACKGROUND'],
            borderwidth=2,
            relief=tk.RAISED
        )
        loading_container.place(
            relx=0.5, rely=0.5,
            anchor=tk.CENTER,
            width=400, height=150
        )
        
        # Add spinner animation
        self.spinner_text = tk.StringVar(value="?")
        spinner_label = tk.Label(
            loading_container,
            textvariable=self.spinner_text,
            font=('Helvetica', 24),
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['PRIMARY']
        )
        spinner_label.pack(pady=(20, 10))
        
        # Add message
        self.loading_message = tk.Label(
            loading_container,
            text=message,
            font=UI_FONTS['LABEL'],
            background=UI_COLORS['BACKGROUND'],
            foreground=UI_COLORS['TEXT_PRIMARY']
        )
        self.loading_message.pack(pady=(10, 20))
        
        # Start spinner animation
        self._animate_spinner()
        
        # Show the loading overlay
        self.loading_toplevel.deiconify()
        self.loading_toplevel.lift()
        self.loading_toplevel.update()
    
    def _animate_spinner(self):
        """Animate the loading spinner."""
        if not hasattr(self, 'loading_frame') or not self.loading_frame.winfo_exists():
            return
            
        if not hasattr(self, 'spinner_text'):
            return
            
        # Spinner animation frames - braille pattern animation
        frames = ["?", "?", "?", "?", "?", "?", "?", "?"]
        
        # Get current frame index
        current_text = self.spinner_text.get()
        current_idx = frames.index(current_text) if current_text in frames else 0
        next_idx = (current_idx + 1) % len(frames)
        
        # Update spinner
        self.spinner_text.set(frames[next_idx])
        
        # Schedule next frame
        self.root.after(100, self._animate_spinner)
    
    def hide_loading_screen(self):
        """Hide the loading screen."""
        if hasattr(self, 'loading_toplevel') and self.loading_toplevel.winfo_exists():
            self.loading_toplevel.destroy()
            delattr(self, 'loading_toplevel')
            
    def handle_login_success(self, role=None):
        """Handle successful login from the login tab."""
        # Update role display
        self.update_role_display()
        
        # Display success message
        if role:
            self.update_status_message(f"Logged in as {role}")
        
        # Redirect to previously requested tab if available
        if hasattr(self, "login_redirect_tab") and self.login_redirect_tab:
            redirect_tab = self.login_redirect_tab
            self.login_redirect_tab = None
            self.switch_tab(redirect_tab)
        else:
            # Otherwise go to main tab
            self.switch_tab("main")
    
    def logout(self):
        """Log out the current user."""
        # Confirm logout
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            # Perform logout
            self.role_manager.logout()
            
            # Update role display
            self.update_role_display()
            
            # Show message
            self.update_status_message("Logged out successfully")
            
            # Switch to login tab if using login tab, otherwise stay on current tab
            if self.start_with_login:
                self.switch_tab("login")
    
    def show_auth_dialog(self, min_role: str, on_success: Optional[Callable] = None):
        """
        Show authentication dialog for access to protected features.
        
        Args:
            min_role: Minimum role required
            on_success: Function to call on successful authentication
        """
        def auth_success():
            # Refresh the authentication session
            self.role_manager.refresh_session()
            
            # Update role display
            self.update_role_display()
            
            # Call success callback if provided
            if on_success:
                on_success()
        
        # Show password dialog
        PasswordDialog(
            self.root,
            min_role,
            on_success=auth_success
        )
    
    def on_physical_start(self):
        """Handle physical start button press."""
        # Only respond if on main tab
        if hasattr(self, 'current_tab') and self.current_tab == "main":
            # Forward to main tab's start_test method
            tab_instance = self.tab_instances.get("main")
            if tab_instance and hasattr(tab_instance, 'start_test'):
                tab_instance.start_test()
    
    def on_physical_stop(self):
        """Handle physical stop button press."""
        # Only respond if on main tab
        if hasattr(self, 'current_tab') and self.current_tab == "main":
            # Forward to main tab's stop_test method
            tab_instance = self.tab_instances.get("main")
            if tab_instance and hasattr(tab_instance, 'stop_test'):
                tab_instance.stop_test()
    
    def bind_key_events(self):
        """Bind global key events."""
        # Escape key to exit fullscreen
        self.root.bind('<Escape>', self.toggle_fullscreen)
        
        # F1 to switch to main tab
        self.root.bind('<F1>', lambda e: self.switch_tab("main"))
        
        # F2 to switch to settings tab
        self.root.bind('<F2>', lambda e: self.switch_tab("settings"))
        
        # F9 to switch to login tab
        self.root.bind('<F9>', lambda e: self.switch_tab("login"))
        
        # F10 to logout
        self.root.bind('<F10>', lambda e: self.logout())
        
        # Home key to return to main tab (useful addition)
        self.root.bind('<Home>', lambda e: self.switch_tab("main"))
    
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode."""
        is_fullscreen = bool(self.root.attributes('-fullscreen'))
        self.root.attributes('-fullscreen', not is_fullscreen)
        
        # Show cursor if exiting fullscreen
        if is_fullscreen:
            self.root.config(cursor="")
        else:
            self.root.config(cursor="none")
    
    def on_exit(self):
        """Handle application exit."""
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.cleanup()
            self.root.destroy()
    
    def cleanup(self):
        """Clean up resources before exit."""
        self.logger.info("Cleaning up resources...")
        
        # Stop background loading
        self.preloading_active = False
        
        # Clean up tabs
        for tab_name, tab_instance in self.tab_instances.items():
            if hasattr(tab_instance, 'cleanup'):
                try:
                    tab_instance.cleanup()
                except Exception as e:
                    self.logger.error(f"Error cleaning up {tab_name} tab: {e}")
        
        # Clean up hardware buffer
        if hasattr(self, 'hardware_queue'):
            try:
                # Clear queue
                while not self.hardware_queue.empty():
                    try:
                        self.hardware_queue.get_nowait()
                        self.hardware_queue.task_done()
                    except:
                        break
            except:
                pass
        
        # Clean up hardware
        try:
            if hasattr(self, 'valve_controller'):
                # Close all valves
                for i in range(3):
                    self.valve_controller.stop_chamber(i)
                    
            if hasattr(self, 'physical_controls') and self.physical_controls:
                self.physical_controls.cleanup()
                
            # Final GPIO cleanup
            if hasattr(self, 'gpio_manager'):
                self.gpio_manager.cleanup()
                
        except Exception as e:
            self.logger.error(f"Error during hardware cleanup: {e}")
        
        # Save settings before exit
        if hasattr(self, 'settings_manager'):
            self.settings_manager.save_settings()
    
    def run(self):
        """Run the application main loop."""
        self.logger.info("Starting application main loop")
        self.root.mainloop()


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to log unhandled exceptions."""
    logger = logging.getLogger('ExceptionHandler')
    logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Show error message to user
    error_message = f"An unhandled error occurred: {exc_type.__name__}: {exc_value}"
    try:
        messagebox.showerror("Application Error", error_message)
    except:
        # If even showing a messagebox fails, print to console
        print(f"CRITICAL ERROR: {error_message}")