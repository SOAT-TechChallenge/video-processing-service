terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# Data source para a VPC default
data "aws_vpc" "default" {
  default = true
}

# Listar todas as subnets da VPC default
data "aws_subnets" "all" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Data source para obter detalhes de cada subnet
data "aws_subnet" "details" {
  for_each = toset(data.aws_subnets.all.ids)
  id       = each.value
}

# Filtrar subnets para zonas suportadas pelo EKS
locals {
  # Zonas suportadas pelo EKS em us-east-1
  eks_supported_zones = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1f"]
  
  # Filtrar subnets que estão nas zonas suportadas
  filtered_subnets = [
    for subnet_id in data.aws_subnets.all.ids : 
    subnet_id 
    if contains(local.eks_supported_zones, data.aws_subnet.details[subnet_id].availability_zone)
  ]
  
  # Usar apenas as primeiras 2-3 subnets
  selected_subnets = slice(local.filtered_subnets, 0, min(3, length(local.filtered_subnets)))
  
  common_tags = {
    Project = var.app_name
  }
  
  cluster_name = var.cluster_name
}