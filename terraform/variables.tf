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

variable "docker_image" {
  description = "Imagem Docker"
  default     = "breno091073/video-processing-service"
}

variable "docker_image_tag" {
  description = "Tag da imagem"
  default     = "latest"
}