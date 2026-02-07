# --- ECR ---
resource "aws_ecr_repository" "video_processing" {
  name                 = "video-processing-repo"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

# --- Security Groups ---
resource "aws_security_group" "alb_sg" {
  name        = "${var.app_name}-alb-sg"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "${var.app_name}-ecs-sg"
  vpc_id      = data.aws_vpc.default.id
  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- Load Balancer (ALB) ---
resource "aws_lb" "processing_alb" {
  name               = "${var.app_name}-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = slice(data.aws_subnets.all.ids, 0, min(2, length(data.aws_subnets.all.ids)))
}

resource "aws_lb_target_group" "processing_tg" {
  name        = "${var.app_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"
  health_check {
    path                = "/health"
    interval            = 60
    timeout             = 30
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.processing_alb.arn
  port              = "80"
  protocol          = "HTTP"
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Acesso Direto Negado. Use o API Gateway."
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "allow_gateway" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.processing_tg.arn
  }
  condition {
    http_header {
      http_header_name = "x-apigateway-token"
      values           = ["tech-challenge-hackathon"]
    }
  }
}

# --- ECS Cluster & Task ---
resource "aws_ecs_cluster" "processing_cluster" {
  name = var.cluster_name
}

resource "aws_ecs_task_definition" "processing_task" {
  family                   = "${var.app_name}-v3"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = data.aws_iam_role.lab_role.arn
  task_role_arn            = data.aws_iam_role.lab_role.arn

  container_definitions = jsonencode([{
    name      = var.app_name
    image     = "${aws_ecr_repository.video_processing.repository_url}:latest"
    essential = true
    portMappings = [{ containerPort = var.container_port }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/${var.app_name}"
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
        awslogs-create-group  = "true"
      }
    }
    environment = [
      { name = "SERVER_PORT", value = tostring(var.container_port) },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "API_SECURITY_INTERNAL_TOKEN", value = "tech-challenge-hackathon" },
      { name = "SQS_QUEUE_URL", value = data.aws_sqs_queue.video_queue.url },
      { name = "NOTIFICATION_SERVICE_URL", value = "http://${data.aws_ssm_parameter.notification_alb_url.value}" },
      { name = "S3_BUCKET_NAME", value = data.aws_ssm_parameter.video_bucket_name.value }
    ]
  }])
}

resource "aws_ecs_service" "processing_service" {
  name            = var.app_name
  cluster         = aws_ecs_cluster.processing_cluster.id
  task_definition = aws_ecs_task_definition.processing_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  health_check_grace_period_seconds = 300

  network_configuration {
    subnets          = slice(data.aws_subnets.all.ids, 0, min(2, length(data.aws_subnets.all.ids)))
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.processing_tg.arn
    container_name   = var.app_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener_rule.allow_gateway]

  lifecycle {
    ignore_changes = [task_definition, load_balancer]
  }
}

resource "aws_ssm_parameter" "processing_alb_dns" {
  name        = "/video-processing/alb_dns_name"
  description = "DNS do Load Balancer do Video Processing para o API Gateway"
  type        = "String"
  value       = aws_lb.processing_alb.dns_name
  overwrite   = true
}