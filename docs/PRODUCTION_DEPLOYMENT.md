# VettedMe Production Deployment Guide

**Version**: 1.0.0  
**Target**: AWS, GCP, Azure, or any cloud provider  
**Scale**: 10M+ requests/day, 99.99% uptime

---

## 🚀 Quick Start (Docker Compose)

```bash
# 1. Clone repository
git clone https://github.com/vettedme/vettedme-backend.git
cd vettedme-backend

# 2. Set environment variables
cp .env.example .env
# Edit .env with your production values

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec api alembic upgrade head

# 5. Verify deployment
curl http://localhost:8000/health
```

**You're live!** VettedMe is now running on `http://localhost:8000`

---

## 🏗️ Production Architecture

```
                                    [CloudFlare CDN]
                                           |
                                    [Load Balancer]
                                    (ALB / NGINX)
                                           |
                        +------------------+------------------+
                        |                  |                  |
                   [API Server 1]    [API Server 2]    [API Server 3]
                   (FastAPI)         (FastAPI)         (FastAPI)
                        |                  |                  |
                        +------------------+------------------+
                                           |
                        +------------------+------------------+
                        |                  |                  |
                   [PostgreSQL]         [Redis]         [Celery Workers]
                   (Primary +           (Cache +        (Background Jobs)
                    Replicas)            Queues)
```

---

## 🔧 Environment Variables

### Required

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/vettedme

# Redis (caching + queues)
REDIS_URL=redis://:password@localhost:6379/0

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
VETTEDME_ISSUER_PRIVATE_KEY=<ed25519-private-key-pem>

# API Keys
OPENAI_API_KEY=sk-...
```

### Optional

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Blockchain
BLOCKCHAIN_ENABLED=true
VETTEDME_CONTRACT_POLYGON=0x...

# Biometrics
BIOMETRIC_LIVENESS_ENABLED=true
BIOMETRIC_FACE_ENABLED=true
FACETEC_API_KEY=...
AWS_REKOGNITION_KEY=...

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
DATADOG_API_KEY=...
```

---

## 📦 AWS Deployment (Recommended)

### Architecture

- **Compute**: ECS Fargate (serverless containers)
- **Database**: RDS PostgreSQL (Multi-AZ)
- **Cache**: ElastiCache Redis (cluster mode)
- **Load Balancer**: Application Load Balancer (ALB)
- **CDN**: CloudFront
- **Storage**: S3 (documents, backups)
- **Monitoring**: CloudWatch + X-Ray

### Step-by-Step

#### 1. Create RDS PostgreSQL

```bash
aws rds create-db-instance \
  --db-instance-identifier vettedme-prod \
  --db-instance-class db.r6g.xlarge \
  --engine postgres \
  --engine-version 15.3 \
  --master-username vettedme \
  --master-user-password <STRONG_PASSWORD> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --multi-az \
  --backup-retention-period 30 \
  --enable-performance-insights
```

#### 2. Create ElastiCache Redis

```bash
aws elasticache create-replication-group \
  --replication-group-id vettedme-prod \
  --replication-group-description "VettedMe Production Cache" \
  --engine redis \
  --cache-node-type cache.r6g.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled
```

#### 3. Build & Push Docker Image

```bash
# Build
docker build -t vettedme-api:latest .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker tag vettedme-api:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/vettedme-api:latest

# Push
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/vettedme-api:latest
```

#### 4. Create ECS Cluster & Service

```bash
# Create cluster
aws ecs create-cluster --cluster-name vettedme-prod

# Create task definition (see ecs-task-definition.json)
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service with ALB
aws ecs create-service \
  --cluster vettedme-prod \
  --service-name vettedme-api \
  --task-definition vettedme-api:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --load-balancers targetGroupArn=<TG_ARN>,containerName=api,containerPort=8000
```

#### 5. Configure Auto-Scaling

