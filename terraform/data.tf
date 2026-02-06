data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "all" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

# Busca a fila criada pelo Uploader pelo nome fixo
data "aws_sqs_queue" "video_queue" {
  name = "video-processing-queue"
}

data "aws_ssm_parameter" "video_bucket_name" {
  name = "/video-uploader/s3_bucket_name"
}

data "aws_ssm_parameter" "notification_alb_url" {
  name = "/notification/alb_dns_name"
}