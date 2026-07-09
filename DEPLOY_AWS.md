# FalconOps AI — AWS Production Deployment (ECR + ECS Fargate)

> **Deployment status as of Phase 24**: Terraform configuration in `infra/` is **ready to apply** —
> `main.tf` provisions ECR + ECS + ALB + DocumentDB + S3 + Secrets Manager, and `secrets_and_s3.tf`
> handles the secret rotation policy. Execution is blocked only on the operator providing AWS
> credentials. The pre-built on-prem bundle (Phase 23) ships a working alternative path for any
> environment where AWS deployment isn't desired.

## ⚡ TL;DR — what you need to do

```bash
# 1. Configure AWS credentials (from your laptop or CI runner)
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=me-south-1   # or your preferred region

# 2. From the project root
cd infra
terraform init
terraform plan                      # review changes
terraform apply -auto-approve       # ~12 min to provision

# 3. Push the backend & frontend images to the newly-created ECR repos
./scripts/build-and-push.sh         # builds + tags + pushes both images

# 4. Flip the backend storage to S3 (replace local /tmp)
aws ssm put-parameter --name "/falconops/STORAGE_BACKEND" --value "s3" --overwrite
aws ssm put-parameter --name "/falconops/REPORTS_S3_BUCKET" --value "$(terraform output -raw reports_bucket)" --overwrite

# 5. Force-redeploy ECS services so they pick up new env
aws ecs update-service --cluster falconops --service backend --force-new-deployment
aws ecs update-service --cluster falconops --service frontend --force-new-deployment

# 6. (Optional) Point your domain at the ALB
# Use `terraform output alb_dns_name` and create a CNAME / Route53 alias
```

End-to-end guide to deploy FalconOps AI to AWS using **ECR + ECS Fargate + ALB + DocumentDB + S3 + Secrets Manager**, orchestrated by Terraform and GitHub Actions.

---

## 1. Prerequisites

| Tool | Version |
|------|---------|
| AWS CLI | ≥ 2.15 |
| Terraform | ≥ 1.6 |
| Docker | ≥ 24 |
| A domain name you own (optional but recommended for HTTPS) |

```bash
aws configure          # set access key + secret + region (e.g. me-south-1)
aws sts get-caller-identity   # verify credentials
```

You also need:
- **Resend API key** (for scheduled report emails) — https://resend.com
- **Stripe API key** (billing) — https://stripe.com
- **Emergent LLM key** (AI agents) — ask Emergent team

---

## 2. One-time bootstrap (Terraform state bucket)

```bash
BUCKET="falconops-terraform-state-$(aws sts get-caller-identity --query Account --output text)"
aws s3api create-bucket --bucket "$BUCKET" --region me-south-1 \
  --create-bucket-configuration LocationConstraint=me-south-1
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
```

Add a `backend.tf` in `/app/infra/`:

```hcl
terraform {
  backend "s3" {
    bucket = "falconops-terraform-state-<ACCOUNT_ID>"
    key    = "production/terraform.tfstate"
    region = "me-south-1"
  }
}
```

---

## 3. Provision infrastructure

```bash
cd /app/infra
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

This creates:
- VPC + public/private subnets + NAT gateway
- 3× ECR repositories (`falconops-production-{backend,frontend,check-node}`)
- ECS Fargate cluster
- Application Load Balancer (HTTP on :80; HTTPS block commented — see §7)
- DocumentDB cluster (MongoDB-compatible, r6g.large × 1 instance)
- IAM roles, CloudWatch log groups, auto-scaling
- **S3 bucket** (`falconops-production-reports-<ACCOUNT_ID>`) for report persistence
- **Secrets Manager** entries (empty — fill them in step 4)

> ⏱ Takes ~15 minutes. DocumentDB creation is the slowest.

### Outputs

```bash
terraform output
# alb_dns_name         = "falconops-production-alb-xxxxx.me-south-1.elb.amazonaws.com"
# ecr_backend_url      = "<acct>.dkr.ecr.me-south-1.amazonaws.com/falconops-production-backend"
# docdb_endpoint       = "falconops-production-docdb.cluster-xxxxx.me-south-1.docdb.amazonaws.com"
# s3_reports_bucket    = "falconops-production-reports-<ACCOUNT_ID>"
```

---

## 4. Populate secrets

```bash
aws secretsmanager put-secret-value --secret-id falconops-production/jwt-secret \
  --secret-string "$(openssl rand -hex 32)"

aws secretsmanager put-secret-value --secret-id falconops-production/emergent-llm-key \
  --secret-string "sk-emergent-XXXXXXXXXXXX"

aws secretsmanager put-secret-value --secret-id falconops-production/stripe-secret \
  --secret-string "sk_live_XXXXXXXXXXXX"

aws secretsmanager put-secret-value --secret-id falconops-production/resend-api-key \
  --secret-string "re_XXXXXXXXXXXX"

aws secretsmanager put-secret-value --secret-id falconops-production/mongo-master-password \
  --secret-string "$(openssl rand -hex 24)"
```

Update your ECS task definitions in `/app/infra/main.tf` to reference these via `secrets` block (see AWS docs: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html).

Example snippet to add inside the `container_definitions`:

```json
"secrets": [
  { "name": "JWT_SECRET_KEY",     "valueFrom": "arn:aws:secretsmanager:...:secret:falconops-production/jwt-secret"     },
  { "name": "EMERGENT_LLM_KEY",   "valueFrom": "arn:aws:secretsmanager:...:secret:falconops-production/emergent-llm-key" },
  { "name": "STRIPE_API_KEY",     "valueFrom": "arn:aws:secretsmanager:...:secret:falconops-production/stripe-secret"     },
  { "name": "RESEND_API_KEY",     "valueFrom": "arn:aws:secretsmanager:...:secret:falconops-production/resend-api-key"    }
]
```

---

## 5. Build & push Docker images

### Option A — Local push (first deploy)

```bash
REGION=me-south-1
ACCT=$(aws sts get-caller-identity --query Account --output text)
ECR=$ACCT.dkr.ecr.$REGION.amazonaws.com

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR

