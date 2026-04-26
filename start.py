#!/usr/bin/env python3
"""
Quick Start Script for Travel AI Agent
Run this to start the application locally
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import pydantic
        print("✓ All core dependencies installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def setup_database():
    """Ensure database directory exists"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Database directory ready: {data_dir}")

def check_env():
    """Check environment variables"""
    required = []
    optional = ['TRAVEL_LLM_API_KEY', 'TRAVEL_CONSENT_SECRET', 'OPENWEATHER_API_KEY']
    
    missing_required = [var for var in required if not os.getenv(var)]
    missing_optional = [var for var in optional if not os.getenv(var)]
    
    if missing_required:
        print(f"✗ Missing required env vars: {missing_required}")
        return False
    
    if missing_optional:
        print(f"⚠ Optional env vars not set: {missing_optional}")
        print("  The app will work but some features may be limited")
    else:
        print("✓ All optional API keys configured")
    
    return True

def start_app():
    """Start the application"""
    print("\n🚀 Starting Travel AI Agent...")
    print("=" * 50)
    print("API Documentation: http://localhost:8000/docs")
    print("Web App: http://localhost:8000/app")
    print("Health Check: http://localhost:8000/health")
    print("=" * 50 + "\n")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app:app", 
            "--reload", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ])
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")

def main():
    """Main entry point"""
    print("🌍 Travel AI Agent - Quick Start\n")
    
    if not check_dependencies():
        sys.exit(1)
    
    setup_database()
    check_env()
    
    start_app()

if __name__ == "__main__":
    main()
