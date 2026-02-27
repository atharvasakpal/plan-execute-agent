"""
FastAPI wrapper for Plan-Execute Agent
Production-ready API with error handling, logging, and async support
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.agent import PlanExecuteAgent
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Plan-Execute API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    yield
    # Shutdown
    logger.info("Shutting down Plan-Execute API...")

# Initialize FastAPI app
app = FastAPI(
    title="Plan-Execute Agent API",
    description="Production-ready AI agent with multi-step reasoning and tool orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class TaskRequest(BaseModel):
    task: str = Field(..., min_length=10, max_length=1000, description="Task description")
    user_id: Optional[str] = Field(None, description="Optional user identifier for tracking")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task": "Write a strategic one-pager for building an AI startup",
                "user_id": "user_123"
            }
        }

class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[str] = None
    plan_steps: Optional[list[str]] = None
    error: Optional[str] = None
    
class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str

# Initialize agent (singleton pattern)
agent = PlanExecuteAgent()

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Plan-Execute Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for AWS load balancers"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.ENVIRONMENT
    )

@app.post("/api/v1/execute", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """
    Execute a task using the plan-execute agent
    
    - **task**: The task description (10-1000 characters)
    - **user_id**: Optional user identifier for tracking
    
    Returns the execution result with plan steps and final response
    """
    try:
        logger.info(f"Received task request: {request.task[:50]}...")
        
        # Execute agent
        result = await agent.execute(request.task)
        
        logger.info(f"Task completed successfully")
        
        return TaskResponse(
            task_id=result.get("task_id", "unknown"),
            status="completed",
            result=result.get("final_response"),
            plan_steps=result.get("plan_steps"),
            error=None
        )
        
    except Exception as e:
        logger.error(f"Error executing task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute task: {str(e)}"
        )

@app.post("/api/v1/execute-async", response_model=dict)
async def execute_task_async(request: TaskRequest, background_tasks: BackgroundTasks):
    """
    Execute a task asynchronously in the background
    Returns immediately with a task_id
    """
    import uuid
    task_id = str(uuid.uuid4())
    
    # Add task to background
    background_tasks.add_task(agent.execute_background, task_id, request.task)
    
    logger.info(f"Task {task_id} added to background queue")
    
    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Task is being processed in the background"
    }

@app.get("/api/v1/task/{task_id}", response_model=dict)
async def get_task_status(task_id: str):
    """Get status of an async task"""
    # In production, this would query a database or cache
    return {
        "task_id": task_id,
        "status": "not_implemented",
        "message": "Async task tracking requires database setup"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )
