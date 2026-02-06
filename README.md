# Video Processing Service

[![CI/CD](https://github.com/your-username/video-processing-service/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-username/video-processing-service/actions/workflows/ci-cd.yml)
[![Coverage](https://codecov.io/gh/your-username/video-processing-service/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/video-processing-service)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

Microsserviço de processamento de vídeos desenvolvido com FastAPI, responsável por extrair frames de vídeos e gerar arquivos ZIP compactados. Suporta processamento manual via API e automático via SQS.

## 📋 Sumário

- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação e Execução](#-instalação-e-execução)
- [API Endpoints](#-api-endpoints)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Testes](#-testes)
- [CI/CD](#-cicd)
- [Deploy na AWS](#-deploy-na-aws)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

## ✨ Funcionalidades

- ✅ Processamento simultâneo de múltiplos vídeos
- ✅ Extração de frames (1 frame por segundo)
- ✅ Geração de arquivo ZIP com imagens extraídas
- ✅ Integração com AWS S3 para armazenamento
- ✅ Processamento automático via SQS
- ✅ Notificações por email
- ✅ Documentação interativa (Swagger UI)
- ✅ Health checks
- ✅ Logs estruturados

## 🏗️ Arquitetura

O serviço é composto por:

- **Backend**: FastAPI com Python 3.11+
- **Processamento**: OpenCV para extração de frames
- **Armazenamento**: AWS S3 para vídeos e outputs
- **Mensageria**: AWS SQS para processamento assíncrono
- **Containerização**: Docker + Docker Compose
- **Infraestrutura**: Terraform para AWS (ECS, ECR, ALB)
- **CI/CD**: GitHub Actions

### Fluxo de Processamento

1. Vídeo é enviado para S3 ou processado via API
2. Serviço extrai frames usando OpenCV
3. Imagens são compactadas em ZIP
4. Arquivo ZIP é salvo no S3
5. Notificação por email é enviada (opcional)

## 📋 Pré-requisitos

- Docker Desktop 4.0+
- Python 3.11+ (para desenvolvimento local)
- AWS CLI configurado (para deploy)
- Terraform 1.0+ (para infraestrutura)

## 🚀 Instalação e Execução

### Desenvolvimento Local

1. **Clone o repositório**
   ```bash
   git clone https://github.com/your-username/video-processing-service.git
   cd video-processing-service
   ```

2. **Configure variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite o .env com suas configurações
   ```

3. **Execute com Docker Compose**
   ```bash
   # Build da imagem
   docker-compose build --no-cache

   # Iniciar containers
   docker-compose up -d

   # Verificar logs
   docker-compose logs --tail=20 video-processor
   ```

4. **Acesse a aplicação**
   - API: http://localhost:8000
   - Documentação: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Desenvolvimento sem Docker

1. **Instale dependências**
   ```bash
   pip install -r requirements.txt
   ```

2. **Execute o serviço**
   ```bash
   python -m app.main
   ```

## 📡 API Endpoints

### Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/` | Informações do serviço |
| `GET` | `/health` | Status de saúde |
| `GET` | `/s3/videos` | Lista vídeos no S3 |
| `POST` | `/process/s3/{s3_key}` | Processa vídeo do S3 |
| `GET` | `/processed` | Lista arquivos processados |
| `GET` | `/download/{filename}` | Download do ZIP |

### Exemplo de Uso

```bash
# Processar vídeo
curl -X POST "http://localhost:8000/process/s3/videos/sample.mp4" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "title": "Sample Video"}'
```

## 🔧 Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `AWS_REGION` | Região AWS | `us-east-1` |
| `S3_BUCKET_NAME` | Nome do bucket S3 | - |
| `SQS_QUEUE_URL` | URL da fila SQS | - |
| `UPLOAD_DIR` | Diretório de uploads | `/app/uploads` |
| `OUTPUT_DIR` | Diretório de outputs | `/app/outputs` |
| `FRAMES_PER_SECOND` | Frames por segundo | `1` |
| `MAX_WORKERS` | Máximo de workers | `5` |

## 🧪 Testes

### Executar Todos os Testes

```bash
# Com cobertura
python -m pytest tests/ --cov=app --cov-report=term-missing

# Apenas testes
python -m pytest tests/ -v
```

### Testes por Arquivo

```bash
pytest tests/test_config.py -v
pytest tests/test_main.py -v
pytest tests/test_s3_service.py -v
pytest tests/test_schemas.py -v
pytest tests/test_sqs_consumer.py -v
pytest tests/test_utils.py -v
pytest tests/test_video_processor.py -v
```

## 🔄 CI/CD

O projeto utiliza GitHub Actions para:

- **Quality Checks**: Linting, testes e cobertura
- **Terraform Plan**: Validação da infraestrutura
- **Deploy**: Build e push para ECR, atualização do ECS

### Workflows

- `python-ci`: Testes e qualidade do código
- `terraform-plan`: Planejamento da infraestrutura
- `terraform-apply`: Aplicação da infraestrutura
- `deploy`: Build e deploy da aplicação

## ☁️ Deploy na AWS

### Pré-requisitos

- Conta AWS com permissões adequadas
- Secrets configurados no GitHub

### Deploy Automático

O deploy é feito automaticamente via GitHub Actions no push para `main`.

### Deploy Manual

1. **Inicializar Terraform**
   ```bash
   cd terraform
   terraform init
   ```

2. **Planejar mudanças**
   ```bash
   terraform plan
   ```

3. **Aplicar infraestrutura**
   ```bash
   terraform apply
   ```

### Recursos Criados

- ECR Repository para imagens Docker
- ECS Cluster e Service (Fargate)
- Application Load Balancer
- Security Groups
- CloudWatch Logs

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

### Padrões de Código

- Use Black para formatação
- Adicione testes para novas funcionalidades
- Mantenha cobertura acima de 80%

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
