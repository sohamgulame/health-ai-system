#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import mysql.connector

# Load .env from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

print("=" * 60)
print("HealthGuard System Health Check")
print("=" * 60)

# Database Connection Test
print("\n1. Database Connection Test")
print("-" * 40)
try:
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "health_db")
    )
    print("✓ Database: Connected")
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM readings")
    result = cursor.fetchone()
    total_readings = result['total'] if result else 0
    print(f"✓ Total readings in database: {total_readings}")
    
    cursor.close()
    db.close()
    db_status = True
except Exception as e:
    print(f"❌ Database Error: {str(e)}")
    db_status = False

# API Key Check
print("\n2. NVIDIA API Key Test")
print("-" * 40)
api_key = os.getenv("NVIDIA_API_KEY")
if api_key:
    print(f"✓ API Key configured: {api_key[:30]}...")
    api_status = True
else:
    print("❌ API Key not found")
    api_status = False

# Configuration Check
print("\n3. Configuration Check")
print("-" * 40)
print(f"✓ DB_HOST: {os.getenv('DB_HOST', 'NOT SET')}")
print(f"✓ DB_USER: {os.getenv('DB_USER', 'NOT SET')}")
print(f"✓ DB_NAME: {os.getenv('DB_NAME', 'NOT SET')}")
print(f"✓ NVIDIA API: {'Configured' if api_key else 'NOT SET'}")

# Summary
print("\n" + "=" * 60)
if db_status and api_status:
    print("✓ System Status: ALL SYSTEMS OPERATIONAL ✓")
else:
    print("⚠ System Status: CHECK CONFIGURATION")
print("=" * 60)
