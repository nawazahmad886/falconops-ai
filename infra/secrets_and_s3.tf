############################################################
# Secrets Manager — stores runtime secrets for ECS tasks
# Set values via: aws secretsmanager put-secret-value
############################################################

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "${local.name_prefix}/jwt-secret"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "emergent_llm_key" {
  name                    = "${local.name_prefix}/emergent-llm-key"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "stripe_secret" {
  name                    = "${local.name_prefix}/stripe-secret"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "resend_api_key" {
  name                    = "${local.name_prefix}/resend-api-key"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "mongo_password" {
  name                    = "${local.name_prefix}/mongo-master-password"
  recovery_window_in_days = 0
  tags                    = local.tags
}

# Allow ECS task role to read all FalconOps secrets
resource "aws_iam_policy" "ecs_secrets_read" {
  name = "${local.name_prefix}-ecs-secrets-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      Resource = [
        aws_secretsmanager_secret.jwt_secret.arn,
        aws_secretsmanager_secret.emergent_llm_key.arn,
        aws_secretsmanager_secret.stripe_secret.arn,
        aws_secretsmanager_secret.resend_api_key.arn,
        aws_secretsmanager_secret.mongo_password.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_secrets" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_secrets_read.arn
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_secrets_read.arn
}


############################################################
# S3 bucket — persist generated reports / branding logos
# (replaces /tmp which is ephemeral on Fargate)
############################################################

resource "aws_s3_bucket" "reports" {
  bucket        = "${local.name_prefix}-reports-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
  tags          = local.tags
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id     = "expire-old-reports"
    status = "Enabled"
    filter { prefix = "reports/" }
    expiration { days = 365 }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

data "aws_caller_identity" "current" {}

# Allow ECS task to read/write reports bucket
resource "aws_iam_policy" "ecs_s3_reports" {
  name = "${local.name_prefix}-ecs-s3-reports"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.reports.arn, "${aws_s3_bucket.reports.arn}/*"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_s3_reports.arn
}


############################################################
# ACM certificate + HTTPS listener (uncomment after creating
# a domain in Route53 and updating var.domain_name)
############################################################

# resource "aws_acm_certificate" "main" {
#   domain_name               = var.domain_name
#   subject_alternative_names = ["*.${var.domain_name}"]
#   validation_method         = "DNS"
#   lifecycle { create_before_destroy = true }
#   tags = local.tags
# }
#
# resource "aws_lb_listener" "https" {
#   load_balancer_arn = aws_lb.main.arn
#   port              = 443
#   protocol          = "HTTPS"
#   ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
#   certificate_arn   = aws_acm_certificate.main.arn
#
#   default_action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.frontend.arn
#   }
# }
#
# resource "aws_lb_listener_rule" "api_https" {
#   listener_arn = aws_lb_listener.https.arn
#   priority     = 100
#   condition { path_pattern { values = ["/api/*"] } }
#   action {
#     type             = "forward"
#     target_group_arn = aws_lb_target_group.backend.arn
#   }
# }
#
# # Redirect HTTP -> HTTPS
# resource "aws_lb_listener" "http_redirect" {
#   load_balancer_arn = aws_lb.main.arn
#   port              = 80
#   protocol          = "HTTP"
#   default_action {
#     type = "redirect"
#     redirect {
#       port        = "443"
#       protocol    = "HTTPS"
#       status_code = "HTTP_301"
#     }
#   }
# }


############################################################
# Outputs
############################################################

output "s3_reports_bucket" { value = aws_s3_bucket.reports.id }
output "secrets_jwt_arn" { value = aws_secretsmanager_secret.jwt_secret.arn }
output "secrets_resend_arn" { value = aws_secretsmanager_secret.resend_api_key.arn }
output "secrets_emergent_arn" { value = aws_secretsmanager_secret.emergent_llm_key.arn }
output "secrets_stripe_arn" { value = aws_secretsmanager_secret.stripe_secret.arn }
