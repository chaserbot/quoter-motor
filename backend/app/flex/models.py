from pydantic import BaseModel
from typing import Optional, Any


class FlexDocument(BaseModel):
    id: str
    documentNumber: Optional[str] = None
    description: Optional[str] = None
    subDocumentTypeId: Optional[str] = None
    clientId: Optional[str] = None
    clientName: Optional[str] = None
    startDateTime: Optional[str] = None
    endDateTime: Optional[str] = None
    totalPrice: Optional[float] = None
    raw: Optional[dict[str, Any]] = None


class FlexDocumentElement(BaseModel):
    """A single line item on a Flex document (equipment or labor)."""
    id: str
    parentId: Optional[str] = None
    elementId: Optional[str] = None
    elementName: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unitPrice: Optional[float] = None
    totalPrice: Optional[float] = None
    elementTypeId: Optional[str] = None
    elementTypeName: Optional[str] = None
    sortOrder: Optional[int] = None
    raw: Optional[dict[str, Any]] = None


class FlexElement(BaseModel):
    """An inventory item in Flex (the catalog)."""
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    elementTypeId: Optional[str] = None
    elementTypeName: Optional[str] = None
    categoryId: Optional[str] = None
    categoryName: Optional[str] = None
    defaultPrice: Optional[float] = None
    active: Optional[bool] = True
    raw: Optional[dict[str, Any]] = None


class FlexClient_Auth(BaseModel):
    token: str
    userId: Optional[str] = None
