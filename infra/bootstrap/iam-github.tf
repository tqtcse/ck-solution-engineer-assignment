resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "gha_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_sub_prefix}:ref:refs/heads/main"]
    }
  }
}

data "aws_iam_policy_document" "gha" {
  statement {
    sid       = "EcrPush"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrRepo"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart",
      "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeRepositories", "ecr:DescribeImages", "ecr:ListImages",
      "ecr:CreateRepository", "ecr:TagResource", "ecr:UntagResource",
      "ecr:ListTagsForResource", "ecr:GetLifecyclePolicy",
      "ecr:PutLifecyclePolicy", "ecr:DeleteLifecyclePolicy",
      "ecr:GetRepositoryPolicy", "ecr:SetRepositoryPolicy",
      "ecr:PutImageScanningConfiguration", "ecr:PutImageTagMutability",
    ]
    resources = ["arn:aws:ecr:${var.region}:${local.account}:repository/${local.name}"]
  }
  statement {
    sid       = "TfState"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.tfstate.arn, "${aws_s3_bucket.tfstate.arn}/*"]
  }
  statement {
    sid = "AppResources"
    actions = [
      "lambda:*", "dynamodb:CreateTable", "dynamodb:DescribeTable",
      "dynamodb:UpdateTable", "dynamodb:UpdateTimeToLive",
      "dynamodb:DescribeTimeToLive", "dynamodb:DescribeContinuousBackups",
      "dynamodb:UpdateContinuousBackups", "dynamodb:TagResource",
      "dynamodb:ListTagsOfResource",
      "logs:CreateLogGroup", "logs:DescribeLogGroups", "logs:PutRetentionPolicy",
      "logs:TagResource", "logs:ListTagsForResource", "logs:DeleteLogGroup",
      "logs:PutMetricFilter", "logs:DescribeMetricFilters", "logs:DeleteMetricFilter",
      "cloudwatch:PutMetricAlarm", "cloudwatch:DescribeAlarms",
      "cloudwatch:DeleteAlarms", "cloudwatch:ListTagsForResource",
      "cloudwatch:TagResource", "cloudwatch:UntagResource",
      "cloudfront:GetDistribution", "cloudfront:GetDistributionConfig",
      "cloudfront:UpdateDistribution", "cloudfront:CreateDistribution",
      "cloudfront:ListTagsForResource", "cloudfront:TagResource",
      "cloudfront:GetOriginAccessControl", "cloudfront:CreateOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl", "cloudfront:GetCachePolicy",
      "cloudfront:ListCachePolicies", "cloudfront:GetOriginRequestPolicy",
      "cloudfront:ListOriginRequestPolicies", "cloudfront:CreateInvalidation",
    ]
    resources = ["*"]
  }
  statement {
    sid       = "PassLambdaRole"
    actions   = ["iam:PassRole", "iam:GetRole"]
    resources = [aws_iam_role.lambda.arn]
  }
}

resource "aws_iam_role" "gha" {
  name               = "${local.name}-gha"
  assume_role_policy = data.aws_iam_policy_document.gha_trust.json
}

resource "aws_iam_role_policy" "gha" {
  name   = "deploy"
  role   = aws_iam_role.gha.id
  policy = data.aws_iam_policy_document.gha.json
}
