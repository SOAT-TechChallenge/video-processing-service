import boto3
import logging
from .config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = S3_BUCKET_NAME
        
        logger.info(f"✅ S3 Service inicializado")
        logger.info(f"   Bucket: {self.bucket_name}")
        logger.info(f"   Usando credenciais AWS do ambiente/CLI")
    
    def download_video(self, s3_key: str, local_path: str) -> str:
        """Baixa um vídeo do S3 para um caminho local"""
        try:
            logger.info(f"⬇️ Baixando: {self.bucket_name}/{s3_key}")
            
            self.s3_client.download_file(
                self.bucket_name, 
                s3_key, 
                local_path
            )
            
            logger.info(f"✅ Baixado: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Erro ao baixar: {e}")
            raise
    
    def list_videos(self, prefix: str = "videos/") -> list:
        """Lista vídeos no bucket S3"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            videos = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    videos.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat()
                    })
            
            logger.info(f"📋 {len(videos)} vídeos encontrados")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar: {e}")
            return []
    
    def video_exists(self, s3_key: str) -> bool:
        """Verifica se um vídeo existe no S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except:
            return False
    
    def get_video_info(self, s3_key: str) -> dict:
        """Obtém informações sobre um vídeo no S3"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return {
                'key': s3_key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType', 'unknown')
            }
        except Exception as e:
            logger.error(f"❌ Erro ao obter info: {e}")
            return {}