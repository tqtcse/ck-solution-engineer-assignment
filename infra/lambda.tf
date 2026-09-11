data "aws_iam_role" "lambda" {
  name = "${local.name}-lambda"
}

resource "aws_lambda_function" "app" {
  function_name = local.name
  role          = data.aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  memory_size   = var.memory_size
  timeout       = 60
  architectures = ["x86_64"]

  environment {
    variables = {
      AWS_LWA_INVOKE_MODE = "response_stream"
      PORT                = "8000"
      CHAT_MODEL          = var.chat_model
      EMBED_MODEL         = var.embed_model
      INDEX_VERSION       = var.index_version
      TOP_K               = "3"
      CONV_TABLE          = aws_dynamodb_table.conv.name
      HISTORY_TURNS       = "12"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_function_url" "app" {
  function_name      = aws_lambda_function.app.function_name
  authorization_type = "AWS_IAM"
  invoke_mode        = "RESPONSE_STREAM"
}
