variable "aws_region" {
  description = "Região AWS"
  default     = "us-east-1"
}

variable "app_name" {
  description = "Nome da aplicação"
  default     = "video-processor"
}

variable "cluster_name" {
  description = "Nome do cluster EKS"
  default     = "video-processor-cluster"
}

variable "container_port" {
  description = "Porta do container"
  default     = 8000
}

variable "aws_s3_bucket" {
  description = "Nome do bucket S3 compartilhado"
  default     = "challenge-hackathon"
}

variable "aws_sqs_queue_url" {
  description = "URL da fila SQS compartilhada"
  default     = "https://sqs.us-east-1.amazonaws.com/294277043425/challenge-hackathon"
}

variable "docker_image" {
  description = "Imagem Docker"
  default     = "leynerbueno/video-processing-service"
}

variable "docker_image_tag" {
  description = "Tag da imagem"
  default     = "latest"
}

variable "notification_service_url" {
  description = "DNS do Load Balancer do Notification Service"
  type        = string
}

variable "aws_access_key_id" {
  description = "Access Key"
}

variable "aws_secret_access_key" {
  description = "Secret Key"
}

variable "aws_session_token" {
  description = "Session Token"
}