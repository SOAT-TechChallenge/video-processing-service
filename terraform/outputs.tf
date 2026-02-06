output "ecr_repo_url" {
  value = aws_ecr_repository.video_processing.repository_url
}
output "api_url" {
  value = "http://${aws_lb.processing_alb.dns_name}"
}
output "ssm_processing_alb_dns_path" {
  value = aws_ssm_parameter.processing_alb_dns.name
}
