# Microserviço de Processamento de Vídeos

Este microsserviço é responsável por:
1. Receber múltiplos vídeos simultaneamente
2. Extrair frames dos vídeos (1 frame por segundo)
3. Criar arquivo ZIP com as imagens extraídas

## Pré-requisitos

- Docker Desktop instalado
- Python 3.11+ (para desenvolvimento local)

## Como Rodar Localmente

1. Buildar a imagem definida no docker-compose
   - docker-compose build --no-cache
2. Criar/Iniciar os containers
   - docker-compose up -d
3. Verificar nos logs se subiu tudo corretamente
   - docker-compose logs --tail=20 video-processor
4. Acessar o swagger e validar os endpoints
   - http://localhost:8000/docs

## Como Rodar pela AWS

1. Iniciar o diretório do projeto
   - terraform init
2. Criar plano de execução
   - terraform plan
3. Executar plano criado
   - terraform apply