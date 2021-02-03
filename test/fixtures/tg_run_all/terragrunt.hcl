generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "null" {}
EOF
}

terraform {
  source = "../apply"
}