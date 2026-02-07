import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import tempfile
from fastapi import HTTPException, BackgroundTasks
from httpx import AsyncClient, ASGITransport # Adicionada a importação do transport

from app.main import app, services
from app.schemas import ProcessingStatus

@pytest.fixture
def temp_zip_file():
    """Cria um arquivo ZIP temporário para testes de download"""
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(b"fake zip content")
        tmp_path = tmp.name
    yield tmp_path
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

# --- Testes de Endpoints ---

@pytest.mark.asyncio
async def test_process_s3_video_manual_logic():
    """Testa se o endpoint manual agenda a tarefa via BackgroundTasks"""
    mock_processor = Mock()
    transport = ASGITransport(app=app)
    
    # Injetamos o mock apenas para o processor
    with patch.dict(services, {"processor": mock_processor}):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/process/s3/videos/test.mp4",
                params={"title": "Manual", "email": "test@test.com"}
            )
        
        assert response.status_code == 202
        mock_processor.process_message.assert_called_once()

@pytest.mark.asyncio
async def test_list_s3_videos_error_flow():
    """Testa erro 500 quando o serviço S3 não está inicializado"""
    transport = ASGITransport(app=app)
    # Removemos apenas a chave 's3' para forçar o erro 500 específico da rota
    with patch.dict(services, {"s3": None}):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/s3/videos")
        
        # O endpoint verifica: if not s3_svc: raise HTTPException(500)
        assert response.status_code == 500

@pytest.mark.asyncio
async def test_download_zip_not_found():
    """Testa erro 404 para arquivo inexistente"""
    mock_processor = Mock()
    mock_processor.output_dir = Path("/tmp")
    transport = ASGITransport(app=app)
    
    with patch.dict(services, {"processor": mock_processor}):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/download/arquivo_que_nao_existe.zip")
        assert response.status_code == 404

def test_root_endpoint_version():
    """Valida a versão e o nome do serviço no root"""
    with patch.dict(services, {"email": Mock()}):
        from app.main import root
        result = asyncio.run(root())
        assert result["version"] == "2.2.0"
        assert result["service"] == "Video Processing Service"

def test_health_check_logic():
    """Valida a lógica do health check"""
    with patch.dict(services, {"processor": Mock()}):
        from app.main import health_check
        result = asyncio.run(health_check())
        assert result["status"] == "healthy"

@pytest.mark.asyncio
async def test_lifespan_complete_flow():
    """Testa o ciclo de vida completo: injeção e shutdown"""
    from app.main import lifespan
    mock_processor = Mock()
    mock_processor.start_sqs_consumer = AsyncMock()
    
    with patch('app.main.S3Service', return_value=Mock()), \
         patch('app.main.EmailService', return_value=Mock()), \
         patch('app.main.VideoProcessor', return_value=mock_processor), \
         patch('app.main.print_config'):
        
        async with lifespan(app):
            assert "processor" in services
            assert "email" in services
        
        mock_processor.stop_sqs_consumer.assert_called()

def test_app_metadata_consistency():
    """Valida se os metadados da app batem com o esperado"""
    assert app.title == "Video Processing Service"
    assert app.version == "2.2.0"