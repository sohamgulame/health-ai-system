#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from current directory
load_dotenv()

print("=" * 60)
print("NVIDIA API Key Test")
print("=" * 60)

# Check if API key is loaded
api_key = os.getenv("NVIDIA_API_KEY")
if not api_key:
    print("❌ ERROR: NVIDIA_API_KEY not found in .env file")
    sys.exit(1)

print(f"✓ API Key found: {api_key[:30]}...")

# Test connection
print("\nTesting NVIDIA API connection...")
try:
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    
    # Simple test call
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Say 'API Working'"}],
        temperature=0.2,
        max_tokens=50,
        stream=False
    )
    
    print("✓ API Connection: SUCCESS ✓")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ API Connection: FAILED")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All tests passed! API Key is working correctly.")
print("=" * 60)
