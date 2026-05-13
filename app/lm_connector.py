"""
LM Connect Module
This module provides connection functionality to locally hosted LM Studio instances
and can be integrated with Langchain for LLM operations.
"""

import os
from dotenv import load_dotenv
import requests
from typing import Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass

load_dotenv()

@dataclass
class LMConfig:
    """Configuration for LM Studio connection"""
    host: str = os.getenv("LM_STUDIO_HOST") or "localhost"
    port: int = int(os.getenv("LM_STUDIO_PORT") or "1234")
    api_base: str = os.getenv("LM_STUDIO_API_BASE") or "/v1"
    model_name: str = os.getenv("LM_STUDIO_MODEL") or "default-model"

class LMConnection:
    """Main class to handle connection to LM Studio"""
    
    def __init__(self, config: LMConfig):
        self.config = config
        # Normalize host to ensure proper URL format
        if config.host.startswith("http://") or config.host.startswith("https://"):
            parsed = urlparse(config.host)
            scheme = parsed.scheme
            hostname = parsed.hostname
            if hostname:
                self.base_url = f"{scheme}://{hostname}:{config.port}{config.api_base}"
            else:
                raise ValueError(f"Invalid host: {config.host}")
        else:
            self.base_url = f"http://{config.host}:{config.port}{config.api_base}"
        self.session = requests.Session()
        
    def test_connection(self) -> bool:
        """Test if connection to LM Studio is working"""
        try:
            response = self.session.get(f"{self.base_url}/models")
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_models(self) -> Dict[str, Any]:
        """Get available models from LM Studio"""
        try:
            response = self.session.get(f"{self.base_url}/models")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch models: {e}")
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get specific model information"""
        try:
            response = self.session.get(f"{self.base_url}/models/{model_name}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch model info: {e}")
    
    def chat_completion(self, messages: list, **kwargs) -> Dict[str, Any]:
        """Send chat completion request to LM Studio"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            **kwargs
        }
        print(payload)
        
        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to get chat completion: {e}")

# Langchain-compatible adapter
class LangChainAdapter:
    """Adapter to make LMConnection compatible with LangChain"""
    
    def __init__(self, lm_connection: LMConnection):
        self.lm_connection = lm_connection
    
    def invoke(self, messages: list) -> str:
        """Invoke chat completion and return just the response text"""
        result = self.lm_connection.chat_completion(messages)
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    def get_config(self) -> LMConfig:
        """Get the configuration"""
        return self.lm_connection.config

# Convenience function for quick setup
def create_lm_connection(
    host: str = "localhost",
    port: int = 1234,
    model_name: str = "default-model"
) -> LMConnection:
    """Create and return a configured LMConnection instance"""
    config = LMConfig(host=host, port=port, model_name=model_name)
    return LMConnection(config)

# Example usage and testing
if __name__ == "__main__":
    # Create connection instance
    lm_conn = create_lm_connection()
    
    # Test the connection
    print("Testing LM Studio connection...")
    if lm_conn.test_connection():
        print("✓ Connection successful!")
        
        # Get models
        try:
            data = lm_conn.get_models()
            models = list(data.get('data', {}))
            print(f"Available models: {[d['id'] for d in models]} ")
        except Exception as e:
            print(f"Error fetching models: {e}")
        
        # Test chat completion
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]
        
        try:
            response = lm_conn.chat_completion(test_messages)
            print(f"Chat response: {response.get('choices', [{}])[0].get('message', {}).get('content', 'No content')}")
        except Exception as e:
            print(f"Error in chat completion: {e}")
    else:
        print("✗ Connection failed. Please ensure LM Studio is running.")