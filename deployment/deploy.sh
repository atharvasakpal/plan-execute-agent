#!/bin/bash

# AWS Deployment Script for Plan-Execute Agent
# Prerequisites: AWS CLI configured, Docker installed

set -e

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
ECR_REPOSITORY="plan-execute-agent"
ECS_CLUSTER="plan-execute-cluster"
ECS_SERVICE="plan-execute-service"
TASK_FAMILY="plan-execute-agent-task"

echo "🚀 Starting AWS deployment process..."

# Step 1: Build Docker image
echo "📦 Building Docker image..."
docker build -t ${ECR_REPOSITORY}:latest .

# Step 2: Authenticate with ECR
echo "🔐 Authenticating with ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Step 3: Tag and push image
echo "📤 Pushing image to ECR..."
docker tag ${ECR_REPOSITORY}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Step 4: Register new task definition
echo "📝 Registering new task definition..."
aws ecs register-task-definition \
    --cli-input-json file://deployment/ecs-task-definition.json \
    --region ${AWS_REGION}

# Step 5: Update ECS service
echo "🔄 Updating ECS service..."
aws ecs update-service \
    --cluster ${ECS_CLUSTER} \
    --service ${ECS_SERVICE} \
    --task-definition ${TASK_FAMILY} \
    --force-new-deployment \
    --region ${AWS_REGION}

echo "✅ Deployment complete!"
echo "🔍 Check service status:"
echo "aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${ECS_SERVICE} --region ${AWS_REGION}"
