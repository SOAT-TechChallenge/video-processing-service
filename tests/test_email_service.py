import pytest
import respx
import httpx
import os
from unittest.mock import patch
from app.email_service import EmailService

@pytest.fixture
def mock_env():
    """Mock das variáveis de ambiente necessárias para o serviço"""
    with patch.dict(os.environ, {
        "NOTIFICATION_SERVICE_URL": "http://notification-service",
        "API_SECURITY_INTERNAL_TOKEN": "test-token-secret"
    }):
        # Forçamos a reinicialização das variáveis caso o módulo já tenha sido carregado
        yield

@pytest.fixture
def email_service(mock_env):
    """Instância do serviço com ambiente mockado"""
    return EmailService()

# --- Testes ---

@pytest.mark.asyncio
@respx.mock
async def test_send_process_start_success(email_service):
    """🚀 NOVO: Testa o aviso de início de processamento"""
    url = "http://notification-service/api/notification/send-email"
    route = respx.post(url).mock(return_value=httpx.Response(200))

    result = await email_service.send_process_start(
        recipient_email="instrutor@kungfu.com",
        video_title="Aula de Formas"
    )

    assert result is True
    assert route.called
    request_data = route.calls.last.request.content.decode()
    assert "Aula de Formas" in request_data
    assert "recebemos o seu vídeo" in request_data.lower()
    assert route.calls.last.request.headers["x-apigateway-token"] == "test-token-secret"

@pytest.mark.asyncio
@respx.mock
async def test_send_process_completion_success(email_service):
    """Testa o envio de sucesso (Fim do processo)"""
    url = "http://notification-service/api/notification/send-email"
    route = respx.post(url).mock(return_value=httpx.Response(200))

    result = await email_service.send_process_completion(
        recipient_email="user@test.com",
        video_title="Meu Video",
        zip_filename="video_123.zip"
    )

    assert result is True
    assert route.called
    request_payload = route.calls.last.request.content.decode()
    assert "Meu Video" in request_payload
    assert "video_123.zip" in request_payload

@pytest.mark.asyncio
@respx.mock
async def test_send_process_error_logic(email_service):
    """Testa o envio de aviso de erro"""
    url = "http://notification-service/api/notification/send-email"
    route = respx.post(url).mock(return_value=httpx.Response(200))

    result = await email_service.send_process_error(
        recipient_email="user@test.com",
        video_title="Video Falho",
        error_message="Codec incompatível"
    )

    assert result is True
    payload = route.calls.last.request.content.decode()
    assert "Video Falho" in payload
    assert "Codec incompatível" in payload

@pytest.mark.asyncio
@respx.mock
async def test_notification_service_failure(email_service):
    """Testa erro 500 no microsserviço de notificação (Spring Boot)"""
    url = "http://notification-service/api/notification/send-email"
    respx.post(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    result = await email_service.send_process_completion("u@t.com", "V", "Z")

    assert result is False

@pytest.mark.asyncio
async def test_missing_config_abort():
    """Testa se o serviço aborta o envio se a URL estiver vazia"""
    with patch.dict(os.environ, {"NOTIFICATION_SERVICE_URL": ""}, clear=True):
        svc = EmailService()
        result = await svc.send_process_completion("u@t.com", "V", "Z")
        assert result is False

@pytest.mark.asyncio
@respx.mock
async def test_connection_timeout(email_service):
    """Testa comportamento em caso de timeout na rede"""
    url = "http://notification-service/api/notification/send-email"
    respx.post(url).side_effect = httpx.ConnectTimeout

    result = await email_service.send_process_completion("u@t.com", "V", "Z")
    
    assert result is False