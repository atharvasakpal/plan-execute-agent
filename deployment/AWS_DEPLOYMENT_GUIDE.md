# AWS Deployment Guide - Step by Step

## Prerequisites Checklist

- [ ] AWS Account created
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] Docker installed (`docker --version`)
- [ ] Google API key obtained

## Part 1: AWS Setup (One-time)

### 1. Create ECR Repository

```bash
aws ecr create-repository \
    --repository-name plan-execute-agent \
    --region us-east-1

# Note the repository URI from output
# Format: YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/plan-execute-agent
```

### 2. Store Secrets in AWS Secrets Manager

```bash
# Store Google API Key
aws secretsmanager create-secret \
    --name plan-execute/google-api-key \
    --description "Google API Key for Gemini" \
    --secret-string "YOUR_ACTUAL_GOOGLE_API_KEY" \
    --region us-east-1

# Note the ARN from output - you'll need it
```

### 3. Create VPC and Networking (if you don't have one)

```bash
# Create VPC
aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=plan-execute-vpc}]' \
    --region us-east-1

# Note the VPC ID from output

# Create subnets (at least 2 for ALB)
aws ec2 create-subnet \
    --vpc-id vpc-xxxxx \
    --cidr-block 10.0.1.0/24 \
    --availability-zone us-east-1a \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=plan-execute-subnet-1}]'

aws ec2 create-subnet \
    --vpc-id vpc-xxxxx \
    --cidr-block 10.0.2.0/24 \
    --availability-zone us-east-1b \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=plan-execute-subnet-2}]'

# Create Internet Gateway
aws ec2 create-internet-gateway \
    --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=plan-execute-igw}]'

# Attach IGW to VPC
aws ec2 attach-internet-gateway \
    --vpc-id vpc-xxxxx \
    --internet-gateway-id igw-xxxxx

# Create security group
aws ec2 create-security-group \
    --group-name plan-execute-sg \
    --description "Security group for Plan-Execute Agent" \
    --vpc-id vpc-xxxxx

# Add inbound rules
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxx \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0
```

### 4. Create IAM Roles

Create `trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# ECS Task Execution Role (pulls images, gets secrets)
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://deployment/trust-policy.json

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Secrets Manager permissions
aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

# ECS Task Role (app permissions)
aws iam create-role \
    --role-name ecsTaskRole \
    --assume-role-policy-document file://deployment/trust-policy.json
```

### 5. Create ECS Cluster

```bash
aws ecs create-cluster \
    --cluster-name plan-execute-cluster \
    --region us-east-1

# Enable CloudWatch Container Insights (optional but recommended)
aws ecs update-cluster-settings \
    --cluster plan-execute-cluster \
    --settings name=containerInsights,value=enabled \
    --region us-east-1
```

### 6. Create CloudWatch Log Group

```bash
aws logs create-log-group \
    --log-group-name /ecs/plan-execute-agent \
    --region us-east-1
```

## Part 2: Update Configuration Files

### 1. Update `deployment/ecs-task-definition.json`

Replace these placeholders:
- `YOUR_ACCOUNT_ID` → Your AWS account ID (12 digits)
- Update the secret ARN with your actual secret ARN from step 2
- Update the image URL with your ECR repository URI

### 2. Update `deployment/deploy.sh`

```bash
# Set your AWS account ID
AWS_ACCOUNT_ID="123456789012"  # Replace with your actual account ID

# Verify region matches your setup
AWS_REGION="us-east-1"
```

## Part 3: First Deployment

### 1. Build and Push Docker Image

```bash
# Make deploy script executable
chmod +x deployment/deploy.sh

# Get your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Authenticate Docker with ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t plan-execute-agent:latest .

# Tag image for ECR
docker tag plan-execute-agent:latest \
    ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/plan-execute-agent:latest

# Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/plan-execute-agent:latest
```

### 2. Register Task Definition

```bash
aws ecs register-task-definition \
    --cli-input-json file://deployment/ecs-task-definition.json \
    --region us-east-1
```

### 3. Create ECS Service

```bash
aws ecs create-service \
    --cluster plan-execute-cluster \
    --service-name plan-execute-service \
    --task-definition plan-execute-agent-task \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx,subnet-yyyyy],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
    --region us-east-1
```

Replace:
- `subnet-xxxxx,subnet-yyyyy` → Your subnet IDs
- `sg-xxxxx` → Your security group ID

### 4. Get Public IP

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
    --cluster plan-execute-cluster \
    --service-name plan-execute-service \
    --query 'taskArns[0]' \
    --output text)

