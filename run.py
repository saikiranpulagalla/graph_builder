"""
Simple runner script for graph_builder.
Run this from inside the graph_builder folder: python run.py
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import graph_builder as a package
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Now run the main module
from graph_builder.__main__ import main

if __name__ == "__main__":
    main()
