#!/usr/bin/env python3
"""
Quick script to run Streamlit v2 frontend
"""

import subprocess
import sys

def main():
    print("🚀 Starting Streamlit Frontend v2...")
    print("📍 URL: http://localhost:8501")
    print("🔄 Press Ctrl+C to stop")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "streamlit_frontend_v2.py",
            "--server.port=8501",
            "--server.address=0.0.0.0"
        ])
    except KeyboardInterrupt:
        print("\n✅ Streamlit stopped")

if __name__ == "__main__":
    main()
