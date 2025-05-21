#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Printer module for the Multi-Chamber Test application.

This module provides a PrinterManager class that interfaces with a USB
thermal printer (typically a Zebra printer) to print test results.
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import usb.core
import usb.util

from multi_chamber_test.config.constants import PRINTER_CONFIG

class PrinterManager:
    """
    Manager for USB thermal printer operations.
    
    This class provides methods to connect to a USB printer (typically
    a Zebra printer) and send ZPL commands to print test results.
    """
    
    def __init__(self, vendor_id: int = PRINTER_CONFIG['VENDOR_ID'], 
                product_id: int = PRINTER_CONFIG['PRODUCT_ID']):
        """
        Initialize the PrinterManager with the specified USB device IDs.
        
        Args:
            vendor_id: USB vendor ID (default: from constants)
            product_id: USB product ID (default: from constants)
        """
        self.logger = logging.getLogger('PrinterManager')
        self._setup_logger()
        
        self.VENDOR_ID = vendor_id
        self.PRODUCT_ID = product_id
        self.printer = None
        self.ep = None
    
    def _setup_logger(self):
        """Configure logging for the printer manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.logger.setLevel(logging.INFO)
    
    def connect(self) -> bool:
        """
        Connect to the printer with enhanced error handling.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            # Find the printer
            self.printer = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID)
            
            if self.printer is None:
                self.logger.error("Printer not found")
                return False
            
            # Detach kernel driver if active
            if self.printer.is_kernel_driver_active(0):
                try:
                    self.printer.detach_kernel_driver(0)
                except usb.core.USBError as e:
                    self.logger.error(f"Failed to detach kernel driver: {e}")
                    return False
            
            # Set configuration
            try:
                self.printer.set_configuration()
            except usb.core.USBError as e:
                self.logger.error(f"Failed to set configuration: {e}")
                return False
            
            # Get endpoint
            cfg = self.printer.get_active_configuration()
            intf = cfg[(0, 0)]
            
            self.ep = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: 
                    usb.util.endpoint_direction(e.bEndpointAddress) == 
                    usb.util.ENDPOINT_OUT
            )
            
            if self.ep is None:
                self.logger.error("Printer endpoint not found")
                return False
                
            self.logger.info("Printer connected successfully")
            return True
            
        except usb.core.USBError as e:
            self.logger.error(f"USB Error during printer connection: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during printer connection: {e}")
            return False
    
    def print_test_results(self, test_data: List[Dict[str, Any]]) -> bool:
        """
        Print test results with specific label format only if all chambers pass
        
        Args:
            test_data: List of dictionaries containing test results for each chamber
        
        Returns:
            bool: True if printing was successful, False otherwise
        """
        try:
            # Check if all chambers passed
            all_passed = all(chamber.get('result') == 'PASS' 
                            for chamber in test_data 
                            if chamber.get('enabled', True))
            
            # If any chamber failed, don't print and return
            if not all_passed:
                self.logger.info("Not printing results - one or more chambers failed")
                return False
    
            # Only proceed with printing if all chambers passed
            if not self.printer:
                if not self.connect():
                    return False
    
            # Get current timestamp
            now = datetime.now()
            date_str = now.strftime("%d/%m/%Y")
            time_str = now.strftime("%H:%M:%S")
            
            # Get reference from first chamber - remove 'G' prefix if it exists
            reference = test_data[0].get('reference', '')
            
            # Create the exact label format
            commands = [
                "^XA",
                "^PW799^LH70,10",
                "^A0N,25,25^FO70,15^FDLEAR - KENITRA^FS",
                "^A0N,25,25^FO70,50^FDBODY V216^FS",
                f"^A0N,25,25^FO70,210^FDDATE:{date_str}^FS",
                f"^A0N,25,25^FO70,240^FDTime:{time_str}^FS",
                # Reference in main text - remove 'G' prefix if present
                f"^A0N,50,50^FO70,140^FD{reference[3:] if reference and len(reference) > 3 and reference.startswith('G') else reference}^FS",
                # Result will always be PASS at this point
                "^A0N,50,50^FO70,280^FDGROMMET TEST PASS^FS",
                # Barcodes with 'G' prefix
                "^FT570,6",
                f"^BY1^BCR,50,Y,N,N^FDG{reference}^FS",
                "^FT0,350",
                f"^BY1^BCB,50,Y,N,N^FDG{reference}^FS",
                "^XZ"
            ]
            
            # Send commands with error handling
            for command in commands:
                try:
                    self.logger.debug(f"Sending command: {command}")
                    self.ep.write(command.encode('utf-8'))
                    time.sleep(0.1)  # Small delay between commands
                except usb.core.USBError as e:
                    self.logger.error(f"USB Error while sending print command: {e}")
                    return False
                except Exception as e:
                    self.logger.error(f"Error sending print command: {e}")
                    return False
            
            self.logger.info("Test results printed successfully")
            return True
                    
        except Exception as e:
            self.logger.error(f"Printing error: {e}")
            return False
        finally:
            try:
                self.close()
            except Exception as e:
                self.logger.error(f"Error closing printer connection: {e}")
    
    def print_calibration_report(self, calibration_data: Dict[str, Any]) -> bool:
        """
        Print a calibration report.
        
        Args:
            calibration_data: Dictionary containing calibration data with keys:
                             'chamber_number', 'date', 'voltage_offset',
                             'voltage_multiplier', 'points'
            
        Returns:
            bool: True if printing was successful, False otherwise
        """
        try:
            if not self.printer:
                if not self.connect():
                    return False
            
            chamber_num = calibration_data.get('chamber_number', 'N/A')
            date = calibration_data.get('date', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            voltage_offset = calibration_data.get('voltage_offset', 'N/A')
            voltage_multiplier = calibration_data.get('voltage_multiplier', 'N/A')
            points = calibration_data.get('points', [])
            
            # Create ZPL commands for the label
            commands = [
                "^XA",                    # Start label
                "^MMT",                   # Set tear-off mode
                "^PW400",                 # Set print width (50mm = 400 dots)
                "^LL800",                 # Increased label length for larger text
                "^LS0",                   # No label shift
                f"~TA{PRINTER_CONFIG['TEAR_OFFSET']}",  # Set tear-off position adjustment
                "^MNY",                   # Enable tear-off mode
                
                # Title - larger font
                f"^FO20,20^A0N,35,35^FDCalibration Report^FS",
                f"^FO20,60^A0N,25,25^FDChamber {chamber_num}^FS",
                f"^FO20,100^A0N,20,20^FD{date}^FS",
                
                # Calibration parameters
                f"^FO20,150^A0N,25,25^FDOffset: {voltage_offset}^FS",
                f"^FO20,180^A0N,25,25^FDMultiplier: {voltage_multiplier}^FS",
                
                # Horizontal line
                f"^FO20,210^GB360,3,3^FS",
                
                # Calibration points header
                f"^FO20,230^A0N,25,25^FDCalibration Points:^FS",
            ]
            
            # Add calibration points
            y_pos = 270
            for i, point in enumerate(points):
                pressure = point.get('pressure', 'N/A')
                voltage = point.get('voltage', 'N/A')
                
                commands.append(
                    f"^FO30,{y_pos}^A0N,20,20^FDPoint {i+1}: {pressure} mbar - {voltage} V^FS"
                )
                y_pos += 30
            
            # End label
            commands.extend([
                "^PQ1,0,1,Y",             # Print 1 label with auto-feed to tear position
                "^XZ"                     # End label
            ])
            
            # Send each command with error handling
            for command in commands:
                try:
                    self.ep.write(command.encode('utf-8'))
                    time.sleep(0.1)  # Small delay between commands
                except usb.core.USBError as e:
                    self.logger.error(f"USB Error while sending print command: {e}")
                    return False
                except Exception as e:
                    self.logger.error(f"Error sending print command: {e}")
                    return False
            
            self.logger.info(f"Calibration report printed successfully for chamber {chamber_num}")
            return True
                
        except Exception as e:
            self.logger.error(f"Printing error: {e}")
            return False
        finally:
            try:
                self.close()
            except Exception as e:
                self.logger.error(f"Error closing printer connection: {e}")
    
    def print_simple_status(self, message: str) -> bool:
        """
        Print a simple status message.
        
        Args:
            message: Status message to print
            
        Returns:
            bool: True if printing was successful, False otherwise
        """
        try:
            if not self.printer:
                if not self.connect():
                    return False
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create ZPL commands for the label
            commands = [
                "^XA",                    # Start label
                "^MMT",                   # Set tear-off mode
                "^PW400",                 # Set print width (50mm = 400 dots)
                "^LL300",                 # Label length for short message
                "^LS0",                   # No label shift
                f"~TA{PRINTER_CONFIG['TEAR_OFFSET']}",  # Set tear-off position adjustment
                "^MNY",                   # Enable tear-off mode
                
                # Date/time
                f"^FO20,20^A0N,20,20^FD{timestamp}^FS",
                
                # Message
                f"^FO20,60^A0N,30,30^FD{message}^FS",
                
                # End label
                "^PQ1,0,1,Y",             # Print 1 label with auto-feed to tear position
                "^XZ"                     # End label
            ]
            
            # Send each command with error handling
            for command in commands:
                try:
                    self.ep.write(command.encode('utf-8'))
                    time.sleep(0.1)  # Small delay between commands
                except usb.core.USBError as e:
                    self.logger.error(f"USB Error while sending print command: {e}")
                    return False
                except Exception as e:
                    self.logger.error(f"Error sending print command: {e}")
                    return False
            
            self.logger.info("Status message printed successfully")
            return True
                
        except Exception as e:
            self.logger.error(f"Printing error: {e}")
            return False
        finally:
            try:
                self.close()
            except Exception as e:
                self.logger.error(f"Error closing printer connection: {e}")
    
    def test_connection(self) -> bool:
        """
        Test the printer connection by printing a small test label.
        
        Returns:
            bool: True if test was successful, False otherwise
        """
        try:
            if not self.printer:
                if not self.connect():
                    return False
            
            # Simple test label
            command = (
                "^XA"                             # Start label
                "^FO50,50^A0N,30,30^FDPrinter Test^FS"  # Add text
                "^FO50,100^A0N,20,20^FD" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "^FS"  # Add timestamp
                "^PQ1,0,1,Y"                      # Print 1 label
                "^XZ"                             # End label
            )
            
            try:
                self.ep.write(command.encode('utf-8'))
                self.logger.info("Printer test successful")
                return True
            except usb.core.USBError as e:
                self.logger.error(f"USB Error during printer test: {e}")
                return False
            except Exception as e:
                self.logger.error(f"Error during printer test: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Printer test error: {e}")
            return False
        finally:
            try:
                self.close()
            except Exception as e:
                self.logger.error(f"Error closing printer connection: {e}")
    
    def is_printer_available(self) -> bool:
        """
        Check if the printer is available.
        
        Returns:
            bool: True if printer is available, False otherwise
        """
        try:
            printer = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID)
            return printer is not None
        except Exception as e:
            self.logger.error(f"Error checking printer availability: {e}")
            return False
    
    def close(self):
        """Clean up printer connection resources."""
        if self.printer:
            try:
                usb.util.dispose_resources(self.printer)
            except Exception as e:
                self.logger.error(f"Error disposing printer resources: {e}")
            finally:
                self.printer = None
                self.ep = None
