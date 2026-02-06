import pytest
import respx
import httpx
import os
from unittest.mock import patch
from app.email_service import EmailService

@pytest.fixture
def mock_env():
    """Mock das variáveis de ambiente necessárias"""
    with patch.dict(os.environ, {
        "NOTIFICATION_SERVICE_URL": "http://notification-service",
        "API_SECURITY_INTERNAL_TOKEN": "test-token-secret"
    }):
        yield

@pytest.fixture
def email_service(mock_env):
    """Instância do serviço com ambiente mockado"""
    return EmailService()

# --- Testes ---

@pytest.mark.asyncio
@respx.mock # Intercepta chamadas HTTP
async def test_send_process_completion_success(email_service):
    """Testa o envio de sucesso quando o serviço de notificação responde 200"""
    
    # Configura o mock do endpoint
    url = "http://notification-service/api/notification/send-email"
    route = respx.post(url).mock(return_value=httpx.Response(200))

    result = await email_service.send_process_completion(
        recipient_email="user@test.com",
        video_title="Meu Video",
        zip_filename="video_123.zip"
    )

    # Asserts
    assert result is True
    assert route.called
    # Verifica se o payload enviado está correto
    request_data = route.calls.last.request.content.decode()
    assert "Meu Video" in request_data
    assert "video_123.zip" in request_data
    assert route.calls.last.request.headers["x-apigateway-token"] == "test-token-secret"

@pytest.mark.asyncio
@respx.mock
async def test_send_process_error_logic(email_service):
    """Testa o envio de erro quando o serviço de notificação responde 200"""
    
    url = "http://notification-service/api/notification/send-email"
    route = respx.post(url).mock(return_value=httpx.Response(200))

    result = await email_service.send_process_error(
        recipient_email="user@test.com",
        video_title="Video Falho",
        error_message="Formato inválido"
    )

    assert result is True
    assert "Video Falho" in route.calls.last.request.content.decode()
    assert "Formato inválido" in route.calls.last.request.content.decode()

@pytest.mark.asyncio
@respx.mock
async def test_notification_service_failure(email_service):
    """Testa comportamento quando o Notification Service retorna erro (ex: 500)"""
    
    url = "http://notification-service/api/notification/send-email"
    respx.post(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    result = await email_service.send_process_completion("u@t.com", "V", "Z")

    assert result is False

@pytest.mark.asyncio
async def test_missing_config_abort(mock_env):
    """Testa se o serviço aborta o envio se a URL não estiver configurada"""
    with patch.dict(os.environ, {"NOTIFICATION_SERVICE_URL": ""}, clear=True):
        svc = EmailService()
        result = await svc.send_process_completion("u@t.com", "V", "Z")
        assert result is False

@pytest.mark.asyncio
@respx.mock
async def test_connection_timeout(email_service):
    """Testa erro de timeout/conexão"""
    url = "http://notification-service/api/notification/send-email"
    respx.post(url).side_effect = httpx.ConnectTimeout

    result = await email_service.send_process_completion("u@t.com", "V", "Z")
    
    assert result is False