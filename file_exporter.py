import os
import csv
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

class FileExporter:
    """
    Utility class to export test result data to CSV on a USB stick or local path.
    """

    def __init__(self, usb_mount_root: str = "/media"):
        self.logger = logging.getLogger("FileExporter")
        self._setup_logger()
        self.usb_mount_root = usb_mount_root
        self._psutil_available = self._check_psutil()

    def _setup_logger(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
    def _check_psutil(self):
        """Check if psutil is available"""
        try:
            import psutil
            return True
        except ImportError:
            self.logger.warning("psutil module not found. USB detection will be limited.")
            return False

    def find_usb_path(self) -> Optional[str]:
        """
        Try to detect a mounted USB drive.

        Returns:
            str or None: Path to the mounted USB directory, or None if not found.
        """
        try:
            for root, dirs, _ in os.walk(self.usb_mount_root):
                for d in dirs:
                    path = os.path.join(root, d)
                    if os.path.ismount(path):
                        self.logger.info(f"Detected USB device: {path}")
                        return path
            self.logger.warning("No USB mount point found.")
            return None
        except Exception as e:
            self.logger.error(f"Error detecting USB path: {e}")
            return None

    def export_results(self, test_results: List[Dict[str, Any]]) -> bool:
        """
        Export the given test results to a CSV file.

        Args:
            test_results: List of dictionaries containing test data

        Returns:
            bool: True if export succeeded, False otherwise
        """
        usb_path = self.find_usb_path()
        if not usb_path:
            self.logger.error("No USB stick detected for export.")
            return False

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.csv"
        file_path = os.path.join(usb_path, filename)

        try:
            if not test_results:
                self.logger.warning("No test results to export.")
                return False

            # Determine fieldnames from the first result entry
            fieldnames = test_results[0].keys()

            with open(file_path, mode='w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(test_results)

            self.logger.info(f"Test results exported successfully to {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to export test results: {e}")
            return False
            
    def is_usb_connected(self) -> bool:
        """Detect whether a USB drive is mounted."""
        try:
            # Method 1: Use psutil if available
            if self._psutil_available:
                return any('/media/' in path for path in self._list_mount_points())
                
            # Method 2: Fallback to manual checking of known USB paths
            return self._check_manual_usb_paths()
        except Exception as e:
            self.logger.error(f"Error checking USB connection: {e}")
            return False
        
    def _check_manual_usb_paths(self) -> bool:
        """Manual check for USB paths without using psutil"""
        try:
            # Common USB mount points to check
            common_paths = [
                "/media/usb",
                "/media/USB",
                "/media/Bot/USB",
                "/media/Bot/usb",
                self.usb_mount_root
            ]
            
            # Check if any directory exists under the mount root
            if os.path.exists(self.usb_mount_root):
                for item in os.listdir(self.usb_mount_root):
                    path = os.path.join(self.usb_mount_root, item)
                    if os.path.ismount(path):
                        return True
            
            # Check common mount paths
            for path in common_paths:
                if os.path.exists(path) and os.path.ismount(path):
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error in manual USB path check: {e}")
            return False
    
    def _list_mount_points(self):
        """Get list of mount points using psutil"""
        try:
            import psutil
            return [part.mountpoint for part in psutil.disk_partitions()]
        except ImportError:
            self.logger.error("psutil module not available for mount point detection")
            return []
        except Exception as e:
            self.logger.error(f"Error listing mount points: {e}")
            return []
            
    # Add these placeholder methods for compatibility with the settings_tab
    def export_all_tests(self) -> bool:
        """Export all test results (placeholder)"""
        self.logger.warning("export_all_tests not fully implemented")
        return False
        
    def export_last_test(self) -> bool:
        """Export last test result (placeholder)"""
        self.logger.warning("export_last_test not fully implemented")
        return False