"""
invoice_mapper.py
-----------------
Maps and validates extracted invoice data to the constant universal schema.
Ensures output always matches the schema structure exactly.
"""

import json
import logging
from typing import Dict, Any, List
from copy import deepcopy

from invoice_engine.schema_loader import get_universal_schema

logger = logging.getLogger(__name__)


class InvoiceMapper:
    """
    Maps extracted invoice data to the constant universal schema.
    Guarantees that output always matches schema structure.
    """
    
    def __init__(self):
        """Initialize invoice mapper with schema."""
        self.schema = get_universal_schema()
        logger.info("InvoiceMapper initialized")
    
    def map_to_schema(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map extracted data to universal schema.
        Fills in extracted values while preserving schema structure.
        
        Args:
            extracted_data: Raw extracted data from LLM or OCR
        
        Returns:
            Invoice data matching universal schema exactly
        """
        try:
            # Start with empty schema template
            result = self._get_empty_schema()
            
            # Merge extracted data into schema
            result = self._merge_data(result, extracted_data)
            
            # Validate structure
            if not self._validate_structure(result):
                logger.warning("Structure validation failed, returning empty schema")
                return self._get_empty_schema()
            
            logger.info("Successfully mapped data to schema")
            return result
            
        except Exception as e:
            logger.error(f"Mapping failed: {str(e)}")
            # Return empty schema on any error
            return self._get_empty_schema()
    
    def _get_empty_schema(self) -> Dict[str, Any]:
        """
        Get a deep copy of the empty schema.
        
        Returns:
            Empty schema dict
        """
        return deepcopy(self.schema)
    
    def _merge_data(
        self, 
        template: Dict[str, Any], 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively merge extracted data into schema template.
        Only updates values that exist in template.
        
        Args:
            template: Schema template (target structure)
            data: Extracted data (source values)
        
        Returns:
            Merged result
        """
        result = deepcopy(template)
        
        for key in result.keys():
            if key not in data:
                # Key not in extracted data, keep default
                continue
            
            template_value = result[key]
            data_value = data[key]
            
            # Handle nested dictionaries
            if isinstance(template_value, dict) and isinstance(data_value, dict):
                result[key] = self._merge_data(template_value, data_value)
            
            # Handle lists (e.g., line_items)
            elif isinstance(template_value, list) and isinstance(data_value, list):
                result[key] = self._merge_list(template_value, data_value)
            
            # Handle primitive values
            else:
                # Validate and assign value
                result[key] = self._validate_value(data_value, template_value)
        
        return result
    
    def _merge_list(
        self, 
        template_list: List, 
        data_list: List
    ) -> List:
        """
        Merge list data (e.g., line_items, codes).
        
        Args:
            template_list: Schema template for list items
            data_list: Extracted list data
        
        Returns:
            Merged list
        """
        if not template_list:
            # Empty template list, return data as-is
            return data_list
        
        # Get template for list items (first item in template)
        item_template = template_list[0]
        
        if not isinstance(item_template, dict):
            # Simple list, return data as-is
            return data_list
        
        # Merge each data item with template
        result = []
        for data_item in data_list:
            if isinstance(data_item, dict):
                merged_item = self._merge_data(item_template, data_item)
                result.append(merged_item)
            else:
                # Invalid item type, skip
                logger.warning(f"Skipping invalid list item: {data_item}")
        
        return result
    
    def _validate_value(self, value: Any, template_value: Any) -> Any:
        """
        Validate and convert value to match template type.
        
        Args:
            value: Value to validate
            template_value: Template value (determines expected type)
        
        Returns:
            Validated value or default
        """
        # Null values are always valid
        if value is None:
            return None
        
        # Get expected type from template
        if template_value is None:
            # Template is null, accept any type but prefer null for numbers
            return value
        
        elif isinstance(template_value, str):
            # Expect string
            if isinstance(value, str):
                return value
            else:
                # Convert to string
                return str(value) if value not in [None, ""] else ""
        
        elif isinstance(template_value, bool):
            # Expect boolean
            if isinstance(value, bool):
                return value
            else:
                return False
        
        elif isinstance(template_value, (int, float)):
            # Expect number
            if isinstance(value, (int, float)):
                return value
            else:
                return None
        
        else:
            # Unknown type, return value as-is
            return value
    
    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """
        Validate that data structure matches schema.
        
        Args:
            data: Data to validate
        
        Returns:
            True if valid, False otherwise
        """
        return self._compare_keys(data, self.schema)
    
    def _compare_keys(
        self, 
        data: Dict[str, Any], 
        schema: Dict[str, Any]
    ) -> bool:
        """
        Compare keys between data and schema.
        
        Args:
            data: Data dict
            schema: Schema dict
        
        Returns:
            True if all schema keys present in data
        """
        for key in schema.keys():
            if key not in data:
                logger.warning(f"Missing key in data: {key}")
                return False
            
            schema_value = schema[key]
            data_value = data[key]
            
            # Recursively check nested dicts
            if isinstance(schema_value, dict) and not isinstance(schema_value, list):
                if isinstance(data_value, dict):
                    if not self._compare_keys(data_value, schema_value):
                        return False
        
        return True
    
    def ensure_required_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure required fields have values.
        If missing, try to extract from alternative locations.
        
        Args:
            data: Invoice data
        
        Returns:
            Invoice data with required fields filled
        """
        # Invoice number (critical)
        if not self._get_nested_value(data, ["header", "invoice_details", "invoice_number"]):
            # Try alternative location
            alt_value = data.get("invoice_details", {}).get("invoice_number", "")
            if alt_value:
                self._set_nested_value(
                    data, 
                    ["header", "invoice_details", "invoice_number"], 
                    alt_value
                )
        
        # Invoice date (critical)
        if not self._get_nested_value(data, ["header", "invoice_details", "invoice_date"]):
            alt_value = data.get("invoice_details", {}).get("invoice_date", "")
            if alt_value:
                self._set_nested_value(
                    data, 
                    ["header", "invoice_details", "invoice_date"], 
                    alt_value
                )
        
        # Total amount (critical)
        if not self._get_nested_value(data, ["summary", "total_amount"]):
            # Try footer totals
            alt_value = self._get_nested_value(
                data, 
                ["footer", "totals_summary", "total_incl_vat_aed"]
            )
            if alt_value:
                self._set_nested_value(data, ["summary", "total_amount"], alt_value)
        
        return data
    
    def _get_nested_value(self, data: Dict[str, Any], path: List[str]) -> Any:
        """Get value from nested dict using path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def _set_nested_value(
        self, 
        data: Dict[str, Any], 
        path: List[str], 
        value: Any
    ) -> None:
        """Set value in nested dict using path."""
        current = data
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def add_metadata(
        self, 
        data: Dict[str, Any], 
        meta_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add processing metadata to result.
        
        Args:
            data: Invoice data
            meta_info: Metadata dict (ocr_pages, gemini_status, processing_time, etc.)
        
        Returns:
            Invoice data with metadata
        """
        result = deepcopy(data)
        result["_meta"] = meta_info
        return result
    
    def remove_extra_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove any fields not in schema (except _meta).
        
        Args:
            data: Invoice data
        
        Returns:
            Cleaned invoice data
        """
        result = self._filter_keys(data, self.schema)
        
        # Preserve metadata if present
        if "_meta" in data:
            result["_meta"] = data["_meta"]
        
        return result
    
    def _filter_keys(
        self, 
        data: Dict[str, Any], 
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter data to only include keys from schema.
        
        Args:
            data: Data dict
            schema: Schema dict
        
        Returns:
            Filtered dict
        """
        result = {}
        
        for key in schema.keys():
            if key in data:
                schema_value = schema[key]
                data_value = data[key]
                
                # Recursively filter nested dicts
                if isinstance(schema_value, dict) and isinstance(data_value, dict):
                    result[key] = self._filter_keys(data_value, schema_value)
                else:
                    result[key] = data_value
            else:
                # Key not in data, use default from schema
                result[key] = schema[key]
        
        return result
