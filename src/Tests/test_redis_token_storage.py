"""
Test Redis Token Storage

This script tests the Redis token storage functionality to ensure
tokens are properly stored, retrieved, and refreshed.
"""

import os
import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
try:
    import load_env
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

def test_redis_connection():
    """Test basic Redis connection"""
    print("\n=== Testing Redis Connection ===")
    try:
        from mcp_redis_config import get_redis_token_manager
        
        redis_manager = get_redis_token_manager()
        if redis_manager.health_check():
            print("✓ Redis connection successful")
            return True
        else:
            print("✗ Redis connection failed")
            return False
    except Exception as e:
        print(f"✗ Error connecting to Redis: {e}")
        return False

def test_token_storage():
    """Test storing and retrieving tokens"""
    print("\n=== Testing Token Storage ===")
    try:
        from mcp_redis_config import get_redis_token_manager
        
        redis_manager = get_redis_token_manager()
        
        # Test data
        test_token = "test-token-" + str(int(time.time()))
        test_scope = "https://graph.microsoft.com/.default"
        expires_on = int(datetime.now().timestamp()) + 3600  # 1 hour
        
        # Store token
        success = redis_manager.store_token(
            token=test_token,
            expires_on=expires_on,
            scope=test_scope,
            metadata={"test": True}
        )
        
        if success:
            print(f"✓ Token stored successfully")
        else:
            print("✗ Failed to store token")
            return False
        
        # Retrieve token
        token_data = redis_manager.get_token(test_scope)
        
        if token_data and token_data.get("token") == test_token:
            print(f"✓ Token retrieved successfully")
            print(f"  Token: {token_data.get('token')[:20]}...")
            print(f"  Expires on: {token_data.get('expires_on')}")
            print(f"  Scope: {token_data.get('scope')}")
            return True
        else:
            print("✗ Failed to retrieve token")
            return False
            
    except Exception as e:
        print(f"✗ Error in token storage test: {e}")
        return False

def test_agent_authentication():
    """Test agent authentication and token acquisition"""
    print("\n=== Testing Agent Authentication ===")
    try:
        from agent_auth_manager import get_auth_manager
        
        auth_manager = get_auth_manager()
        
        # Try to get a token
        token = auth_manager.get_agent_user_token(
            "https://graph.microsoft.com/.default"
        )
        
        if token:
            print("✓ Successfully acquired agent token")
            print(f"  Token preview: {token[:30]}...")
            return True
        else:
            print("✗ Failed to acquire agent token")
            print("  Ensure AGENT_USER_NAME and AGENT_PASSWORD are set")
            return False
            
    except Exception as e:
        print(f"✗ Error in agent authentication: {e}")
        return False

def test_token_refresh_service():
    """Test token refresh service"""
    print("\n=== Testing Token Refresh Service ===")
    try:
        from token_refresh_service import (
            get_token_refresh_service,
            start_token_refresh_service,
            stop_token_refresh_service
        )
        
        # Start the service
        start_token_refresh_service()
        print("✓ Token refresh service started")
        
        # Let it run for a bit
        time.sleep(2)
        
        # Stop the service
        stop_token_refresh_service()
        print("✓ Token refresh service stopped")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing refresh service: {e}")
        return False

def test_token_api():
    """Test token API endpoints (requires running function app)"""
    print("\n=== Testing Token API Endpoints ===")
    print("  Note: This requires the function app to be running")
    print("  Start with: func start")
    
    try:
        import requests
        
        base_url = "http://localhost:7071/api"
        
        # Test health endpoint
        response = requests.get(f"{base_url}/tokens/health", timeout=5)
        if response.status_code == 200:
            print("✓ Health endpoint accessible")
            health = response.json()
            print(f"  Status: {health.get('status')}")
            print(f"  Redis connected: {health.get('redis_connected')}")
            print(f"  Active tokens: {health.get('active_token_count')}")
        else:
            print("✗ Health endpoint returned error")
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to function app")
        print("  Ensure the function app is running with: func start")
    except Exception as e:
        print(f"✗ Error testing API: {e}")

def main():
    """Run all tests"""
    print("Redis Token Storage Test Suite")
    print("=" * 50)
    
    # Check environment variables
    print("\n=== Environment Check ===")
    required_vars = [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID", 
        "AZURE_CLIENT_SECRET",
        "REDIS_HOST",
        "REDIS_PASSWORD"
    ]
    
    optional_vars = [
        "AGENT_USER_NAME",
        "AGENT_PASSWORD"
    ]
    
    missing_required = []
    for var in required_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            print(f"✗ {var} is missing")
            missing_required.append(var)
    
    print("\nOptional variables:")
    for var in optional_vars:
        if os.getenv(var):
            print(f"✓ {var} is set")
        else:
            print(f"  {var} is not set (agent auth may not work)")
    
    if missing_required:
        print(f"\n⚠️  Missing required variables: {', '.join(missing_required)}")
        print("Some tests may fail without these variables")
    
    # Run tests
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Redis connection
    total_tests += 1
    if test_redis_connection():
        tests_passed += 1
    
    # Test 2: Token storage
    total_tests += 1
    if test_token_storage():
        tests_passed += 1
    
    # Test 3: Agent authentication (optional)
    if os.getenv("AGENT_USER_NAME") and os.getenv("AGENT_PASSWORD"):
        total_tests += 1
        if test_agent_authentication():
            tests_passed += 1
    else:
        print("\n=== Skipping Agent Authentication Test ===")
        print("  AGENT_USER_NAME and AGENT_PASSWORD not set")
    
    # Test 4: Token refresh service
    total_tests += 1
    if test_token_refresh_service():
        tests_passed += 1
    
    # Test 5: API endpoints
    test_token_api()
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("\n✓ All tests passed!")
    else:
        print(f"\n⚠️  {total_tests - tests_passed} tests failed")

if __name__ == "__main__":
    main() 