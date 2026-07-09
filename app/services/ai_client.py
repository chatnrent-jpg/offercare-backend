"""
VettedMe Enterprise Engine - OpenAI Integration Service
Async client wrapper for GPT-4 and GPT-3.5-turbo operations with production-grade error handling.
Implements retry logic, rate limiting, cost tracking, and graceful degradation patterns.
"""

import asyncio
import hashlib
import logging
import os
import time
from decimal import Decimal
from typing import Any, Optional

from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)

# Environment configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_REASONING = os.getenv("OPENAI_MODEL_REASONING", "gpt-4")
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-3.5-turbo")
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60.0"))
OPENAI_RATE_LIMIT_DELAY = float(os.getenv("OPENAI_RATE_LIMIT_DELAY", "2.0"))

# Cost tracking (per 1K tokens, approximate as of 2024)
COST_GPT4_INPUT = Decimal("0.03")
COST_GPT4_OUTPUT = Decimal("0.06")
COST_GPT35_INPUT = Decimal("0.0015")
COST_GPT35_OUTPUT = Decimal("0.002")


class AIClientError(Exception):
    """Base exception for AI client operations."""
    pass


class AIClient:
    """
    VettedMe OpenAI async client wrapper.
    Enforces retry logic, rate limiting, and cost tracking for enterprise operations.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI async client with production configuration.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key or self.api_key == "":
            logger.warning("OpenAI API key not configured - AI features will be disabled")
            self.enabled = False
            self.client = None
        else:
            self.enabled = True
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=OPENAI_TIMEOUT_SECONDS,
                max_retries=0  # Handle retries manually for better control
            )
        
        self.total_requests = 0
        self.total_cost = Decimal("0.00")
    
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict[str, str]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Execute OpenAI chat completion with retry logic and cost tracking.
        
        Args:
            messages: List of chat messages (system, user, assistant)
            model: Model to use (defaults to reasoning model)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            response_format: Optional format specification (e.g., {"type": "json_object"})
        
        Returns:
            Dict with response content, usage stats, and cost, or None on failure
        """
        if not self.enabled:
            logger.warning("OpenAI client not enabled - returning None")
            return None
        
        model = model or OPENAI_MODEL_REASONING
        retry_count = 0
        last_error = None
        
        while retry_count <= OPENAI_MAX_RETRIES:
            try:
                params: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                if max_tokens:
                    params["max_tokens"] = max_tokens
                
                if response_format:
                    params["response_format"] = response_format
                
                start_time = time.time()
                response = await self.client.chat.completions.create(**params)
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Extract response data
                content = response.choices[0].message.content or ""
                usage = response.usage
                
                # Calculate cost
                cost = self._calculate_cost(
                    model=model,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                )
                
                self.total_requests += 1
                self.total_cost += cost
                
                logger.info(
                    "OpenAI request completed: model=%s tokens=%s cost=$%s latency=%dms",
                    model,
                    usage.total_tokens if usage else 0,
                    cost,
                    elapsed_ms,
                )
                
                return {
                    "content": content,
                    "model": model,
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                    "cost": float(cost),
                    "elapsed_ms": elapsed_ms,
                    "finish_reason": response.choices[0].finish_reason,
                }
            
            except RateLimitError as e:
                last_error = e
                retry_count += 1
                if retry_count <= OPENAI_MAX_RETRIES:
                    wait_time = OPENAI_RATE_LIMIT_DELAY * (2 ** (retry_count - 1))
                    logger.warning(
                        "OpenAI rate limit hit - retry %d/%d after %.1fs",
                        retry_count,
                        OPENAI_MAX_RETRIES,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("OpenAI rate limit exceeded max retries: %s", e)
            
            except APITimeoutError as e:
                last_error = e
                retry_count += 1
                if retry_count <= OPENAI_MAX_RETRIES:
                    logger.warning(
                        "OpenAI timeout - retry %d/%d",
                        retry_count,
                        OPENAI_MAX_RETRIES,
                    )
                    await asyncio.sleep(1.0)
                else:
                    logger.error("OpenAI timeout exceeded max retries: %s", e)
            
            except APIError as e:
                last_error = e
                logger.error("OpenAI API error: %s", e)
                break
            
            except Exception as e:
                last_error = e
                logger.error("OpenAI unexpected error: %s", e)
                break
        
        logger.error("OpenAI request failed after %d retries: %s", retry_count, last_error)
        return None
    
    async def fast_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Fast completion using GPT-3.5-turbo for high-throughput operations.
        
        Args:
            messages: List of chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Response dict or None on failure
        """
        return await self.chat_completion(
            messages=messages,
            model=OPENAI_MODEL_FAST,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    async def structured_json_completion(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Optional[dict[str, Any]]:
        """
        Request structured JSON output from OpenAI.
        
        Args:
            messages: List of chat messages
            model: Model to use
            temperature: Sampling temperature (lower for structured output)
        
        Returns:
            Response dict with JSON content or None on failure
        """
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    
    def _calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Decimal:
        """
        Calculate estimated cost for OpenAI API call.
        
        Args:
            model: Model name used
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
        
        Returns:
            Estimated cost in USD
        """
        if "gpt-4" in model.lower():
            input_cost = (Decimal(prompt_tokens) / Decimal("1000")) * COST_GPT4_INPUT
            output_cost = (Decimal(completion_tokens) / Decimal("1000")) * COST_GPT4_OUTPUT
        else:
            input_cost = (Decimal(prompt_tokens) / Decimal("1000")) * COST_GPT35_INPUT
            output_cost = (Decimal(completion_tokens) / Decimal("1000")) * COST_GPT35_OUTPUT
        
        return input_cost + output_cost
    
    def get_usage_summary(self) -> dict[str, Any]:
        """
        Get cumulative usage statistics for this client instance.
        
        Returns:
            Dict with total requests and cost
        """
        return {
            "total_requests": self.total_requests,
            "total_cost_usd": float(self.total_cost),
            "enabled": self.enabled,
        }
    
    @staticmethod
    def hash_input(input_text: str) -> str:
        """
        Generate SHA-256 hash of input text for audit trail.
        
        Args:
            input_text: Text to hash
        
        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(input_text.encode("utf-8")).hexdigest()


# Global singleton instance
_ai_client_instance: Optional[AIClient] = None


def get_ai_client() -> AIClient:
    """
    Get or create global AI client singleton instance.
    
    Returns:
        AIClient instance
    """
    global _ai_client_instance
    if _ai_client_instance is None:
        _ai_client_instance = AIClient()
    return _ai_client_instance
