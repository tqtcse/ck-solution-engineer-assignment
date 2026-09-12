variable "project" { default = "ck-agent" }
variable "env" { default = "dev" }
variable "region" { default = "us-east-1" }

variable "image_tag" {
  description = "tag image trong ECR — CI truyền commit sha vào"
  default     = "latest"
}

variable "chat_model" {
  default = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}
variable "embed_model" {
  default = "amazon.titan-embed-text-v2:0"
}
variable "index_version" { default = "v2" }
variable "memory_size" { default = 2048 }
variable "log_retention" { default = 7 }
