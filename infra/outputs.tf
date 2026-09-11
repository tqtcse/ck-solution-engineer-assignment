output "app_url" { value = "https://${aws_cloudfront_distribution.app.domain_name}/" }
output "function_url" { value = aws_lambda_function_url.app.function_url }
output "image_uri" { value = "${aws_ecr_repository.app.repository_url}:${var.image_tag}" }
output "table_name" { value = aws_dynamodb_table.conv.name }
output "log_group" { value = aws_cloudwatch_log_group.lambda.name }
