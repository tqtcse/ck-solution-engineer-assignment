resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${local.name}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.app.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "slow" {
  alarm_name          = "${local.name}-p95-latency"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = aws_lambda_function.app.function_name }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 15000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_log_metric_filter" "throttle" {
  name           = "${local.name}-bedrock-throttle"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "ThrottlingException"

  metric_transformation {
    name          = "BedrockThrottles"
    namespace     = "CkAgent"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "throttle" {
  alarm_name          = "${local.name}-bedrock-throttle"
  namespace           = "CkAgent"
  metric_name         = "BedrockThrottles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
