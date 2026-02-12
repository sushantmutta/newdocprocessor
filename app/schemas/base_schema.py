# app/schemas/base_schema.py
from pydantic import BaseModel, Field
from typing import Optional
import re
from datetime import datetime


class BaseDocumentSchema(BaseModel):
    """
    Base schema for all document types.
    Provides common fields, configuration, and utility methods.
    """
    
    class Config:
        # Forbid extra fields to ensure strict validation
        extra = "forbid"
        # Validate on assignment
        validate_assignment = True
        # Use enum values
        use_enum_values = True
    
    @staticmethod
    def parse_date(value: str) -> str:
        """
        Parse various date formats and normalize to ISO format (YYYY-MM-DD).
        
        Supported formats:
        - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        - YYYY-MM-DD, YYYY/MM/DD
        - MM/DD/YYYY, MM-DD-YYYY
        
        Args:
            value: Date string in various formats
            
        Returns:
            ISO formatted date string (YYYY-MM-DD)
            
        Raises:
            ValueError: If date format is not recognized
        """
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        
        if not isinstance(value, str):
            return str(value)
        
        value = value.strip()
        
        # Try different date formats
        date_formats = [
            "%Y-%m-%d",      # ISO format
            "%d/%m/%Y",      # DD/MM/YYYY
            "%d-%m-%Y",      # DD-MM-YYYY
            "%d.%m.%Y",      # DD.MM.YYYY
            "%Y/%m/%d",      # YYYY/MM/DD
            "%d %b %Y",      # DD Mon YYYY
            "%d %B %Y",      # DD Month YYYY
            "%b %d, %Y",     # Mon DD, YYYY
            "%B %d, %Y",     # Month DD, YYYY
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(value, fmt)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # If no format matched, return as-is (will fail validation later)
        return value
    
    @staticmethod
    def parse_currency(value) -> float:
        """
        Parse various currency formats and convert to float.
        
        Supported formats:
        - US: $8,028.26, 8,028.26
        - European: 8.028,26 €, 8.028,26
        - Indian: ₹8,02,826.00, Rs. 8,02,826, 8,02,826.00 (lakhs/crores notation)
        - Plain: 8028.26
        - Negative: -$1,000.00, ($1,000.00)
        
        Args:
            value: Currency value as string or number
            
        Returns:
            Float value
            
        Raises:
            ValueError: If value cannot be parsed
        """
        if isinstance(value, (int, float)):
            return float(value)
        
        if not isinstance(value, str):
            value = str(value)
        
        # Store original for error messages
        original_value = value
        value = value.strip()
        
        # Check for negative sign FIRST (before removing symbols)
        is_negative = False
        if value.startswith('-'):
            is_negative = True
            value = value[1:].strip()
        
        # Handle negative amounts in parentheses: ($1,000.00) -> -1000.00
        if value.startswith('(') and value.endswith(')'):
            is_negative = True
            value = value[1:-1].strip()
        
        # Remove currency symbols and spaces
        # Supports: $, €, ₹, Rs, Rs., INR, USD, EUR, etc.
        # First remove "Rs." or "Rs" specifically to avoid issues with the dot
        value = re.sub(r'\bRs\.?\s*', '', value, flags=re.IGNORECASE)
        # Then remove other currency symbols and text
        value = re.sub(r'[₹$€£¥]|INR|USD|EUR|GBP|JPY', '', value, flags=re.IGNORECASE)
        # Remove remaining spaces
        value = value.replace(' ', '')
        
        # Now determine the decimal separator
        # European format: 8.028,26 (comma is decimal)
        # US/Indian format: 8,028.26 (dot is decimal)
        # Indian lakhs: 8,02,826.00 (dot is decimal, commas for grouping)
        
        comma_count = value.count(',')
        dot_count = value.count('.')
        
        if comma_count > 0 and dot_count > 0:
            # Both present - determine which is decimal separator
            last_comma_pos = value.rfind(',')
            last_dot_pos = value.rfind('.')
            
            if last_comma_pos > last_dot_pos:
                # European format: 8.028,26
                value = value.replace('.', '').replace(',', '.')
            else:
                # US/Indian format: 8,028.26 or 8,02,826.00
                value = value.replace(',', '')
        
        elif comma_count > 0:
            # Only commas present
            if comma_count == 1 and len(value.split(',')[1]) == 2:
                # Likely European decimal: 8028,26
                value = value.replace(',', '.')
            else:
                # Likely thousands separator: 8,028 or Indian: 8,02,826
                value = value.replace(',', '')
        
        # At this point, value should be clean number string
        try:
            result = float(value)
            return -result if is_negative else result
        except ValueError:
            raise ValueError(f"Cannot parse currency value: {original_value}")
    
    @staticmethod
    def clean_text(value: str) -> str:
        """
        Clean text by removing extra whitespace and normalizing.
        
        Args:
            value: Text to clean
            
        Returns:
            Cleaned text
        """
        if not isinstance(value, str):
            return str(value)
        
        # Replace multiple spaces with single space
        value = re.sub(r'\s+', ' ', value)
        # Strip leading/trailing whitespace
        return value.strip()
