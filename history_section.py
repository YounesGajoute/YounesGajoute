#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test History Section module for the Multi-Chamber Test application.

This module provides the HistorySection class that displays test history
and allows viewing detailed test results and filtering past tests.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import threading
import time
from datetime import datetime, timedelta
import csv
import os
from typing import Dict, Any, List, Optional, Tuple

from multi_chamber_test.config.constants import UI_COLORS, UI_FONTS
from multi_chamber_test.ui.settings.base_section import BaseSection
from multi_chamber_test.database.test_result_db import TestResultDatabase


class HistorySection(BaseSection):
    """
    Test history section for viewing historical test results.
    
    This section displays a list of past tests with their results and allows
    filtering by date, exporting results, and viewing detailed test information.
    """
    
    def __init__(self, parent, test_manager):
        """
        Initialize the test history section.
        
        Args:
            parent: Parent widget
            test_manager: TestManager for accessing test data
        """
        self.test_manager = test_manager
        
        # Initialize the test results database
        self.test_db = TestResultDatabase()
        
        # State variables
        self.filter_date = tk.StringVar(value="All Time")
        self.test_records = []
        self.filtered_records = []
        
        # Call base class constructor
        super().__init__(parent)
    
    def create_widgets(self):
        """Create UI widgets for the test history section."""
        # Section title with icon
        title_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(
            title_frame,
            text="?? Test History",
            style='ContentTitle.TLabel'
        ).pack(anchor=tk.W)
        
        # Create main history browser
        self.create_history_browser()
        
        # Create detail view (initially hidden)
        self.create_detail_view()
    
    def create_history_browser(self):
        """Create the test history browser with filtering."""
        # Create a styled card
        card, content = self.create_card(
            "Test Records",
            "View and filter all past test results."
        )
        
        # Filter controls
        filter_frame = ttk.Frame(content, style='Card.TFrame')
        filter_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(
            filter_frame,
            text="Filter:",
            style='CardText.TLabel'
        ).pack(side=tk.LEFT)
        
        # Time filter dropdown
        time_options = ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Last 90 Days"]
        time_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_date,
            values=time_options,
            state="readonly",
            width=15
        )
        time_dropdown.pack(side=tk.LEFT, padx=10)
        time_dropdown.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        
        # Refresh button
        refresh_button = ttk.Button(
            filter_frame,
            text="Refresh",
            command=self.load_test_records,
            style='Secondary.TButton'
        )
        refresh_button.pack(side=tk.RIGHT)
        
        # Export all results button
        export_button = ttk.Button(
            filter_frame,
            text="Export All",
            command=self.export_all_results,
            style='Secondary.TButton'
        )
        export_button.pack(side=tk.RIGHT, padx=10)
        
        # Create table for test records
        self.create_test_table(content)
    
    def create_test_table(self, parent):
        """
        Create the table for displaying test records.
        
        Args:
            parent: Parent widget to contain the table
        """
        # Table container
        table_frame = ttk.Frame(parent, style='Card.TFrame')
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create Treeview widget
        columns = (
            'timestamp', 'duration', 'mode', 'result', 
            'chamber1', 'chamber2', 'chamber3', 'reference'
        )
        
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            selectmode='browse',
            height=15
        )
        
        # Configure columns
        column_widths = {
            'timestamp': 150,
            'duration': 80,
            'mode': 100,
            'result': 80,
            'chamber1': 100,
            'chamber2': 100,
            'chamber3': 100,
            'reference': 150
        }
        
        column_texts = {
            'timestamp': 'Date & Time',
            'duration': 'Duration (s)',
            'mode': 'Test Mode',
            'result': 'Result',
            'chamber1': 'Chamber 1',
            'chamber2': 'Chamber 2',
            'chamber3': 'Chamber 3',
            'reference': 'Reference ID'
        }
        
        for col in columns:
            self.tree.column(col, width=column_widths.get(col, 100), anchor='center')
            self.tree.heading(col, text=column_texts.get(col, col.title()))
        
        # Add scrollbars
        yscroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        
        # Pack in order: horizontal scrollbar at bottom, tree and vertical scrollbar in middle
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to view details
        self.tree.bind('<Double-1>', self.view_test_details)
        
        # Action button frame
        action_frame = ttk.Frame(parent, style='Card.TFrame')
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            action_frame,
            text="View Details",
            command=self.view_selected_test,
            style='Action.TButton'
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            action_frame,
            text="Export Selected",
            command=self.export_selected_test,
            style='Secondary.TButton'
        ).pack(side=tk.RIGHT)
    
    def create_detail_view(self):
        """Create the detailed test view panel (initially hidden)."""
        # Detail view container (hidden initially)
        self.detail_frame = ttk.Frame(self.content_frame, style='Card.TFrame')
        
        # Header with back button
        header_frame = ttk.Frame(self.detail_frame, style='Card.TFrame', padding=10)
        header_frame.pack(fill=tk.X)
        
        back_button = ttk.Button(
            header_frame,
            text="? Back to Test List",
            command=self.hide_test_details,
            style='Secondary.TButton'
        )
        back_button.pack(side=tk.LEFT)
        
        self.detail_title = ttk.Label(
            header_frame,
            text="Test Details",
            style='CardTitle.TLabel'
        )
        self.detail_title.pack(side=tk.LEFT, padx=(20, 0))
        
        # Detail content container
        detail_content = ttk.Frame(self.detail_frame, style='Card.TFrame', padding=10)
        detail_content.pack(fill=tk.BOTH, expand=True)
        
        # Create placeholder for test details (will be populated when a test is selected)
        self.detail_content = detail_content
    
    def load_test_records(self):
        """Load test records from the test database."""
        try:
            # Show loading cursor
            self.frame.config(cursor="watch")
            
            # Start loading in a separate thread to avoid freezing UI
            threading.Thread(target=self._load_records_thread, daemon=True).start()
        except Exception as e:
            self.logger.error(f"Error starting test record load: {e}")
            self.frame.config(cursor="")
            self.show_feedback(f"Error loading test records: {str(e)}", is_error=True)
    
    def _load_records_thread(self):
        """Background thread for loading test records."""
        try:
            # Load records from database
            self.test_records = self.test_db.get_all_results()
            
            # Schedule UI update with results
            self._schedule_ui_update(self._finish_loading_records)
        except Exception as e:
            self.logger.error(f"Error loading test records: {e}")
            self._schedule_ui_update(lambda: self._handle_loading_error(str(e)))
    
    def _finish_loading_records(self):
        """Complete the test record loading process in the UI thread."""
        try:
            # Reset cursor
            self.frame.config(cursor="")
            
            # Check if we got any records
            if not self.test_records:
                self.show_feedback("No test records found in database", is_error=False)
                self.filtered_records = []
                self.display_records([])
                return
                
            # Show success message
            self.show_feedback(f"Loaded {len(self.test_records)} test records", is_error=False)
            
            # Apply filters and display
            self.apply_filters()
        except Exception as e:
            self.logger.error(f"Error displaying test records: {e}")
            self.show_feedback(f"Error displaying test records: {str(e)}", is_error=True)
    
    def _handle_loading_error(self, error_message):
        """Handle errors during test record loading."""
        self.frame.config(cursor="")
        self.show_feedback(f"Error loading test records: {error_message}", is_error=True)
    
    def apply_filters(self):
        """Apply the selected filters to the test records."""
        if not self.test_records:
            self.filtered_records = []
            self.display_records([])
            return
            
        self.filtered_records = self.filter_records(self.test_records)
        self.display_records(self.filtered_records)
    
    def filter_records(self, records):
        """
        Filter test records based on selected criteria.
        
        Args:
            records: List of test records to filter
            
        Returns:
            Filtered list of test records
        """
        filter_option = self.filter_date.get()
        
        if filter_option == "All Time":
            return records
        
        # Calculate date cutoff based on filter
        now = datetime.now()
        cutoff = None
        
        if filter_option == "Today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif filter_option == "Last 7 Days":
            cutoff = now - timedelta(days=7)
        elif filter_option == "Last 30 Days":
            cutoff = now - timedelta(days=30)
        elif filter_option == "Last 90 Days":
            cutoff = now - timedelta(days=90)
        
        if cutoff:
            # Filter records by timestamp
            filtered = []
            for record in records:
                try:
                    # Parse timestamp from string
                    timestamp = datetime.fromisoformat(record['timestamp'])
                    if timestamp >= cutoff:
                        filtered.append(record)
                except (ValueError, TypeError):
                    # Skip records with invalid timestamps
                    pass
            return filtered
        
        return records
    
    def display_records(self, records):
        """
        Display the filtered records in the tree view.
        
        Args:
            records: Records to display
        """
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add filtered records
        for record in records:
            # Format values for display
            try:
                timestamp = record['timestamp']
                duration = str(record['test_duration'])
                mode = record['test_mode'] if record['test_mode'] else "Unknown"
                result = 'PASS' if record['overall_result'] else 'FAIL'
                reference = record.get('reference', 'N/A')
                
                # Get chamber results
                chamber_results = []
                chambers = record.get('chambers', [])
                
                # Ensure we have 3 chambers (even if some are missing in the data)
                while len(chambers) < 3:
                    chambers.append({'enabled': False})
                
                for chamber in chambers:
                    if chamber.get('enabled', False):
                        pressure = chamber.get('final_pressure', 0)
                        status = 'OK' if chamber.get('result', False) else 'FAIL'
                        chamber_results.append(f"{pressure:.1f} mbar ({status})")
                    else:
                        chamber_results.append("Disabled")
                
                # Add to tree with proper colors
                values = [
                    timestamp, duration, mode, result,
                    chamber_results[0], chamber_results[1], chamber_results[2],
                    reference
                ]
                
                item_id = self.tree.insert('', 'end', values=values)
                
                # Color by result
                if record['overall_result']:
                    self.tree.item(item_id, tags=('pass',))
                else:
                    self.tree.item(item_id, tags=('fail',))
            except Exception as e:
                self.logger.error(f"Error displaying record: {e}")
                # Skip record and continue
        
        # Configure tag colors
        self.tree.tag_configure('pass', background='#DFF0D8')
        self.tree.tag_configure('fail', background='#F2DEDE')
    
    def view_selected_test(self):
        """View details of the selected test."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a test to view.")
            return
        
        # Get the selected record
        item_id = selected[0]
        item_values = self.tree.item(item_id, 'values')
        if not item_values or len(item_values) < 8:
            messagebox.showerror("Error", "Selected item has invalid data.")
            return
        
        timestamp = item_values[0]
        
        # Find the corresponding record
        for record in self.filtered_records:
            if record['timestamp'] == timestamp:
                self.show_test_details(record)
                return
        
        messagebox.showerror("Error", "Could not find test details for the selected record.")
    
    def view_test_details(self, event):
        """
        Handle double-click event on a test record.
        
        Args:
            event: The event data
        """
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            self.view_selected_test()
    
    def show_test_details(self, record):
        """
        Show detailed view of a test record.
        
        Args:
            record: The test record to display
        """
        # Hide the browser and show the detail view
        self.tree.master.master.pack_forget()
        self.detail_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Set title
        timestamp = record['timestamp']
        self.detail_title.config(text=f"Test Details - {timestamp}")
        
        # Clear existing content
        for widget in self.detail_content.winfo_children():
            widget.destroy()
        
        # Add details
        self.populate_test_details(record)
    
    def hide_test_details(self):
        """Hide the detail view and show the browser."""
        self.detail_frame.pack_forget()
        self.tree.master.master.pack(fill=tk.BOTH, expand=True, pady=10)
    
    def populate_test_details(self, record):
        """
        Populate the detail view with test record information.
        
        Args:
            record: The test record to display
        """
        # Test summary section
        summary_frame = ttk.LabelFrame(self.detail_content, text="Test Summary")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        summary_grid = ttk.Frame(summary_frame)
        summary_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Add summary fields
        fields = [
            ("Date & Time", record['timestamp']),
            ("Duration", f"{record['test_duration']} seconds"),
            ("Test Mode", record['test_mode'] if record['test_mode'] else "Unknown"),
            ("Operator", record.get('operator_id', 'N/A')),
            ("Reference", record.get('reference', 'N/A')),
            ("Result", "PASS" if record['overall_result'] else "FAIL")
        ]
        
        for i, (label, value) in enumerate(fields):
            row = i // 3
            col = i % 3
            
            # Label
            ttk.Label(
                summary_grid,
                text=f"{label}:",
                style='CardText.TLabel',
                font=('Helvetica', 10, 'bold')
            ).grid(row=row, column=col*2, sticky='w', padx=(10, 5), pady=5)
            
            # Value
            value_color = UI_COLORS.get('SUCCESS', 'green') if label == "Result" and value == "PASS" else \
                          UI_COLORS.get('ERROR', 'red') if label == "Result" and value == "FAIL" else \
                          UI_COLORS.get('TEXT_PRIMARY', 'black')
                          
            ttk.Label(
                summary_grid,
                text=value,
                foreground=value_color
            ).grid(row=row, column=col*2+1, sticky='w', padx=(0, 20), pady=5)
        
        # Chamber results section
        chambers_frame = ttk.LabelFrame(self.detail_content, text="Chamber Results")
        chambers_frame.pack(fill=tk.X, pady=(0, 10))
        
        chamber_grid = ttk.Frame(chambers_frame)
        chamber_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Header row
        headers = ["Chamber", "Status", "Target (mbar)", "Actual (mbar)", "Threshold", "Result"]
        for col, header in enumerate(headers):
            ttk.Label(
                chamber_grid,
                text=header,
                font=('Helvetica', 10, 'bold')
            ).grid(row=0, column=col, sticky='w', padx=10, pady=(0, 5))
        
        # Add chamber data
        chambers = record.get('chambers', [])
        
        # Ensure we have 3 chambers (even if some are missing in the data)
        while len(chambers) < 3:
            chambers.append({'enabled': False, 'chamber_id': len(chambers)})
        
        for chamber in chambers:
            chamber_id = chamber.get('chamber_id', 0)
            row = chamber_id + 1
            
            # Chamber number
            ttk.Label(
                chamber_grid,
                text=f"Chamber {chamber_id+1}"
            ).grid(row=row, column=0, sticky='w', padx=10, pady=5)
            
            if chamber.get('enabled', False):
                # Status
                ttk.Label(
                    chamber_grid,
                    text="Enabled"
                ).grid(row=row, column=1, sticky='w', padx=10, pady=5)
                
                # Target
                ttk.Label(
                    chamber_grid,
                    text=f"{chamber.get('pressure_target', 0):.1f}"
                ).grid(row=row, column=2, sticky='w', padx=10, pady=5)
                
                # Actual pressure
                ttk.Label(
                    chamber_grid,
                    text=f"{chamber.get('final_pressure', 0):.1f}"
                ).grid(row=row, column=3, sticky='w', padx=10, pady=5)
                
                # Threshold
                ttk.Label(
                    chamber_grid,
                    text=f"{chamber.get('pressure_threshold', 0):.1f}"
                ).grid(row=row, column=4, sticky='w', padx=10, pady=5)
                
                # Result
                result = chamber.get('result', False)
                result_text = "PASS" if result else "FAIL"
                result_color = UI_COLORS.get('SUCCESS', 'green') if result else UI_COLORS.get('ERROR', 'red')
                
                ttk.Label(
                    chamber_grid,
                    text=result_text,
                    foreground=result_color
                ).grid(row=row, column=5, sticky='w', padx=10, pady=5)
            else:
                # Chamber disabled
                ttk.Label(
                    chamber_grid,
                    text="Disabled",
                    foreground=UI_COLORS.get('TEXT_SECONDARY', 'gray')
                ).grid(row=row, column=1, columnspan=5, sticky='w', padx=10, pady=5)
        
        # Export button at the bottom
        export_frame = ttk.Frame(self.detail_content)
        export_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            export_frame,
            text="Export This Test Record",
            command=lambda: self.export_record_to_csv(record),
            style='Secondary.TButton'
        ).pack(side=tk.RIGHT)
    
    def export_selected_test(self):
        """Export the selected test data to CSV."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a test to export.")
            return
        
        # Get the selected record
        item_id = selected[0]
        item_values = self.tree.item(item_id, 'values')
        if not item_values or len(item_values) < 8:
            messagebox.showerror("Error", "Selected item has invalid data.")
            return
        
        timestamp = item_values[0]
        
        # Find the corresponding record
        for record in self.filtered_records:
            if record['timestamp'] == timestamp:
                self.export_record_to_csv(record)
                return
        
        messagebox.showerror("Error", "Could not find test details for the selected record.")
    
    def export_all_results(self):
        """Export all filtered test results to CSV."""
        if not self.filtered_records:
            messagebox.showinfo("No Records", "There are no test records to export.")
            return
        
        # Ask for destination file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Test Records"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Show waiting cursor
            self.frame.config(cursor="watch")
            
            # Start export in a separate thread
            threading.Thread(
                target=self._export_records_thread,
                args=(self.filtered_records, file_path),
                daemon=True
            ).start()
            
        except Exception as e:
            self.logger.error(f"Error starting export: {e}")
            self.frame.config(cursor="")
            messagebox.showerror("Export Error", f"Failed to start export: {str(e)}")
    
    def _export_records_thread(self, records, file_path):
        """
        Background thread for exporting records to CSV.
        
        Args:
            records: List of records to export
            file_path: Path to save the CSV file
        """
        try:
            # Export to CSV
            self._export_to_csv(records, file_path)
            
            # Schedule UI update with success
            self._schedule_ui_update(lambda: self._show_export_success(file_path))
            
        except Exception as e:
            self.logger.error(f"Error exporting records: {e}")
            self._schedule_ui_update(lambda e=str(e): self._show_export_error(e))
    
    def _show_export_success(self, file_path):
        """Show export success message."""
        self.frame.config(cursor="")
        messagebox.showinfo(
            "Export Successful",
            f"Test records were successfully exported to:\n{file_path}"
        )
    
    def _show_export_error(self, error):
        """Show export error message."""
        self.frame.config(cursor="")
        messagebox.showerror(
            "Export Error",
            f"Failed to export test records: {error}"
        )
    
    def export_record_to_csv(self, record):
        """
        Export a single test record to CSV.
        
        Args:
            record: The test record to export
        """
        # Ask for destination file
        default_filename = f"test_{record['timestamp'].replace(':', '-').replace(' ', '_')}.csv"
        default_filename = default_filename.replace('/', '-').replace('\\', '-')
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Export Test Record"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            # Export the record to CSV
            self._export_to_csv([record], file_path)
            
            messagebox.showinfo(
                "Export Successful",
                f"Test record was successfully exported to:\n{file_path}"
            )
            
        except Exception as e:
            self.logger.error(f"Error exporting record: {e}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export test record: {str(e)}"
            )
    
    def _export_to_csv(self, records, file_path):
        """
        Write records to a CSV file.
        
        Args:
            records: List of records to export
            file_path: Path to save the CSV file
        """
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            # Write test summary section
            writer = csv.writer(csvfile)
            
            # Write header row
            writer.writerow([
                "Test ID", "Timestamp", "Operator", "Test Mode", "Reference", 
                "Duration (s)", "Overall Result"
            ])
            
            # Write summary for each record
            for record in records:
                writer.writerow([
                    record.get('id', ''),
                    record['timestamp'],
                    record.get('operator_id', 'N/A'),
                    record.get('test_mode', 'Unknown'),
                    record.get('reference', 'N/A'),
                    record['test_duration'],
                    "PASS" if record['overall_result'] else "FAIL"
                ])
            
            # Add a blank row
            writer.writerow([])
            
            # Write chamber details section
            writer.writerow([
                "Test ID", "Chamber", "Enabled", "Target (mbar)", 
                "Threshold (mbar)", "Tolerance (mbar)", "Final Pressure (mbar)", "Result"
            ])
            
            # Write chamber details for each record
            for record in records:
                test_id = record.get('id', '')
                
                for chamber in record.get('chambers', []):
                    writer.writerow([
                        test_id,
                        f"Chamber {chamber.get('chamber_id', 0) + 1}",
                        "Yes" if chamber.get('enabled', False) else "No",
                        chamber.get('pressure_target', 0),
                        chamber.get('pressure_threshold', 0),
                        chamber.get('pressure_tolerance', 0),
                        chamber.get('final_pressure', 0),
                        "PASS" if chamber.get('result', False) else "FAIL"
                    ])
    
    def refresh_all(self):
        """Refresh all UI components."""
        self.load_test_records()
    
    def on_selected(self):
        """Called when this section is selected."""
        super().on_selected()
        self.load_test_records()