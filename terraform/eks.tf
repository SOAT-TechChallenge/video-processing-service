# --- SECURITY GROUP DO CLUSTER ---
resource "aws_security_group" "eks_cluster" {
  name        = "${var.cluster_name}-sg"
  description = "Security group for EKS cluster"
  vpc_id      = data.aws_vpc.default.id

  # Comunicação interna do cluster
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  # Permite que o ALB acesse a porta NodePort
  ingress {
    description     = "Allow ALB to access NodePort"
    from_port       = local.node_port
    to_port         = local.node_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# --- CRIAÇÃO DO CLUSTER EKS ---
resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"

  vpc_config {
    subnet_ids              = local.selected_subnets
    endpoint_public_access  = true
    endpoint_private_access = true # Necessário true para comunicação interna
    security_group_ids      = [aws_security_group.eks_cluster.id]
  }

  tags = local.common_tags
}

# --- CRIAÇÃO DOS NODES ---
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.app_name}-ng"
  node_role_arn   = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"
  subnet_ids      = local.selected_subnets

  scaling_config {
    desired_size = 1
    max_size     = 2
    min_size     = 1
  }

  instance_types = ["t3.medium"]
  capacity_type  = "ON_DEMAND"

  tags = local.common_tags

  depends_on = [aws_eks_cluster.main]
}

# --- CONEXÃO ALB -> NODES ---
resource "aws_autoscaling_attachment" "eks_nodes_to_tg" {
  # Pega o ASG criado pelo Node Group novo
  autoscaling_group_name = aws_eks_node_group.main.resources[0].autoscaling_groups[0].name
  lb_target_group_arn    = aws_lb_target_group.app_tg.arn
  
  depends_on = [aws_eks_node_group.main, aws_lb_target_group.app_tg]
}