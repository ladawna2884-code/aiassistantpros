#!/usr/bin/env python3
"""Test Supabase authentication directly."""
import os
from supabase import create_client

# Load env vars
os.environ.setdefault("SUPABASE_URL", "https://selufuikaahpuapvuebw.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlbHVmdWlrYWFocHVhcHZ1ZWJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUwMzQwMDgsImV4cCI6MjA4MDYxMDAwOH0.71Q2t4MxGYVCBrbyRGlHv2LalffPCVwL17ScB0AZfn0")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"[INFO] Supabase URL: {url}")
print(f"[INFO] Supabase Key present: {bool(key)}")

try:
    supabase = create_client(url, key)
    print("[SUCCESS] Supabase client initialized")
    
    # Try to sign in with a test account
    print("\n[TESTING] Attempting sign-in with test@example.com...")
    result = supabase.auth.sign_in_with_password({
        "email": "test@example.com",
        "password": "password123"
    })
    
    print(f"[RESULT] Type: {type(result)}")
    print(f"[RESULT] Content: {result}")
    
    # Check for error
    if hasattr(result, 'error') and result.error:
        print(f"[ERROR] Auth error: {result.error}")
    elif isinstance(result, dict) and result.get('error'):
        print(f"[ERROR] Auth error: {result.get('error')}")
    else:
        print("[SUCCESS] Sign-in appeared successful")
        
except Exception as e:
    print(f"[EXCEPTION] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
