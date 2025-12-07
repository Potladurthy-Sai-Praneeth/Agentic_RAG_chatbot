from typing import Dict, Any
import httpx
import asyncio
import logging 
from RAG.context import current_jwt_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceClient:
    """HTTP client for microservice communication with retry logic."""
    
    def __init__(self, base_url: str, service_name: str, config: Dict):
        """
        Initialize service client.
        
        Args:
            base_url: Base URL of the service
            service_name: Name of the service (for logging)
        """
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.settings = config.get("retry", {})
        self.timeout = httpx.Timeout(self.settings.get("service_timeout", 30))
        
    async def _request(
        self,
        method: str,
        endpoint: str,
        requires_auth: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for httpx
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = kwargs.get("headers", {})

        if requires_auth:
            # For internal service-to-service calls, we need to forward the token
            # The token should be passed via headers in kwargs if available
            # Otherwise, we'll rely on the service's own auth middleware
            if "Authorization" not in headers:
                # Try to get token from context (though it stores decoded payload)
                # In practice, the calling service should pass the Authorization header
                pass

        kwargs.setdefault("headers", headers)


        max_retries = self.settings.get("max_retries", 3)
        retry_delay = self.settings.get("retry_delay", 1.0)
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPError as e:
                logger.warning(
                    f"[{self.service_name}] Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * (attempt + 1))
    
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return await self._request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return await self._request("POST", endpoint, **kwargs)
    
    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self._request("DELETE", endpoint, **kwargs)
    
    async def health_check(self) -> bool:
        """
        Check if service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self.get("/health", requires_auth=False)
            return response.get("status") in ["healthy", "ok", "running"]
        except Exception as e:
            logger.error(f"[{self.service_name}] Health check failed: {str(e)}")
            return False