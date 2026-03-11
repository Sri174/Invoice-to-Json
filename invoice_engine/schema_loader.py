"""
schema_loader.py
----------------
Loads and manages the constant universal invoice schema.
The schema is the immutable contract for all invoice extraction outputs.
"""

import json
import os
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# Path to the universal schema JSON file
SCHEMA_FILE = "universal_schema.json"


class SchemaLoader:
    """
    Loads and provides access to the constant universal invoice schema.
    """
    
    def __init__(self, schema_path: str = None):
        """
        Initialize schema loader.
        
        Args:
            schema_path: Optional custom path to schema file.
                        If None, looks for universal_schema.json in invoice_engine directory.
        """
        if schema_path:
            self.schema_path = schema_path
        else:
            # Default to invoice_engine/universal_schema.json
            current_dir = Path(__file__).parent
            self.schema_path = current_dir / SCHEMA_FILE
        
        self._schema = None
        self._load_schema()
        
        logger.info(f"SchemaLoader initialized with schema from: {self.schema_path}")
    
    def _load_schema(self) -> None:
        """
        Load the schema from JSON file.
        
        Raises:
            FileNotFoundError: If schema file not found
            json.JSONDecodeError: If schema file is invalid JSON
        """
        try:
            if not os.path.exists(self.schema_path):
                raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
            
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._schema = json.load(f)
            
            logger.info("Universal schema loaded successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema file: {str(e)}")
            raise
        
        except Exception as e:
            logger.error(f"Failed to load schema: {str(e)}")
            raise
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the constant invoice schema.
        
        Returns:
            Deep copy of the universal schema dict
        """
        if self._schema is None:
            self._load_schema()
        
        # Return a deep copy to prevent modifications
        return json.loads(json.dumps(self._schema))
    
    def get_empty_invoice(self) -> Dict[str, Any]:
        """
        Get an empty invoice structure with default values.
        All fields are present but empty.
        
        Returns:
            Empty invoice dict matching schema
        """
        return self.get_schema()
    
    def validate_schema_structure(self, data: Dict[str, Any]) -> bool:
        """
        Validate that data matches the schema structure.
        Checks for presence of all required fields.
        
        Args:
            data: Invoice data to validate
        
        Returns:
            True if structure is valid, False otherwise
        """
        try:
            schema = self.get_schema()
            return self._compare_structures(data, schema)
        except Exception as e:
            logger.error(f"Schema validation error: {str(e)}")
            return False
    
    def _compare_structures(
        self, 
        data: Dict[str, Any], 
        schema: Dict[str, Any],
        path: str = ""
    ) -> bool:
        """
        Recursively compare data structure with schema.
        
        Args:
            data: Data to validate
            schema: Schema to validate against
            path: Current path in structure (for logging)
        
        Returns:
            True if structures match
        """
        # Check all schema keys exist in data
        for key in schema.keys():
            if key not in data:
                logger.warning(f"Missing key in data: {path}.{key}")
                return False
            
            schema_value = schema[key]
            data_value = data[key]
            
            # If schema value is a dict, recurse
            if isinstance(schema_value, dict) and not isinstance(schema_value, list):
                if not isinstance(data_value, dict):
                    logger.warning(f"Type mismatch at {path}.{key}: expected dict")
                    return False
                
                if not self._compare_structures(data_value, schema_value, f"{path}.{key}"):
                    return False
            
            # If schema value is a list with dict template, validate list items
            elif isinstance(schema_value, list) and len(schema_value) > 0:
                if not isinstance(data_value, list):
                    logger.warning(f"Type mismatch at {path}.{key}: expected list")
                    return False
                
                # Validate each item in data list against first schema item (template)
                template = schema_value[0]
                if isinstance(template, dict):
                    for i, item in enumerate(data_value):
                        if not isinstance(item, dict):
                            logger.warning(f"List item type mismatch at {path}.{key}[{i}]")
                            return False
                        
                        if not self._compare_structures(item, template, f"{path}.{key}[{i}]"):
                            return False
        
        return True
    
    def get_schema_fields(self) -> list:
        """
        Get list of all top-level fields in schema.
        
        Returns:
            List of field names
        """
        schema = self.get_schema()
        return list(schema.keys())
    
    def get_required_fields(self) -> list:
        """
        Get list of critical fields that should always be populated.
        
        Returns:
            List of (path, field_name) tuples for required fields
        """
        return [
            ("header.invoice_details", "invoice_number"),
            ("header.invoice_details", "invoice_date"),
            ("summary", "total_amount"),
            ("line_items", "*"),  # At least one line item
        ]
    
    def reload_schema(self) -> None:
        """
        Reload schema from file.
        Useful if schema file is updated during runtime.
        """
        logger.info("Reloading schema from file")
        self._load_schema()


# Singleton instance for easy access
_global_schema_loader = None


def get_schema_loader() -> SchemaLoader:
    """
    Get global schema loader instance (singleton pattern).
    
    Returns:
        SchemaLoader instance
    """
    global _global_schema_loader
    
    if _global_schema_loader is None:
        _global_schema_loader = SchemaLoader()
    
    return _global_schema_loader


def get_universal_schema() -> Dict[str, Any]:
    """
    Quick access function to get the universal schema.
    
    Returns:
        Universal invoice schema dict
    """
    loader = get_schema_loader()
    return loader.get_schema()
