# app/schemas/base_schema.py
from pydantic import BaseModel, Field


class IDCardSchema(BaseModel):
    full_name: str = Field(..., description="The name on the ID card")
    id_number: str = Field(..., description="Unique identification number")
    date_of_birth: str = Field(..., description="DOB in DD/MM/YYYY format")
    expiry_date: str = Field(..., description="Card expiry date")
