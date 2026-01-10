# EKS Cluster usando role existente (LabRole)
resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  vpc_config {
    subnet_ids              = local.selected_subnets
    endpoint_public_access  = true
    endpoint_private_access = false
  }

  tags = local.common_tags
}

# EKS Node Group
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "default-nodegroup"
  node_role_arn   = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"
  subnet_ids      = local.selected_subnets

  scaling_config {
    desired_size = 1
    max_size     = 1
    min_size     = 1
  }

  instance_types = ["t3.medium"]
  capacity_type  = "ON_DEMAND"

  tags = local.common_tags

  depends_on = [aws_eks_cluster.main]
}

# Data source para autenticação
data "aws_eks_cluster_auth" "cluster_auth" {
  name = aws_eks_cluster.main.name
}