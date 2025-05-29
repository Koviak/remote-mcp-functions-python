#!/usr/bin/env python3
"""
Test script to verify that both MCP tools and HTTP endpoints are properly
registered and working.
"""

import sys
import requests
import time
import json

sys.path.append('src')


def test_registration():
    """Test that both MCP tools and HTTP endpoints are registered"""
    
    print("Testing Function Registration...")
    print("=" * 50)
    
    # Import the app to trigger registration
    try:
        from src.function_app import app  # noqa: F401
        print("✅ Successfully imported function app")
    except Exception as e:
        print(f"❌ Failed to import function app: {e}")
        return
    
    # Count MCP tools by looking at the source file
    mcp_count = 0
    http_count = 0
    
    try:
        with open('src/function_app.py', 'r') as f:
            content = f.read()
            
        # Count MCP tools (generic_trigger decorators)
        mcp_count = content.count('@app.generic_trigger(')
        
        # Count MCP tools from additional_tools.py
        try:
            with open('src/additional_tools.py', 'r') as f:
                additional_content = f.read()
            additional_mcp_count = additional_content.count(
                '@app.generic_trigger(')
            mcp_count += additional_mcp_count
        except FileNotFoundError:
            print("⚠️  additional_tools.py not found")
        
        # Count HTTP endpoints from http_endpoints.py
        with open('src/http_endpoints.py', 'r') as f:
            http_content = f.read()
            
        # Count app.route decorators in the registration function
        http_count = http_content.count('app.route(')
        
        print(f"MCP Tools Found: {mcp_count}")
        print(f"HTTP Endpoints Found: {http_count}")
        print(f"Total Functions: {mcp_count + http_count}")
        print()
        
        # Expected counts
        expected_mcp = 44  # 34 in function_app + 10 in additional_tools
        expected_http = 44  # Should match MCP tools
        
        print("Registration Status:")
        mcp_status = ("✅ OK" if mcp_count >= expected_mcp 
                      else "⚠️  MISSING")
        http_status = ("✅ OK" if http_count >= expected_http 
                       else "⚠️  MISSING")
        print(f"   MCP Tools: {mcp_count}/{expected_mcp} ({mcp_status})")
        print(f"   HTTP Endpoints: {http_count}/{expected_http} "
              f"({http_status})")
        
        if mcp_count >= expected_mcp and http_count >= expected_http:
            print("\n🎉 SUCCESS: All functions are properly registered!")
        else:
            print("\n⚠️  ISSUE: Some functions may be missing!")
            
    except Exception as e:
        print(f"❌ Error analyzing function registration: {e}")
        print("⚠️  Could not access function registry - this is expected "
              "with Azure Functions")
        print("   The HTTP endpoint tests below will verify actual "
              "functionality")


def test_http_endpoints():
    """Test actual HTTP endpoint functionality"""
    
    print("\nTesting HTTP Endpoint Functionality...")
    print("=" * 50)
    
    # Common ports where Azure Functions might be running
    test_ports = [7071, 7072, 7073, 7074, 7075, 7076]
    base_url = None
    
    # Find which port the function is running on
    print("🔍 Searching for running Azure Functions instance...")
    for port in test_ports:
        try:
            test_url = f"http://localhost:{port}/api/hello"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                base_url = f"http://localhost:{port}/api"
                print(f"✅ Found Azure Functions running on port {port}")
                break
        except requests.exceptions.RequestException:
            continue
    
    if not base_url:
        print("❌ No running Azure Functions instance found on common ports")
        print("   Please start Azure Functions with: func start --port 7071")
        return
    
    # Test endpoints
    endpoints_to_test = [
        ("hello", "GET", "Hello endpoint test"),
        ("groups", "GET", "List Microsoft 365 groups"),
        ("users", "GET", "List users"),
        ("groups/with-planner", "GET", "List groups with Planner"),
        ("groups/check-planner?displayName=TestGroup", "GET", 
         "Check group Planner status"),
        ("plans?groupId=test-group-id", "GET", "List plans for group"),
        ("tasks?planId=test-plan-id", "GET", "List tasks in plan"),
        ("me/tasks", "GET", "List my tasks"),
        ("plans/test-plan-id/buckets", "GET", "List buckets in plan")
    ]
    
    print(f"\n🧪 Testing endpoints at {base_url}...")
    print("-" * 40)
    
    for endpoint, method, description in endpoints_to_test:
        url = f"{base_url}/{endpoint}"
        print(f"\nTesting: {method} {url}")
        print(f"Description: {description}")
        
        try:
            start_time = time.time()
            
            if method == "GET":
                response = requests.get(url, timeout=30)
            elif method == "POST":
                response = requests.post(url, json={}, timeout=30)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"Status: {response.status_code}")
            print(f"Duration: {duration:.2f} seconds")
            
            if response.status_code == 200:
                print("✅ SUCCESS")
                
                # For groups endpoint, show some details
                if endpoint == "groups" and response.headers.get('content-type', '').startswith('application/json'):
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            print(f"   Found {len(data)} groups")
                            if data:
                                print(f"   First group: {data[0].get('displayName', 'N/A')}")
                        else:
                            print(f"   Response type: {type(data)}")
                    except json.JSONDecodeError:
                        print("   Response is not valid JSON")
                
            elif response.status_code == 401:
                print("⚠️  AUTHENTICATION REQUIRED")
                print("   This is expected - Azure AD credentials needed")
            elif response.status_code >= 400:
                print(f"❌ ERROR: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
            else:
                print(f"ℹ️  Unexpected status: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("⏰ TIMEOUT (>30 seconds)")
            print("   This indicates a potential issue with the endpoint")
        except requests.exceptions.ConnectionError:
            print("❌ CONNECTION ERROR")
            print("   Azure Functions may not be running")
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {str(e)}")
    
    print("\n" + "=" * 50)
    print("HTTP Endpoint Testing Complete")


def main():
    """Main test function"""
    test_registration()
    test_http_endpoints()


if __name__ == "__main__":
    main() 