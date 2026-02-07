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

variable "aws_access_key_id" {
  description = "Access Key"
  sensitive = true
}

variable "aws_secret_access_key" {
  description = "Secret Key"
  sensitive = true
}

variable "aws_session_token" {
  description = "Session Token"
  sensitive = true
}