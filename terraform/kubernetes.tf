# kubernetes.tf
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

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_name
  }

  depends_on = [aws_eks_node_group.main]
}

# Secret com credenciais AWS (do seu .env)
resource "kubernetes_secret" "aws_credentials" {
  metadata {
    name      = "aws-credentials"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    AWS_ACCESS_KEY_ID     = ""
    AWS_SECRET_ACCESS_KEY = ""
    AWS_SESSION_TOKEN     = ""
  }

  type = "Opaque"
}

# ConfigMap com configurações da aplicação
resource "kubernetes_config_map" "app_config" {
  metadata {
    name      = "${var.app_name}-config"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    # AWS Configuration (do seu .env)
    S3_BUCKET_NAME = "video-processor-485453072337-20260116"
    SQS_QUEUE_URL  = "" //https://sqs.us-east-1.amazonaws.com/485453072337/video-processing-queue
    
    # Application Settings
    AWS_REGION          = "us-east-1"
    UPLOAD_DIR          = "/app/uploads"
    OUTPUT_DIR          = "/app/outputs"
    LOG_LEVEL           = "INFO"
    FRAMES_PER_SECOND   = "1"
    MAX_WORKERS         = "5"
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
    replicas = 2

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

          # Configurações do ConfigMap
          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          # Credenciais AWS do Secret
          env {
            name = "AWS_ACCESS_KEY_ID"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.aws_credentials.metadata[0].name
                key  = "AWS_ACCESS_KEY_ID"
              }
            }
          }
          
          env {
            name = "AWS_SECRET_ACCESS_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.aws_credentials.metadata[0].name
                key  = "AWS_SECRET_ACCESS_KEY"
              }
            }
          }
          
          env {
            name = "AWS_SESSION_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.aws_credentials.metadata[0].name
                key  = "AWS_SESSION_TOKEN"
              }
            }
          }
          
          # Garantir variáveis regionais
          env {
            name  = "AWS_DEFAULT_REGION"
            value = "us-east-1"
          }
          
          env {
            name  = "AWS_REGION"
            value = "us-east-1"
          }

          # Volume mounts
          volume_mount {
            name       = "uploads"
            mount_path = "/app/uploads"
          }

          volume_mount {
            name       = "outputs"
            mount_path = "/app/outputs"
          }

          # Resources
          resources {
            limits = {
              cpu    = "1000m"
              memory = "1Gi"
            }
            requests = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          # Health checks
          liveness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }

        # Volumes
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

  depends_on = [
    kubernetes_config_map.app_config,
    kubernetes_secret.aws_credentials
  ]
}

# Service LoadBalancer
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
      protocol    = "TCP"
    }

    type = "LoadBalancer"
  }

  depends_on = [kubernetes_deployment.app]
}