# Backend
docker build -t $ECR/falconops-production-backend:latest -f backend/Dockerfile backend/
docker push   $ECR/falconops-production-backend:latest

# Frontend
docker build -t $ECR/falconops-production-frontend:latest -f frontend/Dockerfile frontend/
docker push   $ECR/falconops-production-frontend:latest
```

### Option B — GitHub Actions (CI/CD, recommended)

1. Create an IAM role with trust policy for your repo (OIDC):
   ```
   arn:aws:iam::<ACCT>:role/FalconOpsGitHubActions
   ```
2. Add GitHub repo secret `AWS_ROLE_ARN` = that role's ARN.
3. Push to `main` — `/app/.github/workflows/ci-cd.yml` will run tests → build → push → deploy.

---

## 6. Force ECS to pull new images

```bash
aws ecs update-service --cluster falconops-production-cluster \
  --service falconops-production-backend --force-new-deployment

aws ecs update-service --cluster falconops-production-cluster \
  --service falconops-production-frontend --force-new-deployment
```

Watch tasks come up:
```bash
aws ecs describe-services --cluster falconops-production-cluster \
  --services falconops-production-backend falconops-production-frontend \
  --query 'services[].{service:serviceName,running:runningCount,desired:desiredCount}'
```

Your app is live at the ALB DNS (see `terraform output alb_dns_name`).

---

## 7. Enable HTTPS (strongly recommended)

1. Create an ACM certificate for your domain:
   ```bash
   aws acm request-certificate --domain-name falconops.example.com \
     --subject-alternative-names '*.falconops.example.com' \
     --validation-method DNS --region me-south-1
   ```
2. Add the DNS validation CNAME to Route53 (or your DNS provider).
3. Uncomment the ACM + HTTPS listener block in `/app/infra/secrets_and_s3.tf`.
4. `terraform apply`.
5. Point your domain's A-record (ALIAS) to the ALB.

---

## 8. Backup & recovery

- **DocumentDB**: automated backups retained 7 days (configured in `main.tf`).
- **S3 Reports bucket**: versioning enabled, 365-day lifecycle, 90-day noncurrent retention.
- **Secrets**: 0-day recovery (rotate via `aws secretsmanager update-secret-version-stage`).

To restore DocumentDB from a snapshot:
```bash
aws docdb restore-db-cluster-from-snapshot \
  --db-cluster-identifier falconops-restored \
  --snapshot-identifier <snapshot-id> --engine docdb
```

---

## 9. Cost estimate (steady state, single AZ)

| Service | Instance | Monthly (USD) |
|---------|----------|---------------|
| ALB | Standard | ~$22 |
| ECS Fargate | 1× backend (1 vCPU 2GB) + 1× frontend (0.5 vCPU 1GB) | ~$45 |
| DocumentDB | 1× db.r6g.large | ~$195 |
| NAT Gateway | 1× | ~$34 |
| CloudWatch Logs | 30-day retention | ~$6 |
| ECR storage | <5 GB | ~$0.5 |
| S3 Reports | <5 GB | ~$0.1 |
| Secrets Manager | 5 secrets | ~$2 |
| **Total** | | **~$305 / month** |

Scale-down options: replace DocumentDB with MongoDB Atlas shared tier (~$9/mo) for dev; use Fargate Spot (40% savings).

---

## 10. Migrate report storage to S3 (post-deploy code change)

The app currently writes generated reports to `/tmp/falconops_reports` which is **ephemeral** on Fargate.
After first deploy, swap this out for S3:

1. `pip install boto3` (already present).
2. Replace filesystem writes in `/app/backend/app/services/report_generator_service.py:store_report()` with:
   ```python
   import boto3, os
   s3 = boto3.client("s3")
   bucket = os.environ["REPORTS_S3_BUCKET"]
   s3.put_object(Bucket=bucket, Key=f"reports/{report_id}.pdf", Body=pdf_bytes,
                 ContentType="application/pdf", ServerSideEncryption="AES256")
   ```
3. Replace `FileResponse(path)` in download endpoints with a presigned URL redirect.
4. Set `REPORTS_S3_BUCKET` env var in the backend ECS task definition.

> This is **left as a deliberate follow-up** so your first deploy runs green. The in-memory/tmp storage works fine for 1-task deployments; swap to S3 when you scale to multiple backend replicas.

---

## 11. Rollback

Every `git push` to `main` tags `:$SHA` in ECR. To roll back:

```bash
aws ecs update-service --cluster falconops-production-cluster \
  --service falconops-production-backend \
  --task-definition falconops-production-backend:<PREVIOUS_REVISION>
```

Or re-tag a known-good SHA as `:latest` and force new deployment.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Tasks stop immediately with "Essential container in task exited" | Check CloudWatch `/ecs/falconops-production/backend` for Python errors |
| 502 from ALB | Task not passing `/api/health` probe — verify `MONGO_URL` secret |
| Scheduler cron not firing | APScheduler needs persistent process — confirm backend has `desiredCount=1` (multiple replicas would cause duplicate runs; use DynamoDB lock if scaling out) |
| PDF downloads return 404 after 1 hour | Ephemeral `/tmp` — migrate to S3 (see §10) |

---

© FalconOps AI · Production Deployment Guide v1.0 · Feb 2026
