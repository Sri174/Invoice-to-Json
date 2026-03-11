"""
gemini_client.py
----------------
Google Gemini API client for invoice extraction with robust retry logic.
Implements exponential backoff and fallback strategies.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
import requests
from requests.exceptions import RequestException, Timeout

from invoice_engine.json_repair import parse_json_with_repair, clean_json_string

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Robust Gemini API client with retry logic and error handling.
    """
    
    # Default retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [2, 4, 8]  # Exponential backoff in seconds
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        max_retries: int = 3,
        timeout: int = 90
    ):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google Gemini API key (reads from GEMINI_API_KEY env if None)
            model: Gemini model to use (default: gemini-1.5-flash)
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 90)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. "
                "Set environment variable or pass api_key parameter."
            )
        
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.base_url = "https://generativelanguage.googleapis.com/v1/models"
        self.endpoint = f"{self.base_url}/{self.model}:generateContent"
        
        logger.info(f"GeminiClient initialized with model={model}, max_retries={max_retries}")
    
    def extract_invoice(
        self, 
        invoice_text: str, 
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract invoice data using Gemini with retry logic.
        
        Args:
            invoice_text: Combined OCR text from all pages
            schema: JSON schema that output must follow
        
        Returns:
            Extracted invoice data as dict matching schema
        
        Raises:
            Exception: If all retry attempts fail
        """
        prompt = self._build_extraction_prompt(invoice_text, schema)
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Gemini extraction attempt {attempt}/{self.max_retries}")
                
                response = self._call_gemini_api(prompt)
                result = self._parse_gemini_response(response)
                
                logger.info("Gemini extraction successful")
                return result
                
            except (RequestException, Timeout) as e:
                logger.warning(f"Attempt {attempt} failed: {str(e)}")
                
                if attempt < self.max_retries:
                    delay = self.RETRY_DELAYS[attempt - 1] if attempt <= len(self.RETRY_DELAYS) else 8
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("All retry attempts exhausted")
                    raise Exception(f"Gemini API failed after {self.max_retries} attempts: {str(e)}")
            
            except Exception as e:
                logger.error(f"Unexpected error during Gemini extraction: {str(e)}")
                raise
    
    def _build_extraction_prompt(
        self, 
        invoice_text: str, 
        schema: Dict[str, Any]
    ) -> str:
        """
        Build the extraction prompt for Gemini.
        
        Args:
            invoice_text: OCR extracted text
            schema: Target JSON schema
        
        Returns:
            Formatted prompt string
        """
        schema_json = json.dumps(schema, indent=2)
        
        prompt = f"""You are an expert invoice extraction AI.

Extract invoice information from the text below and return ONLY valid, well-formed JSON.

CRITICAL JSON FORMATTING RULES:
1. Every opening brace {{ must have a closing brace }}
2. Every object in an array must be complete and properly closed
3. Use proper comma placement (comma after each item except the last)
4. Do not use trailing commas before closing brackets
5. Ensure all quotes are balanced
6. Return ONLY the JSON object - no explanations, no markdown blocks, no extra text

SCHEMA TO FOLLOW:
{schema_json}

INVOICE TEXT:
{invoice_text}

EXTRACTION RULES:
- Include ALL fields from the schema (never omit fields)
- If a value is missing: use null for numbers, "" for strings, false for booleans
- Never add fields not in the schema
- Match the exact structure and field names
- Ensure proper JSON syntax throughout
- Each line_item object must be complete with all fields

Return the JSON now:
"""
        return prompt
    
    def _call_gemini_api(self, prompt: str) -> Dict[str, Any]:
        """
        Make API call to Gemini.
        
        Args:
            prompt: Extraction prompt
        
        Returns:
            Raw API response as dict
        
        Raises:
            RequestException: On HTTP errors
            Timeout: On timeout
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,  # Low temperature for consistent extraction
                "topK": 1,
                "topP": 1,
                "maxOutputTokens": 8192,
            }
        }
        
        url = f"{self.endpoint}?key={self.api_key}"
        
        logger.debug(f"Calling Gemini API: {url}")
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        
        # Handle HTTP errors
        if response.status_code == 429:
            raise RequestException("Rate limit exceeded (429)")
        elif response.status_code == 500:
            raise RequestException("Gemini server error (500)")
        elif response.status_code != 200:
            raise RequestException(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def _parse_gemini_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Gemini API response and extract JSON.
        
        Args:
            response: Raw API response
        
        Returns:
            Parsed invoice data as dict
        
        Raises:
            ValueError: If response cannot be parsed
        """
        try:
            # Extract text from response
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Gemini response")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                raise ValueError("No parts in Gemini response")
            
            text = parts[0].get("text", "")
            
            if not text:
                raise ValueError("Empty text in Gemini response")
            
            # Clean and parse JSON with repair attempts
            text = clean_json_string(text)
            result = parse_json_with_repair(text)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.debug(f"Raw response: {response}")
            raise ValueError(f"Invalid JSON in Gemini response: {str(e)}")
        
        except Exception as e:
            logger.error(f"Response parsing error: {str(e)}")
            raise ValueError(f"Failed to parse Gemini response: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test Gemini API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing Gemini API connection...")
            
            test_prompt = "Say 'OK' if you can read this."
            
            response = self._call_gemini_api(test_prompt)
            
            logger.info("Gemini API connection successful")
            return True
            
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {str(e)}")
            return False


class GeminiClientFactory:
    """Factory for creating Gemini clients with different configurations."""
    
    @staticmethod
    def create_production_client() -> GeminiClient:
        """Create a production-grade Gemini client with optimal settings."""
        return GeminiClient(
            model="gemini-1.5-flash",
            max_retries=3,
            timeout=90
        )
    
    @staticmethod
    def create_fast_client() -> GeminiClient:
        """Create a fast Gemini client for testing."""
        return GeminiClient(
            model="gemini-1.5-flash",
            max_retries=2,
            timeout=30
        )
    
    @staticmethod
    def create_robust_client() -> GeminiClient:
        """Create a robust client with extended retries."""
        return GeminiClient(
            model="gemini-1.5-flash",
            max_retries=5,
            timeout=120
        )
