# ------------------ IAM role EventBridge Scheduler assumes to invoke Lambda ------------------

resource "aws_iam_role" "scheduler_invoke" {
    name = "financial-data-warehouse-scheduler-role"
    tags = local.common_tags

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [ 
            {
                Effect = "Allow"
                Principal = { Service = "scheduler.amazonaws.com"}
                Action = "sts:AssumeRole"
            }
        ]
    })
}


resource "aws_iam_role_policy" "scheduler_invoke_permission" {
    name = "financial-data-warehouse-scheduler-role-permissions"
    role = aws_iam_role.scheduler_invoke.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Sid    = "InvokeIngestLambdas"
                Effect = "Allow"
                Action = ["lambda:InvokeFunction"]
                Resource = [
                    aws_lambda_function.sec_edgar_ingest.arn,
                    aws_lambda_function.stooq_ingest.arn
                ]
            }
        ]
    })
}


# ------------------- Daily schedules ------------------------------------

resource "aws_scheduler_schedule" "sec_edgar_daily" {
  name       = "sec-edgar-ingest-daily"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

    schedule_expression = "cron(0 22 * * ? *)"
    schedule_expression_timezone = "UTC"

    target {
        arn      = aws_lambda_function.sec_edgar_ingest.arn
        role_arn = aws_iam_role.scheduler_invoke.arn
    }
}

resource "aws_scheduler_schedule" "stooq_daily" {
  name       = "stooq-ingest-daily"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

    schedule_expression          = "cron(5 22 * * ? *)"
    schedule_expression_timezone = "UTC"

    target {
        arn      = aws_lambda_function.stooq_ingest.arn
        role_arn = aws_iam_role.scheduler_invoke.arn
    }
}
