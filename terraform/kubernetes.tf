# Configurar o provider Kubernetes
provider "kubernetes" {
  host                   = aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster_auth.token

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.main.name]
    command     = "aws"
  }
}

# Namespace para aplicação (COM DEPENDS_ON)
resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_name
  }

  depends_on = [aws_eks_node_group.main]  # IMPORTANTE: Esperar nodes estarem prontos
}

# ConfigMap para configurações
resource "kubernetes_config_map" "app_config" {
  metadata {
    name      = "${var.app_name}-config"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    UPLOAD_DIR = "/app/uploads"
    OUTPUT_DIR = "/app/outputs"
    LOG_LEVEL  = "INFO"
  }

  depends_on = [kubernetes_namespace.app]
}

# Deployment da aplicação
resource "kubernetes_deployment" "app" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = var.app_name
      }
    }

    template {
      metadata {
        labels = {
          app = var.app_name
        }
      }

      spec {
        container {
          name  = var.app_name
          image = "${var.docker_image}:${var.docker_image_tag}"
          
          port {
            container_port = var.container_port
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          volume_mount {
            name       = "uploads"
            mount_path = "/app/uploads"
          }

          volume_mount {
            name       = "outputs"
            mount_path = "/app/outputs"
          }

          resources {
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
          }
        }

        volume {
          name = "uploads"
          empty_dir {}
        }

        volume {
          name = "outputs"
          empty_dir {}
        }
      }
    }
  }

  depends_on = [kubernetes_config_map.app_config]
}

# Service do tipo LoadBalancer
resource "kubernetes_service" "app" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = {
      app = var.app_name
    }

    port {
      port        = 80
      target_port = var.container_port
    }

    type = "LoadBalancer"
  }

  depends_on = [kubernetes_deployment.app]
}