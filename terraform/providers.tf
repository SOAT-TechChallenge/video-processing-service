terraform {
  required_version = ">= 1.0"

  backend "s3" {
    bucket = "challenge-hackathon"
    key    = "video-processing/ecs-terraform.tfstate"
    region = "us-east-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}