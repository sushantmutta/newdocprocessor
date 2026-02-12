from pydantic import BaseModel, Field, field_validator
import re


class InvoiceSchema(BaseModel):
    invoice_number: str = Field(...,
                                description="The unique invoice ID (e.g., 60475)")
    vendor_name: str = Field(...,
                             description="The company name (e.g., Morar Inc)")
    total_amount: float = Field(...,
                                description="The final invoice total as a number")
    date: str = Field(..., description="The date of the invoice")

    @field_validator("total_amount", mode="before")
    @classmethod
    def clean_amount(cls, value):
        """
        Cleans strings like '8.028,26 €' or '2.628,40' into a valid float.
        """
        if isinstance(value, str):
            # Remove currency symbols and spaces
            cleaned = re.sub(r'[^\d,.-]', '', value)
            # Handle European format: 8.028,26 -> 8028.26
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace('.', '').replace(',', '.')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        return value
