# Plan-Execute Agent API

Production-ready FastAPI deployment of a multi-step reasoning AI agent using LangGraph and Google Gemini.

## 🏗️ Architecture

```
User Request → FastAPI → Plan-Execute Agent → LangGraph
                                ↓
                         Tools (Search, Wikipedia, Arxiv, Calculator)
                                ↓
                         Multi-step execution
                                ↓
                         Structured Response
```

## 📋 Features

- ✅ **FastAPI REST API** with async support
- ✅ **Multi-step reasoning** with LangGraph
- ✅ **Tool orchestration** (Search, Wikipedia, Arxiv, Calculator)
- ✅ **Production-ready** with error handling and logging
- ✅ **Docker containerization**
- ✅ **AWS ECS/Fargate deployment ready**
- ✅ **Health checks** and monitoring
- ✅ **CORS support**
- ✅ **Environment-based configuration**

## 🚀 Quick Start

### Local Development

1. **Clone and setup**
```bash
cd plan-execute-api
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run locally**
```bash
uvicorn app.main:app --reload
```

4. **Test the API**
```bash
# Health check
curl http://localhost:8000/health

# Execute a task
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Calculate the compound interest on $10,000 at 5% for 3 years"}'
```

5. **Access API docs**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Docker Development

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -t plan-execute-agent .
docker run -p 8000:8000 -e GOOGLE_API_KEY=your_key plan-execute-agent
```

## ☁️ AWS Deployment Guide

### Prerequisites

1. AWS CLI installed and configured
2. Docker installed
3. AWS account with appropriate permissions

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
    --repository-name plan-execute-agent \
    --region us-east-1
```

### Step 2: Store API Key in Secrets Manager

```bash
aws secretsmanager create-secret \
    --name plan-execute/google-api-key \
    --secret-string "your_actual_google_api_key" \
    --region us-east-1
```

### Step 3: Create ECS Cluster

```bash
aws ecs create-cluster \
    --cluster-name plan-execute-cluster \
    --region us-east-1
```

### Step 4: Create IAM Roles

**ECS Task Execution Role** (for pulling images and secrets):
```bash
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://deployment/trust-policy.json

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

**ECS Task Role** (for application permissions):
```bash
aws iam create-role \
    --role-name ecsTaskRole \
    --assume-role-policy-document file://deployment/trust-policy.json
```

### Step 5: Update Configuration

Edit `deployment/ecs-task-definition.json`:
- Replace `YOUR_ACCOUNT_ID` with your AWS account ID
- Update secret ARN with your region

Edit `deployment/deploy.sh`:
- Set `AWS_ACCOUNT_ID`
- Adjust region if needed

### Step 6: Deploy

```bash
# Make script executable
chmod +x deployment/deploy.sh

# Run deployment
./deployment/deploy.sh
```

### Step 7: Create Load Balancer (Optional)

For production, create an Application Load Balancer:

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name plan-execute-alb \
    --subnets subnet-xxxxx subnet-yyyyy \
    --security-groups sg-xxxxx

# Create target group
aws elbv2 create-target-group \
    --name plan-execute-targets \
    --protocol HTTP \
    --port 8000 \
    --vpc-id vpc-xxxxx \
    --health-check-path /health
```

### Step 8: Create ECS Service

```bash
aws ecs create-service \
    --cluster plan-execute-cluster \
    --service-name plan-execute-service \
    --task-definition plan-execute-agent-task \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}"
```

## 📊 Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /ecs/plan-execute-agent --follow
```

### Metrics

- CPU utilization
- Memory utilization
- Request count
- Error rate

## 🧪 Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=app tests/
```

## 📝 API Endpoints

### `GET /health`
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production"
}
```

### `POST /api/v1/execute`
Execute a task synchronously

**Request:**
```json
{
  "task": "Write a strategic one-pager for building an AI startup",
  "user_id": "optional_user_123"
}
```

**Response:**
```json
{
  "task_id": "uuid-here",
  "status": "completed",
  "result": "Strategic one-pager content...",
  "plan_steps": [
    "Step 1: Research AI startup landscape",
    "Step 2: Identify key value propositions",
    "Step 3: Draft executive summary"
  ]
}
```

### `POST /api/v1/execute-async`
Execute a task asynchronously (returns immediately)

**Response:**
```json
{
  "task_id": "uuid-here",
  "status": "processing"
}
```

## 🔧 Configuration

Environment variables (`.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google AI API key | Required |
| `ENVIRONMENT` | Environment name | `development` |
| `MODEL_NAME` | Gemini model to use | `gemini-2.5-flash` |
| `MODEL_TEMPERATURE` | Model temperature | `1.0` |
| `MAX_RETRIES` | Max retry attempts | `3` |
| `TIMEOUT_SECONDS` | Request timeout | `300` |
| `ALLOWED_ORIGINS` | CORS origins | `*` |

## 🐛 Troubleshooting

### Common Issues

**1. Import errors**
```bash
pip install -r requirements.txt --upgrade
```

**2. Docker build fails**
```bash
# Clear Docker cache
docker system prune -a
```

**3. AWS deployment fails**
- Check IAM permissions
- Verify secrets manager ARN
- Check VPC/subnet configuration

## 📚 Tech Stack

- **FastAPI** - Modern async web framework
- **LangChain** - LLM orchestration
- **LangGraph** - Stateful agent workflows
- **Google Gemini** - LLM provider
- **Docker** - Containerization
- **AWS ECS/Fargate** - Container orchestration
- **AWS Secrets Manager** - Secret management
- **CloudWatch** - Logging and monitoring

## 🎯 Production Considerations

- [ ] Add authentication (API keys, JWT)
- [ ] Implement rate limiting
- [ ] Add caching (Redis)
- [ ] Set up CI/CD pipeline
- [ ] Configure auto-scaling
- [ ] Add database for async task tracking
- [ ] Implement comprehensive monitoring
- [ ] Set up alerts and notifications

## 📄 License

MIT

## 👤 Author

Atharva Sakpal
- LinkedIn: [atharvasakpal](https://linkedin.com/in/atharvasakpal)
- GitHub: [atharvasakpal](https://github.com/atharvasakpal)

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR.
# plan-execute-agent
