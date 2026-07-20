# -------------------SEC EDGAR Lambda ------------------------


data "archive_file" "sec_edgar_ingest" {
  type        = "zip"
  source_file = "${path.module}/../src/lambdas/sec_edgar_ingest/handler.py"
  output_path = "${path.module}/build/sec_edgar_ingest.zip"
}

resource "aws_cloudwatch_log_group" "sec_edgar_ingest" {
  name              = "/aws/lambda/sec_edgar_ingest"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "sec_edgar_ingest" {
    function_name       = "sec_edgar_ingest"
    role                = aws_iam_role.lambda_exec.arn
    handler             = "handler.handler"
    runtime             = "python3.12"
    timeout             = 30
    memory_size         = 128
    filename            = data.archive_file.sec_edgar_ingest.output_path
    source_code_hash    = data.archive_file.sec_edgar_ingest.output_base64sha256


    environment {
    variables = {
      S3_BUCKET     = aws_s3_bucket.raw_data.id
      TICKERS       = join(",", var.tickers)
      CONTACT_EMAIL = var.notification_email
    }
  }

    depends_on = [aws_cloudwatch_log_group.sec_edgar_ingest]
    tags       = local.common_tags
}


# ----------------------- Stooq Lambda ------------------------

data "archive_file" "stooq_ingest" {
  type        = "zip"
  source_file = "${path.module}/../src/lambdas/stooq_ingest/handler.py"
  output_path = "${path.module}/build/stooq_ingest.zip"
}

resource "aws_cloudwatch_log_group" "stooq_ingest" {
  name              = "/aws/lambda/stooq_ingest"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "stooq_ingest" {
    function_name       = "stooq_ingest"
    role                = aws_iam_role.lambda_exec.arn
    handler             = "handler.handler"
    runtime             = "python3.12"
    timeout             = 30
    memory_size         = 128
    filename            = data.archive_file.stooq_ingest.output_path
    source_code_hash    = data.archive_file.stooq_ingest.output_base64sha256


    environment {
    variables = {
      S3_BUCKET     = aws_s3_bucket.raw_data.id
      TICKERS       = join(",", var.tickers)
    }
  }

    depends_on = [aws_cloudwatch_log_group.stooq_ingest]
    tags       = local.common_tags
}
