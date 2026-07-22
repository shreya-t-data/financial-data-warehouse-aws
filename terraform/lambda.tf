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


# ---------- Alpha Vantage Lambda ----------

data "archive_file" "alpha_vantage_ingest" {
  type        = "zip"
  source_file = "${path.module}/../src/lambdas/alpha_vantage_ingest/handler.py"
  output_path = "${path.module}/build/alpha_vantage_ingest.zip"
}

resource "aws_cloudwatch_log_group" "alpha_vantage_ingest" {
  name              = "/aws/lambda/alpha_vantage_ingest"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_lambda_function" "alpha_vantage_ingest" {
  function_name    = "alpha_vantage_ingest"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.alpha_vantage_ingest.output_path
  source_code_hash = data.archive_file.alpha_vantage_ingest.output_base64sha256

  environment {
    variables = {
      S3_BUCKET             = aws_s3_bucket.raw_data.id
      TICKERS                = join(",", var.tickers)
      ALPHA_VANTAGE_API_KEY  = var.alpha_vantage_api_key
    }
  }

  depends_on = [aws_cloudwatch_log_group.alpha_vantage_ingest]
  tags       = local.common_tags
}
