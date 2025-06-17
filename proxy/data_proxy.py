"""
Data Proxy - Main entry point
This script initializes and runs the MQTT Client GUI application
"""
import tkinter as tk
import sys
import os

# Ensure modules directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the GUI module
from modules.gui import MQTTClientGUI

def main():
    """Initialize and run the application"""
    root = tk.Tk()
    app = MQTTClientGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
