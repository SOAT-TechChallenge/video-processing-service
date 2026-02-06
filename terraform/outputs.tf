output "ecr_repo_url" { value = aws_ecr_repository.video_processing.repository_url }
output "api_url"      { value = "http://${aws_lb.processing_alb.dns_name}" }