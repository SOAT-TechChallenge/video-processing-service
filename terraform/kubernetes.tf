# --- AUTENTICAÇÃO NO NOVO CLUSTER ---
data "aws_eks_cluster_auth" "cluster_auth" {
  name = aws_eks_cluster.main.name
}

provider "kubernetes" {
  host                   = aws_eks_cluster.main.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.main.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster_auth.token
}

# --- NAMESPACE & CONFIGS ---
resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_name
  }
  depends_on = [aws_eks_node_group.main] # Espera o Node Group estar pronto
}

resource "kubernetes_secret" "aws_credentials" {
  metadata {
    name      = "aws-credentials"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    AWS_ACCESS_KEY_ID     = var.aws_access_key_id
    AWS_SECRET_ACCESS_KEY = var.aws_secret_access_key
    AWS_SESSION_TOKEN     = var.aws_session_token
  }
  type = "Opaque"
}

resource "kubernetes_config_map" "app_config" {
  metadata {
    name      = "${var.app_name}-config"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    AWS_S3_BUCKET               = var.aws_s3_bucket
    AWS_SQS_QUEUE_URL           = var.aws_sqs_queue_url
    NOTIFICATION_SERVICE_URL    = var.notification_service_url
    AWS_REGION                  = var.aws_region
    SERVER_PORT                 = "8000"
    LOG_LEVEL                   = "INFO"
    API_SECURITY_INTERNAL_TOKEN = "tech-challenge-hackathon"
  }
}

# --- DEPLOYMENT ---
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

          # Credenciais AWS
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
          env {
            name  = "AWS_DEFAULT_REGION"
            value = var.aws_region
          }
          env {
            name  = "AWS_REGION"
            value = var.aws_region
          }

          # Probes para FastAPI
          liveness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 60
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = var.container_port
            }
            initial_delay_seconds = 10
            period_seconds        = 5
          }

          resources {
            limits = {
              cpu    = "1000m"
              memory = "2048Mi"
            }
            requests = {
              cpu    = "500m"
              memory = "1024Mi"
            }
          }
        }
      }
    }
  }
  depends_on = [kubernetes_config_map.app_config, kubernetes_secret.aws_credentials]
}

resource "kubernetes_service" "app" {
  metadata {
    name      = var.app_name
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = {
      app = var.app_name
    }
    type = "NodePort"
    port {
      port        = 80
      target_port = var.container_port
      node_port   = local.node_port # 30008
    }
  }
  depends_on = [kubernetes_deployment.app]
}