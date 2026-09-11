output "tfstate_bucket" { value = aws_s3_bucket.tfstate.id }
output "lambda_role_arn" { value = aws_iam_role.lambda.arn }
output "gha_role_arn" { value = aws_iam_role.gha.arn }
