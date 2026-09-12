variable "project" { default = "ck-agent" }
variable "env" { default = "dev" }
variable "region" { default = "us-east-1" }
variable "github_sub_prefix" {
  description = "Giá trị sub_claim_prefix của repo, lấy từ GET /repos/{owner}/{repo}/actions/oidc/customization/sub. Khi repo bật immutable subject claims, prefix này mang id số của owner và repo thay vì tên."
  default     = "repo:tqtcse@151527649/ck-solution-engineer-assignment@1363563923"
}

variable "github_repo" {
  description = "owner/repo — dùng trong điều kiện sub của OIDC"
  default     = "tqtcse/ck-solution-engineer-assignment"
}
