
output "raw_bucket_name" {
    description = "Name of the S3 raw landing zone bucket"
    value      = aws_s3_bucket.raw_data.id
}

output "raw_bucket_arn" {
    description = "ARN of the s3 raw landing zone bucket"
    value       = aws_s3_bucket.raw_data.arn
}

output "lambda_role_arn" {
    description = "ARN of the IAM role Lambda functions will assume"
    value       = aws_iam_role.lambda_exec.arn
}

output "account_id" {
    description = "AWS account ID in use"
    value       = data.aws_caller_identity.current.account_id
}

output "sec_edgar_ingest_arn" {
    value = aws_lambda_function.sec_edgar_ingest.arn
}

output "alpha_vantage_ingest_arn" {
    value = aws_lambda_function.alpha_vantage_ingest.arn
}