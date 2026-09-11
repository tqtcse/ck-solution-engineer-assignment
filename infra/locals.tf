data "aws_caller_identity" "me" {}

locals {
  name    = "${var.project}-${var.env}"
  account = data.aws_caller_identity.me.account_id
}
