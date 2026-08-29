import sys
import os

# Add root directory to sys.path to import server.py safely
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app
