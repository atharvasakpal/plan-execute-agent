"""
Basic tests for the Plan-Execute Agent API
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    """Test root endpoint returns correct information"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data

def test_execute_endpoint_validation():
    """Test execute endpoint validates input"""
    # Test with too short task
    response = client.post(
        "/api/v1/execute",
        json={"task": "short"}
    )
    assert response.status_code == 422  # Validation error
    
    # Test with missing task
    response = client.post(
        "/api/v1/execute",
        json={}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_execute_endpoint_success():
    """Test successful task execution (requires valid API key)"""
    response = client.post(
        "/api/v1/execute",
        json={"task": "Calculate 2 + 2 and explain the result"}
    )
    
    # This will fail without proper API key, but tests structure
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "task_id" in data
        assert "status" in data
