output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "selected_subnets" {
  value = local.selected_subnets
}

output "instructions" {
  value = <<-EOT

  ✅ CLUSTER EKS CRIADO!

  Para configurar:
  aws eks update-kubeconfig --name ${aws_eks_cluster.main.name} --region ${var.aws_region}

  Para verificar:
  kubectl get nodes
  kubectl get pods -n ${var.app_name}
  kubectl get svc -n ${var.app_name}

  URL da aplicação estará disponível no LoadBalancer.

  EOT
}

output "load_balancer_url" {
  value = "http://${kubernetes_service.app.status.0.load_balancer.0.ingress.0.hostname}"
  depends_on = [kubernetes_service.app]
}