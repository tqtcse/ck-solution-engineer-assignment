variable "project" { default = "ck-agent" }
variable "env" { default = "dev" }
variable "region" { default = "us-east-1" }
variable "github_repo" {
  description = "owner/repo — dùng trong điều kiện sub của OIDC"
  default     = "tqtcse/ck-solution-engineer-assignment"
}
