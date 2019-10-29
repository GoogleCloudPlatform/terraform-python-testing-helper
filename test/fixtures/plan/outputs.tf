output "gcs_buckets" {
  description = "GCS bucket names."
  value       = module.gcs-buckets.names
}

output "service_accounts" {
  description = "Service account emails."
  value       = module.service-accounts.emails
}
