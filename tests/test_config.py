import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch

# ========== Testes para Config ==========

def test_config_validation():
    """Testa validação de configuração"""
    from app.config import validate_config, S3_BUCKET_NAME, SQS_QUEUE_URL
    
    # Mock S3_BUCKET_NAME e SQS_QUEUE_URL para teste
    import app.config
    
    # Guarda valores originais
    original_bucket = app.config.S3_BUCKET_NAME
    original_queue = app.config.SQS_QUEUE_URL
    
    try:
        # Teste com bucket vazio
        app.config.S3_BUCKET_NAME = ""
        app.config.SQS_QUEUE_URL = ""
        with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
            validate_config()
        
        # Teste com bucket configurado
        app.config.S3_BUCKET_NAME = "my-bucket"
        app.config.SQS_QUEUE_URL = ""
        validate_config()  # Não deve lançar exceção
        
        # Teste com SQS URL inválida
        app.config.SQS_QUEUE_URL = "invalid-url"
        with pytest.raises(ValueError, match="SQS_QUEUE_URL"):
            validate_config()
            
        # Teste com SQS URL válida
        app.config.SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"
        validate_config()  # Não deve lançar exceção
        
    finally:
        # Restaura valores originais
        app.config.S3_BUCKET_NAME = original_bucket
        app.config.SQS_QUEUE_URL = original_queue

def test_config_print():
    """Testa função de impressão de configuração"""
    from app.config import print_config
    
    # Mock das variáveis de ambiente
    with patch.dict('os.environ', {
        'AWS_ACCESS_KEY_ID': 'TESTKEY1234567890',
        'S3_BUCKET_NAME': 'test-bucket',
        'SQS_QUEUE_URL': 'https://sqs.test.queue',
        'UPLOAD_DIR': '/tmp/uploads',
        'OUTPUT_DIR': '/tmp/outputs',
        'ENVIRONMENT': 'test'
    }, clear=True):
        # Importa novamente para pegar as variáveis mockadas
        import importlib
        import app.config
        importlib.reload(app.config)
        
        # Captura a saída de print
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            app.config.print_config()
        
        output = f.getvalue()
        
        # Verifica se informações importantes estão na saída
        assert "test-bucket" in output
        assert "TESTKEY***7890" in output or "TEST***" in output 
        assert "sqs.test.queue" in output
        assert "/tmp/uploads" in output
        assert "/tmp/outputs" in output
        assert "test" in output
        
        # Restaura o módulo original
        importlib.reload(app.config)