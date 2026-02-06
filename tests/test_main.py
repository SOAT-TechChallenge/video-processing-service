import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
from fastapi import HTTPException
from app.main import app, services


@pytest.fixture
def temp_zip_file():
    """Cria um arquivo ZIP temporário para testes de download"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(b"fake zip content")
        tmp_path = tmp.name
    yield tmp_path
    try:
        os.unlink(tmp_path)
    except:
        pass


def test_list_s3_videos_service_not_initialized():
    """Testa quando S3 service não está no dicionário global"""
    with patch.dict(services, {}, clear=True):
        from app.main import list_s3_videos
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_s3_videos())
        assert exc_info.value.status_code == 500

def test_list_processed_files_processor_not_initialized():
    """Testa quando processor não está no dicionário global"""
    with patch.dict(services, {}, clear=True):
        from app.main import list_processed_files
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(list_processed_files())
        assert exc_info.value.status_code == 500

def test_download_zip_logic(temp_zip_file):
    """Testa a lógica do endpoint de download usando o dicionário services"""
    mock_processor = Mock()
    filename = Path(temp_zip_file).name
    
    mock_processor.output_dir = Path(temp_zip_file).parent
    
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import download_zip
        
        with patch('app.main.unquote', return_value=filename):
            result = asyncio.run(download_zip(filename))
            assert result.status_code == 200
            assert result.media_type == "application/zip"

def test_root_endpoint_logic():
    """Testa a lógica do endpoint raiz e valida a versão correta 2.2.0"""
    with patch('app.main.SQS_QUEUE_URL', 'http://test-queue'):
        with patch.dict(services, {"email": Mock()}):
            from app.main import root
            result = asyncio.run(root())
            assert result["service"] == "Video Processing Service"
            assert result["version"] == "2.2.0"
            assert result["mode"] == "auto"

def test_health_check_logic_healthy():
    """Testa health check com o dicionário services preenchido"""
    mock_processor = Mock()
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import health_check
        result = asyncio.run(health_check())
        assert result["status"] == "healthy"

def test_app_configuration():
    """Testa metadados da aplicação FastAPI"""
    assert app.title == "Video Processing Service"
    assert app.version == "2.2.0"

@pytest.mark.asyncio
async def test_lifespan_flow():
    """Substitui o antigo startup/shutdown pelo teste do lifespan"""
    from app.main import lifespan
    
    mock_processor = Mock()
    mock_processor.start_sqs_consumer = AsyncMock()
    
    # Mock das classes para evitar conexões reais durante o teste do lifespan
    with patch('app.main.S3Service', return_value=Mock()):
        with patch('app.main.EmailService', return_value=Mock()):
            with patch('app.main.VideoProcessor', return_value=mock_processor):
                with patch('app.main.print_config'):
                    # Simula o ciclo de vida do FastAPI
                    async with lifespan(app):
                        assert "processor" in services
                        assert "s3" in services
                    
                    # Verifica se o shutdown parou o consumidor
                    mock_processor.stop_sqs_consumer.assert_called()

def test_list_processed_files_logic():
    """Testa listagem de arquivos processados via services"""
    mock_processor = Mock()
    mock_files = [{"filename": "test.zip"}]
    mock_processor.get_processed_files.return_value = mock_files
    
    with patch.dict(services, {"processor": mock_processor}):
        from app.main import list_processed_files
        result = asyncio.run(list_processed_files())
        assert result["files"] == mock_files