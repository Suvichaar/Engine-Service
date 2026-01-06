"""Azure Key Vault integration for secure secret management."""

import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import Azure Key Vault SDK
try:
    from azure.keyvault.secrets import SecretClient
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    AZURE_KEYVAULT_AVAILABLE = True
except ImportError:
    AZURE_KEYVAULT_AVAILABLE = False
    logger.warning("Azure Key Vault SDK not available. Install with: pip install azure-keyvault-secrets azure-identity")


@lru_cache(maxsize=1)
def get_keyvault_client() -> Optional[SecretClient]:
    """Get Azure Key Vault client using Managed Identity or DefaultAzureCredential.
    
    Returns:
        SecretClient if available, None otherwise
    """
    if not AZURE_KEYVAULT_AVAILABLE:
        return None
    
    # Get Key Vault URL from environment variable
    keyvault_url = os.getenv("AZURE_KEYVAULT_URL")
    if not keyvault_url:
        logger.debug("AZURE_KEYVAULT_URL not set, skipping Key Vault")
        return None
    
    try:
        # Try Managed Identity first (for Azure Container Apps/Container Instances)
        # Then fallback to DefaultAzureCredential (for local dev with Azure CLI login)
        try:
            credential = ManagedIdentityCredential()
            logger.info("✅ Using Managed Identity for Azure Key Vault")
        except Exception:
            credential = DefaultAzureCredential()
            logger.info("✅ Using DefaultAzureCredential for Azure Key Vault")
        
        client = SecretClient(vault_url=keyvault_url, credential=credential)
        logger.info(f"✅ Azure Key Vault client initialized: {keyvault_url}")
        return client
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize Azure Key Vault client: {e}")
        return None


def get_secret_from_keyvault(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret from Azure Key Vault.
    
    Args:
        secret_name: Name of the secret in Key Vault
        default: Default value if secret not found
        
    Returns:
        Secret value or default
    """
    client = get_keyvault_client()
    if not client:
        return default
    
    try:
        secret = client.get_secret(secret_name)
        logger.debug(f"✅ Retrieved secret '{secret_name}' from Key Vault")
        return secret.value
    except Exception as e:
        logger.warning(f"⚠️ Failed to get secret '{secret_name}' from Key Vault: {e}")
        return default


def load_secrets_from_keyvault() -> Dict[str, Any]:
    """Load all application secrets from Azure Key Vault.
    
    Maps Key Vault secret names to configuration sections.
    
    Returns:
        Dictionary with configuration overrides from Key Vault
    """
    if not AZURE_KEYVAULT_AVAILABLE:
        return {}
    
    # Check if Key Vault is enabled
    if not os.getenv("AZURE_KEYVAULT_URL"):
        return {}
    
    logger.info("🔐 Loading secrets from Azure Key Vault...")
    
    # Mapping: Key Vault secret name -> (section, key)
    # You can customize these secret names based on your Key Vault setup
    secret_mapping = {
        # Azure OpenAI
        "azure-openai-endpoint": ("azure_api", "endpoint"),
        "azure-openai-api-key": ("azure_api", "api_key"),
        "azure-openai-deployment": ("azure_api", "deployment"),
        "azure-openai-api-version": ("azure_api", "api_version"),
        
        # AI Image (DALL-E)
        "ai-image-endpoint": ("ai_image", "endpoint"),
        "ai-image-api-key": ("ai_image", "api_key"),
        
        # Pexels
        "pexels-api-key": ("pexels", "api_key"),
        
        # Azure Speech
        "azure-speech-key": ("azure_speech", "api_key"),
        "azure-speech-region": ("azure_speech", "region"),
        "voice-name": ("azure_speech", "voice_name"),
        
        # Azure Document Intelligence
        "azure-di-endpoint": ("azure_di", "endpoint"),
        "azure-di-key": ("azure_di", "api_key"),
        
        # AWS
        "aws-access-key": ("aws", "access_key"),
        "aws-secret-key": ("aws", "secret_key"),
        "aws-region": ("aws", "region"),
        "aws-bucket": ("aws", "bucket"),
        "s3-prefix": ("aws", "s3_prefix"),
        "html-s3-prefix": ("aws", "html_s3_prefix"),
        "cdn-prefix-media": ("aws", "cdn_prefix_media"),
        "cdn-html-base": ("aws", "cdn_html_base"),
        "cdn-base": ("aws", "cdn_base"),
        
        # ElevenLabs
        "elevenlabs-api-key": ("elevenlabs", "api_key"),
        "elevenlabs-voice-id": ("elevenlabs", "voice_id"),
        
        # Database
        "database-url": ("database", "url"),
    }
    
    overrides: Dict[str, Any] = {}
    
    for secret_name, (section, key) in secret_mapping.items():
        value = get_secret_from_keyvault(secret_name)
        if value:
            if section not in overrides:
                overrides[section] = {}
            overrides[section][key] = value
            logger.debug(f"✅ Loaded {section}.{key} from Key Vault")
    
    logger.info(f"✅ Loaded {sum(len(v) if isinstance(v, dict) else 1 for v in overrides.values())} secrets from Key Vault")
    return overrides

