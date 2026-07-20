
variable "aws_region" {
    description = "AWS region for all resources"
    type        = string
    default     = "us-east-1"
}


variable "aws_profile" {
    description = "AWS CLI profile to use"
    type        = string
    default     = "financial-warehouse"
}


variable "project_name" {
    description = "Base name used for tagging and resource naming"
    type        = string
    default     = "financial-data-warehouse"
}


variable "notification_email" {
    description = "Email address for budget alert notifications"
    type        = string
}


variable "budget_limit" {
    description = "Monthly budget limit in USD"
    type        = string
    default     = "5"
}

variable "lambda_role_name" {
    description = "Name of the IAM role Lambda functions will assume"
    type        = string
    default     = "financial-data-warehouse-lambda-role"
}

variable "s3_lifecycle_expiration_days" {
    description = "Days vefore raw landing zone objects expire"
    type        = number
    default     = "45"
}

variable "tickers" {
    description = "AI/tech ticker basket to track"
    type        = list(string)
    default     = ["NVDA", "MSFT", "GOOGL", "META", "AMD", "AVGO", "PLTR", "TSLA"]
}