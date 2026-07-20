
terraform {
    required_version = ">= 1.08"
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }
        archive = {
            source = "hashicorp/archive"
            version = "~> 2.4"
        }
    }
}

provider "aws" {
    region = var.aws_region
    profile = var.aws_profile
}

data "aws_caller_identity" "current" {}

locals {
    common_tags = {
        Project = var.project_name
        ManagedBy = "terraform"
    }
    # Bucket names are globally unique across all AWS accounts, so we suffix
    # with the account ID to guarantee that without hardcoding a random string.
    bucket_name = "${var.project_name}-raw-${data.aws_caller_identity.current.account_id}"
}


# --------------- S3 raw landing zone --------------------

resource "aws_s3_bucket" "raw_data" {
    bucket = local.bucket_name
    tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "raw_data" {
    bucket = aws_s3_bucket.raw_data.id
    versioning_configuration {
        status = "Enabled"
    }
}

resource "aws_s3_bucket_public_access_block" "raw_data" {
    bucket                  = aws_s3_bucket.raw_data.id
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true 
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
    bucket = aws_s3_bucket.raw_data.id

    rule {
        id  = "expire-raw-after-${var.s3_lifecycle_expiration_days}-days"
        status = "Enabled"

        filter {} # applies to every object in the bucket

        expiration {
            days = var.s3_lifecycle_expiration_days
        }
    }
}


# ------------------ IAM role for Lambda -----------------------

resource "aws_iam_role" "lambda_exec" {
    name = var.lambda_role_name
    tags = local.common_tags

    assume_role_policy = jsonencode({
        "Version" : "2012-10-17",
        "Statement" : [
            {
                "Effect" : "Allow",
                "Principal" : {"Service" : "lambda.amazonaws.com"},
                "Action" : "sts:AssumeRole"
            }
        ]
    })
}


resource "aws_iam_role_policy" "lambda_exec_permissions" {
    name = "${var.lambda_role_name}-permissions"
    role = aws_iam_role.lambda_exec.id

    policy = jsonencode({
        "Version" : "2012-10-17",
        "Statement" : [
            {
               Sid = "WriteToLandingBucket"
               Effect = "Allow"
               Action = ["s3:PutObject"]
               Resource = "${aws_s3_bucket.raw_data.arn}/*"
            },
            {
                Sid = "WriteLogs"
                Effect = "Allow"
                Action = [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ]
                Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.id}:log-group:/aws/lambda/*"
            }
        ]
    })
}


# ----------------------------- Budget alert -----------------------

resource "aws_budgets_budget" "monthly_cost" {
    name = "${var.project_name}-monthly-budget"
    account_id = data.aws_caller_identity.current.account_id
    budget_type = "COST"
    limit_amount = var.budget_limit
    limit_unit = "USD"
    time_unit = "MONTHLY"

    notification {
        comparison_operator = "GREATER_THAN" 
        threshold = 80
        threshold_type = "PERCENTAGE"
        notification_type = "ACTUAL"
        subscriber_email_addresses = [var.notification_email]
    }

    notification {
        comparison_operator = "GREATER_THAN" 
        threshold = 100
        threshold_type = "PERCENTAGE"
        notification_type = "ACTUAL"
        subscriber_email_addresses = [var.notification_email]
    }
}