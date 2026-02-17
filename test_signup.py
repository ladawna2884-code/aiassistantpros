#!/usr/bin/env python3
"""Test Supabase signup."""
import os
from supabase import create_client

os.environ.setdefault("SUPABASE_URL", "https://selufuikaahpuapvuebw.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlbHVmdWlrYWFocHVhcHZ1ZWJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUwMzQwMDgsImV4cCI6MjA4MDYxMDAwOH0.71Q2t4MxGYVCBrbyRGlHv2LalffPCVwL17ScB0AZfn0")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

print("[TESTING] Attempting signup with testuser@demo.com...")
try:
    result = supabase.auth.sign_up({
        "email": "testuser@demo.com",
        "password": "TestPassword123!",
        "options": {
            "email_redirect_to": "http://127.0.0.1:5555/login"
        }
    })
    
    print(f"[RESULT] Type: {type(result)}")
    print(f"[RESULT] Content: {result}")
    
    # Check for user
    if hasattr(result, 'user') and result.user:
        print(f"[SUCCESS] User created with ID: {result.user.id}")
    elif isinstance(result, dict) and result.get('user'):
        print(f"[SUCCESS] User created")
    else:
        print("[INFO] Check result above for details")
        
except Exception as e:
    print(f"[EXCEPTION] {type(e).__name__}: {e}")
