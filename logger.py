#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Logger module for the Multi-Chamber Test application.

This module provides a TestLogger class for recording and managing
test results, with capabilities to save results to CSV files and
maintain a history of recent tests.
"""

import csv
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union
import json

from multi_chamber_test.config.constants import RESULTS_DIR

class TestLogger:
    """
    Logger for test results with CSV export capabilities.
    
    This class maintains an in-memory record of recent test results and
    provides methods to save results to CSV files. It supports both
    detailed logging of individual test runs and summary statistics.
    """
    
    def __init__(self, max_records: int = 1000, results_dir: str = RESULTS_DIR):
        """
        Initialize the TestLogger with specified capacity.
        
        Args:
            max_records: Maximum number of test records to keep in memory
            results_dir: Directory for saving test result CSV files
        """
        self.logger = logging.getLogger('TestLogger')
        self._setup_logger()
        
        self.max_records = max_records
        self.results_dir = results_dir
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Internal storage for test results
        self.test_records = []
        
        # Initialize counters for statistics
        self.stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'last_test_time': None
        }
        
        self.logger.info(f"TestLogger initialized with capacity for {max_records} records")
    
    def _setup_logger(self):
        """Configure logging for the test logger."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def log_test_result(self, test_data: Dict[str, Any]) -> bool:
        """
        Log a test result to the in-memory storage.
        
        Args:
            test_data: Dictionary containing test result data with keys:
                      'timestamp': Test timestamp (datetime or str)
                      'reference': Reference barcode (str or None)
                      'test_mode': Test mode ('manual' or 'reference')
                      'test_duration': Test duration in seconds (int)
                      'overall_result': Overall test result (bool)
                      'chambers': List of dictionaries with chamber-specific results:
                          'chamber_id': Chamber identifier (int, 0-2)
                          'enabled': Whether the chamber was enabled for the test (bool)
                          'pressure_target': Target pressure in mbar (float)
                          'pressure_threshold': Threshold pressure in mbar (float)
                          'pressure_tolerance': Acceptable pressure variation in mbar (float)
                          'final_pressure': Final pressure reading in mbar (float)
                          'pressure_log': List of pressure readings during test (optional)
                          'result': Chamber-specific test result (bool)
            
        Returns:
            bool: True if the test result was logged successfully, False otherwise
        """
        try:
            # Ensure timestamp is in the correct format
            if isinstance(test_data.get('timestamp'), datetime):
                timestamp = test_data['timestamp']
            elif isinstance(test_data.get('timestamp'), str):
                try:
                    timestamp = datetime.fromisoformat(test_data['timestamp'])
                except ValueError:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            # Format the record with standardized structure
            record = {
                'timestamp': timestamp.isoformat(),
                'reference': test_data.get('reference', 'N/A'),
                'test_mode': test_data.get('test_mode', 'manual'),
                'test_duration': test_data.get('test_duration', 0),
                'overall_result': bool(test_data.get('overall_result', False)),
                'chambers': []
            }
            
            # Process chamber-specific data
            chambers_data = test_data.get('chambers', [])
            for chamber_data in chambers_data:
                chamber_record = {
                    'chamber_id': chamber_data.get('chamber_id', 0),
                    'enabled': bool(chamber_data.get('enabled', True)),
                    'pressure_target': float(chamber_data.get('pressure_target', 0.0)),
                    'pressure_threshold': float(chamber_data.get('pressure_threshold', 0.0)),
                    'pressure_tolerance': float(chamber_data.get('pressure_tolerance', 0.0)),
                    'final_pressure': float(chamber_data.get('final_pressure', 0.0)),
                    'result': bool(chamber_data.get('result', False))
                }
                
                # Add pressure log if available (but limit size)
                if 'pressure_log' in chamber_data:
                    # Store only a sample of pressure readings to save memory
                    pressure_log = chamber_data['pressure_log']
                    if len(pressure_log) > 100:
                        # Sample the pressure log to reduce size
                        sample_step = len(pressure_log) // 100
                        chamber_record['pressure_log'] = pressure_log[::sample_step][:100]
                    else:
                        chamber_record['pressure_log'] = pressure_log
                
                record['chambers'].append(chamber_record)
            
            # Add the record to the in-memory storage
            self.test_records.append(record)
            
            # Enforce the maximum number of records
            if len(self.test_records) > self.max_records:
                self.test_records.pop(0)
            
            # Update statistics
            self.stats['total_tests'] += 1
            if record['overall_result']:
                self.stats['passed_tests'] += 1
            else:
                self.stats['failed_tests'] += 1
            self.stats['last_test_time'] = record['timestamp']
            
            self.logger.info(f"Logged test result: {record['overall_result']} for reference {record['reference']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging test result: {e}")
            return False
    
    def get_recent_tests(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent test results.
        
        Args:
            count: Number of recent test results to retrieve
            
        Returns:
            List of dictionaries containing test results, most recent first
        """
        return self.test_records[-count:][::-1]
    
    def get_test_by_reference(self, reference: str) -> List[Dict[str, Any]]:
        """
        Get test results for a specific reference barcode.
        
        Args:
            reference: Reference barcode to search for
            
        Returns:
            List of dictionaries containing matching test results
        """
        if not reference:
            return []
            
        return [
            record for record in self.test_records
            if record['reference'] == reference
        ]
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about test results.
        
        Returns:
            Dictionary containing test statistics
        """
        # Calculate pass rate
        pass_rate = 0.0
        if self.stats['total_tests'] > 0:
            pass_rate = (self.stats['passed_tests'] / self.stats['total_tests']) * 100
        
        # Return comprehensive statistics
        return {
            'total_tests': self.stats['total_tests'],
            'passed_tests': self.stats['passed_tests'],
            'failed_tests': self.stats['failed_tests'],
            'pass_rate': pass_rate,
            'last_test_time': self.stats['last_test_time'],
            'record_count': len(self.test_records)
        }
    
    def save_to_csv(self, path: Optional[str] = None) -> bool:
        """
        Save all test results to a CSV file.
        
        Args:
            path: Path to save the CSV file (optional, generates default if None)
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        if not self.test_records:
            self.logger.warning("No test records to save")
            return False
            
        try:
            # Generate default filename if not provided
            if not path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_results_{timestamp}.csv"
                path = os.path.join(self.results_dir, filename)
            
            # Create all necessary directories
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Prepare data for CSV export (flatten nested structures)
            flattened_records = []
            for record in self.test_records:
                for chamber in record['chambers']:
                    flat_record = {
                        'timestamp': record['timestamp'],
                        'reference': record['reference'],
                        'test_mode': record['test_mode'],
                        'test_duration': record['test_duration'],
                        'overall_result': 'PASS' if record['overall_result'] else 'FAIL',
                        'chamber_id': chamber['chamber_id'] + 1,  # Convert to 1-based for display
                        'chamber_enabled': chamber['enabled'],
                        'pressure_target': chamber['pressure_target'],
                        'pressure_threshold': chamber['pressure_threshold'],
                        'pressure_tolerance': chamber['pressure_tolerance'],
                        'final_pressure': chamber['final_pressure'],
                        'chamber_result': 'PASS' if chamber['result'] else 'FAIL'
                    }
                    flattened_records.append(flat_record)
            
            # Write to CSV
            with open(path, 'w', newline='') as csvfile:
                if not flattened_records:
                    self.logger.warning("No flattened records to write to CSV")
                    return False
                    
                fieldnames = flattened_records[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(flattened_records)
            
            self.logger.info(f"Saved {len(flattened_records)} test records to {path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving test results to CSV: {e}")
            return False
    
    def save_detailed_test_to_csv(self, test_index: int, path: Optional[str] = None) -> bool:
        """
        Save detailed data for a specific test to a CSV file.
        
        Args:
            test_index: Index of the test in the records list
            path: Path to save the CSV file (optional, generates default if None)
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            if not 0 <= test_index < len(self.test_records):
                self.logger.error(f"Invalid test index: {test_index}")
                return False
                
            record = self.test_records[test_index]
            
            # Generate default filename if not provided
            if not path:
                timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y%m%d_%H%M%S")
                ref = record['reference'].replace(' ', '_')
                filename = f"test_detail_{ref}_{timestamp}.csv"
                path = os.path.join(self.results_dir, filename)
            
            # Create all necessary directories
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Check if we have pressure logs to output
            has_pressure_logs = any('pressure_log' in chamber for chamber in record['chambers'])
            
            if has_pressure_logs:
                # Save with pressure logs in a time-series format
                rows = []
                
                # Find the maximum length of pressure logs
                max_length = 0
                for chamber in record['chambers']:
                    if 'pressure_log' in chamber:
                        max_length = max(max_length, len(chamber['pressure_log']))
                
                # Create header row
                headers = ['sample_index']
                for chamber in record['chambers']:
                    if chamber['enabled']:
                        ch_id = chamber['chamber_id'] + 1  # 1-based for display
                        headers.append(f'chamber{ch_id}_pressure')
                
                # Create data rows
                for i in range(max_length):
                    row = {'sample_index': i}
                    for chamber in record['chambers']:
                        if chamber['enabled'] and 'pressure_log' in chamber:
                            ch_id = chamber['chamber_id'] + 1  # 1-based for display
                            if i < len(chamber['pressure_log']):
                                row[f'chamber{ch_id}_pressure'] = chamber['pressure_log'][i]
                            else:
                                row[f'chamber{ch_id}_pressure'] = None
                    rows.append(row)
                
                # Write to CSV
                with open(path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                # Write a summary since we don't have pressure logs
                with open(path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Test Summary'])
                    writer.writerow(['Timestamp', record['timestamp']])
                    writer.writerow(['Reference', record['reference']])
                    writer.writerow(['Test Mode', record['test_mode']])
                    writer.writerow(['Test Duration', record['test_duration']])
                    writer.writerow(['Overall Result', 'PASS' if record['overall_result'] else 'FAIL'])
                    writer.writerow([])
                    
                    writer.writerow(['Chamber', 'Enabled', 'Target (mbar)', 'Threshold (mbar)', 
                                    'Tolerance (mbar)', 'Final Pressure (mbar)', 'Result'])
                    
                    for chamber in record['chambers']:
                        writer.writerow([
                            f"Chamber {chamber['chamber_id'] + 1}",
                            'Yes' if chamber['enabled'] else 'No',
                            chamber['pressure_target'],
                            chamber['pressure_threshold'],
                            chamber['pressure_tolerance'],
                            chamber['final_pressure'],
                            'PASS' if chamber['result'] else 'FAIL'
                        ])
            
            self.logger.info(f"Saved detailed test data to {path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving detailed test to CSV: {e}")
            return False
    
    def save_last_test_to_csv(self, path: Optional[str] = None) -> bool:
        """
        Save the most recent test result to a CSV file.
        
        Args:
            path: Path to save the CSV file (optional, generates default if None)
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        if not self.test_records:
            self.logger.warning("No test records available")
            return False
            
        return self.save_detailed_test_to_csv(len(self.test_records) - 1, path)
    
    def export_pressure_logs(self, test_index: int, path: Optional[str] = None) -> bool:
        """
        Export pressure logs for a specific test to a CSV file.
        
        Args:
            test_index: Index of the test in the records list
            path: Path to save the CSV file (optional, generates default if None)
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        return self.save_detailed_test_to_csv(test_index, path)
    
    def clear_records(self) -> bool:
        """
        Clear all test records from memory.
        
        Returns:
            bool: True if records were cleared successfully
        """
        try:
            self.test_records = []
            self.logger.info("Test records cleared from memory")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing test records: {e}")
            return False
    
    def export_json(self, path: Optional[str] = None, count: int = None) -> bool:
        """
        Export test records to a JSON file.
        
        Args:
            path: Path to save the JSON file (optional, generates default if None)
            count: Number of most recent records to export (None for all)
            
        Returns:
            bool: True if export was successful, False otherwise
        """
        try:
            # Generate default filename if not provided
            if not path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_results_{timestamp}.json"
                path = os.path.join(self.results_dir, filename)
            
            # Create all necessary directories
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Get records to export
            if count is None:
                records_to_export = self.test_records
            else:
                records_to_export = self.test_records[-count:]
            
            # Convert datetime objects to strings for JSON serialization
            json_data = {
                'statistics': self.get_test_statistics(),
                'records': records_to_export
            }
            
            with open(path, 'w') as jsonfile:
                json.dump(json_data, jsonfile, indent=2)
            
            self.logger.info(f"Exported {len(records_to_export)} test records to {path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting test records to JSON: {e}")
            return False