# Get ENI ID
ENI_ID=$(aws ecs describe-tasks \
    --cluster plan-execute-cluster \
    --tasks $TASK_ARN \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
    --output text)

# Get public IP
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
    --network-interface-ids $ENI_ID \
    --query 'NetworkInterfaces[0].Association.PublicIp' \
    --output text)

echo "API available at: http://${PUBLIC_IP}:8000"
```

## Part 4: Testing Your Deployment

```bash
# Replace with your actual public IP
API_URL="http://YOUR_PUBLIC_IP:8000"

# Health check
curl $API_URL/health

# Execute a task
curl -X POST $API_URL/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Calculate 2+2"}'
```

## Part 5: Setting Up Application Load Balancer (Production)

### 1. Create Target Group

```bash
aws elbv2 create-target-group \
    --name plan-execute-targets \
    --protocol HTTP \
    --port 8000 \
    --vpc-id vpc-xxxxx \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --region us-east-1
```

### 2. Create Application Load Balancer

```bash
aws elbv2 create-load-balancer \
    --name plan-execute-alb \
    --subnets subnet-xxxxx subnet-yyyyy \
    --security-groups sg-xxxxx \
    --region us-east-1
```

### 3. Create Listener

```bash
aws elbv2 create-listener \
    --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:xxxxx:loadbalancer/app/plan-execute-alb/xxxxx \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:xxxxx:targetgroup/plan-execute-targets/xxxxx
```

### 4. Update ECS Service with ALB

```bash
aws ecs update-service \
    --cluster plan-execute-cluster \
    --service plan-execute-service \
    --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:xxxxx:targetgroup/plan-execute-targets/xxxxx,containerName=plan-execute-agent,containerPort=8000 \
    --region us-east-1
```

## Part 6: Monitoring and Logs

### View Logs

```bash
# Stream logs
aws logs tail /ecs/plan-execute-agent --follow

# View specific time range
aws logs filter-log-events \
    --log-group-name /ecs/plan-execute-agent \
    --start-time $(date -d '1 hour ago' +%s)000
```

### Check Service Status

```bash
aws ecs describe-services \
    --cluster plan-execute-cluster \
    --services plan-execute-service \
    --region us-east-1
```

### Check Task Status

```bash
aws ecs list-tasks \
    --cluster plan-execute-cluster \
    --service-name plan-execute-service

aws ecs describe-tasks \
    --cluster plan-execute-cluster \
    --tasks TASK_ARN
```

## Part 7: Future Updates

When you make changes to your code:

```bash
# Option 1: Use the deploy script
./deployment/deploy.sh

# Option 2: Manual deployment
docker build -t plan-execute-agent:latest .
docker tag plan-execute-agent:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/plan-execute-agent:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/plan-execute-agent:latest

aws ecs update-service \
    --cluster plan-execute-cluster \
    --service plan-execute-service \
    --force-new-deployment \
    --region us-east-1
```

## Cost Estimation

### Free Tier (First 12 months)
- ECS Fargate: Free tier not available
- Actual cost: ~$15-30/month for minimal usage

### After Free Tier
- Fargate (0.5 vCPU, 1GB): ~$0.05/hour = ~$36/month (if running 24/7)
- Data transfer: ~$1-5/month
- CloudWatch Logs: ~$0.50-2/month

**Total: ~$40-50/month**

### Cost Optimization Tips
1. Use spot instances (save 70%)
2. Stop tasks when not in use
3. Use reserved capacity (save 20-40%)
4. Implement auto-scaling based on usage

## Troubleshooting

### Task Not Starting
```bash
# Check task stopped reason
aws ecs describe-tasks \
    --cluster plan-execute-cluster \
    --tasks TASK_ARN \
    --query 'tasks[0].stoppedReason'
```

### Can't Pull Image
- Check ECR permissions in IAM role
- Verify image exists: `aws ecr list-images --repository-name plan-execute-agent`

### Task Keeps Failing
- Check CloudWatch logs
- Verify environment variables
- Check secret access permissions

### Can't Access API
- Check security group allows port 8000
- Verify task has public IP
- Check network configuration

## Next Steps

1. Set up domain name (Route 53)
2. Add HTTPS (ACM certificate)
3. Implement API authentication
4. Set up CI/CD pipeline (GitHub Actions)
5. Add monitoring and alerts (CloudWatch Alarms)
6. Implement auto-scaling
7. Add database for async task tracking

## Support

If you encounter issues:
1. Check CloudWatch logs first
2. Verify all ARNs and IDs are correct
3. Ensure IAM permissions are properly set
4. Check AWS service quotas
