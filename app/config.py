import os

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")

# Application Settings
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/outputs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
FRAMES_PER_SECOND = int(os.getenv("FRAMES_PER_SECOND", "1"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))

def validate_config():
    """Valida configurações mínimas"""
    errors = []
    
    if not S3_BUCKET_NAME:
        errors.append("S3_BUCKET_NAME não configurado")
    
    # SQS é opcional
    if SQS_QUEUE_URL and not SQS_QUEUE_URL.startswith("https://sqs."):
        errors.append(f"SQS_QUEUE_URL inválida: {SQS_QUEUE_URL}")
    
    if errors:
        raise ValueError(" | ".join(errors))

def print_config():
    """Imprime configurações (útil para debug)"""
    print("=" * 50)
    print("CONFIGURAÇÕES DO SISTEMA")
    print("=" * 50)
    print(f"📦 S3 Bucket: {S3_BUCKET_NAME}")
    print(f"📧 Notification URL: {NOTIFICATION_SERVICE_URL}")
    
    # Mascarar credenciais nos logs
    aws_key = os.getenv("AWS_ACCESS_KEY_ID", "Não configurada")
    masked_key = aws_key[:4] + "***" + aws_key[-4:] if len(aws_key) > 8 else "***"
    
    print(f"🔑 AWS Key: {masked_key}")
    
    if SQS_QUEUE_URL:
        print(f"📫 SQS Queue: {SQS_QUEUE_URL}")
        print(f"🔧 Modo: Automático (SQS)")
    else:
        print(f"📫 SQS Queue: Não configurada")
        print(f"🔧 Modo: Manual (API)")
    
    print(f"📁 Upload Dir: {UPLOAD_DIR}")
    print(f"📁 Output Dir: {OUTPUT_DIR}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'production')}")
    print("=" * 50)