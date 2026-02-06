import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch
import importlib

# ========== Testes para Config ==========

def test_config_validation():
    """Testa validação de configuração obrigatória"""
    import app.config
    
    # Mock das funções de validação para testar a lógica sem derrubar o processo
    # Nota: Como o S3_BUCKET_NAME agora pode vir do SSM no deploy real, 
    # nos testes garantimos que a validação aceita valores injetados.
    
    original_bucket = app.config.S3_BUCKET_NAME
    original_notification_url = getattr(app.config, 'NOTIFICATION_SERVICE_URL', None)
    
    try:
        # 1. Teste de falha: Sem Bucket S3
        app.config.S3_BUCKET_NAME = ""
        with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
            app.config.validate_config()
            
        # 2. Teste de sucesso: Configuração básica presente
        app.config.S3_BUCKET_NAME = "my-test-bucket"
        # validate_config não deve lançar erro aqui
        app.config.validate_config()
        
    finally:
        # Restaura valores originais para não afetar outros testes
        app.config.S3_BUCKET_NAME = original_bucket

def test_config_print():
    """Testa a função de log das configurações (mascarando dados sensíveis)"""
    # Mock das variáveis de ambiente para o reload do módulo
    mock_env = {
        'AWS_ACCESS_KEY_ID': 'AKIA1234567890EXAMPLE',
        'S3_BUCKET_NAME': 'video-storage-test',
        'SQS_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/1234/test-queue',
        'NOTIFICATION_SERVICE_URL': 'http://notification-api',
        'ENVIRONMENT': 'testing'
    }

    with patch.dict(os.environ, mock_env):
        import app.config
        importlib.reload(app.config)
        
        # Captura a saída do print_config
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            app.config.print_config()
        
        output = f.getvalue()
        
        # Validações de sanidade no log
        assert "video-storage-test" in output
        assert "sqs.us-east-1.amazonaws.com" in output
        assert "http://notification-api" in output
        # Valida se o Access Key foi mascarado (Segurança!)
        assert "AKIA***" in output
        assert "MPLE" in output
        assert "AKIA1234567890EXAMPLE" not in output # Não pode exibir a chave inteira

def test_missing_notification_url_warning():
    """Verifica se o sistema aceita a ausência da URL de notificação (modo manual)"""
    import app.config
    original_url = getattr(app.config, 'NOTIFICATION_SERVICE_URL', None)
    
    try:
        app.config.NOTIFICATION_SERVICE_URL = None
        # A validação não deve quebrar, pois o serviço pode rodar sem notificações
        app.config.validate_config() 
    finally:
        app.config.NOTIFICATION_SERVICE_URL = original_url