```bash
# Target tracking (CPU-based)
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/vettedme-prod/vettedme-api \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 3 \
  --max-capacity 50

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/vettedme-prod/vettedme-api \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

---

## 🔐 Security Checklist

### SSL/TLS
- [ ] Valid SSL certificate (Let's Encrypt or AWS ACM)
- [ ] TLS 1.3 minimum
- [ ] HSTS headers enabled
- [ ] Certificate auto-renewal configured

### Database
- [ ] Strong password (32+ chars, random)
- [ ] Encryption at rest enabled
- [ ] Encryption in transit (SSL mode required)
- [ ] No public accessibility
- [ ] Automated backups (30 days retention)
- [ ] Point-in-time recovery enabled

### API Security
- [ ] Rate limiting enabled (per IP + per API key)
- [ ] CORS configured properly
- [ ] Security headers (CSP, X-Frame-Options, etc.)
- [ ] API keys stored as hashes (SHA256)
- [ ] Secrets in environment variables (never in code)

### Infrastructure
- [ ] VPC with private subnets
- [ ] Security groups (least privilege)
- [ ] IAM roles (no access keys)
- [ ] CloudTrail logging enabled
- [ ] GuardDuty threat detection enabled
- [ ] WAF rules configured

---

## 📊 Monitoring & Alerts

### Health Checks

```python
# Add to app/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": await check_db(),
        "redis": await check_redis(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

### CloudWatch Alarms

```bash
# High CPU
aws cloudwatch put-metric-alarm \
  --alarm-name vettedme-high-cpu \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High Error Rate
aws cloudwatch put-metric-alarm \
  --alarm-name vettedme-high-errors \
  --metric-name 5XXError \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Log Aggregation

```bash
# Ship logs to CloudWatch
aws logs create-log-group --log-group-name /ecs/vettedme-api

# Or use Datadog
docker run -d \
  --name datadog-agent \
  -e DD_API_KEY=<YOUR_KEY> \
  -e DD_LOGS_ENABLED=true \
  -e DD_APM_ENABLED=true \
  datadog/agent:latest
```

---

## ⚡ Performance Optimization

### Redis Caching

```python
# Cache frequently accessed data
@cache(expire=300)  # 5 minutes
async def get_passport(passport_id: UUID):
    return db.query(Passport).filter_by(id=passport_id).first()
```

### Database Connection Pooling

```python
# In database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### CDN Configuration

```nginx
# nginx.conf
location /static/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /api/ {
    proxy_cache_valid 200 5m;
    proxy_cache_bypass $http_cache_control;
}
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run tests
        run: pytest
      
      - name: Build Docker image
        run: docker build -t vettedme-api:${{ github.sha }} .
      
      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com
          docker push <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/vettedme-api:${{ github.sha }}
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster vettedme-prod \
            --service vettedme-api \
            --force-new-deployment
```

---

## 💰 Cost Optimization

### AWS Costs (Estimated for 10M requests/day)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| ECS Fargate | 3 tasks (2 vCPU, 4GB) | $150 |
| RDS PostgreSQL | db.r6g.xlarge Multi-AZ | $400 |
| ElastiCache Redis | cache.r6g.large x2 | $300 |
| ALB | 10M requests/day | $30 |
| Data Transfer | 1TB/month | $90 |
| **Total** | | **~$970/month** |

### Optimization Tips

1. **Use Reserved Instances**: Save 30-50% on RDS/ElastiCache
2. **Enable Auto-Scaling**: Scale down during off-hours
3. **Compress Responses**: Reduce data transfer costs
4. **Cache Aggressively**: Reduce database queries

---

## 🚨 Disaster Recovery

### Backup Strategy

```bash
# Automated daily backups
aws rds modify-db-instance \
  --db-instance-identifier vettedme-prod \
  --backup-retention-period 30 \
  --preferred-backup-window "03:00-04:00"

# Manual snapshot before major changes
aws rds create-db-snapshot \
  --db-instance-identifier vettedme-prod \
  --db-snapshot-identifier vettedme-pre-deploy-$(date +%Y%m%d)
```

### Recovery Time Objective (RTO)

- **Database failure**: < 5 minutes (Multi-AZ automatic failover)
- **Application failure**: < 2 minutes (ECS auto-restart)
- **Region failure**: < 30 minutes (Cross-region replica promotion)

---

## 📈 Scaling Guidelines

| Daily Requests | ECS Tasks | RDS Instance | Redis Instance |
|----------------|-----------|--------------|----------------|
| 1M | 2-3 | db.t3.large | cache.t3.medium |
| 10M | 3-10 | db.r6g.xlarge | cache.r6g.large |
| 100M | 10-50 | db.r6g.4xlarge | cache.r6g.2xlarge |
| 1B | 50-200 | db.r6g.16xlarge | cache.r6g.8xlarge |

---

## ✅ Pre-Launch Checklist

### Week Before Launch
- [ ] Load testing (simulate 2x expected traffic)
- [ ] Disaster recovery drill
- [ ] Security scan (OWASP ZAP, Nessus)
- [ ] Penetration test
- [ ] Review all logs and metrics
- [ ] Prepare rollback plan

### Launch Day
- [ ] Enable enhanced monitoring
- [ ] Set up PagerDuty/Opsgenie
- [ ] Announce maintenance window
- [ ] Deploy to production
- [ ] Run smoke tests
- [ ] Monitor for 4 hours

### Week After Launch
- [ ] Review error rates
- [ ] Analyze performance metrics
- [ ] Collect user feedback
- [ ] Optimize based on real traffic
- [ ] Document lessons learned

---

**Questions?** Contact devops@vettedme.ai

**Ready to scale to billions of verifications?** You got this! 🚀
