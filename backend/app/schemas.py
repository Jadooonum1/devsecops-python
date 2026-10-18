import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ISBN_RE = re.compile(r"^(97[89])?\d{9}[\dX]$")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BookIn(BaseModel):
    isbn: str = Field(min_length=10, max_length=17)
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=120)
    genre: str | None = Field(default=None, max_length=60)
    published_year: int | None = Field(default=None, ge=1400, le=2100)

    @field_validator("isbn")
    @classmethod
    def normalise_isbn(cls, v: str) -> str:
        digits = v.replace("-", "").replace(" ", "").upper()
        if not ISBN_RE.match(digits):
            raise ValueError("isbn must be a 10 or 13 digit ISBN")
        return digits

    @field_validator("title", "author")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class BookOut(ORM):
    id: int
    isbn: str
    title: str
    author: str
    genre: str | None
    published_year: int | None
    created_at: datetime
    total_copies: int = 0
    available_copies: int = 0


class CopyIn(BaseModel):
    barcode: str = Field(min_length=3, max_length=32, pattern=r"^[A-Z0-9-]+$")
    shelf: str | None = Field(default=None, max_length=20)


class CopyStatusIn(BaseModel):
    status: str = Field(pattern=r"^(available|maintenance)$")


class CopyOut(ORM):
    id: int
    book_id: int
    barcode: str
    shelf: str | None
    status: str
    book_title: str | None = None


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    max_loans: int = Field(default=3, ge=1, le=10)


class MemberOut(ORM):
    id: int
    name: str
    email: str
    max_loans: int
    created_at: datetime
    active_loans: int = 0
    unpaid_fines: int = 0


class LoanIn(BaseModel):
    copy_id: int = Field(gt=0)
    member_id: int = Field(gt=0)
    days: int | None = Field(default=None, ge=1, le=60)


class LoanOut(ORM):
    id: int
    copy_id: int
    member_id: int
    status: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None
    renewals: int
    fine: int
    fine_paid: bool
    overdue: bool = False
    days_overdue: int = 0
    book_title: str | None = None
    barcode: str | None = None
    member_name: str | None = None


class AuditOut(ORM):
    id: int
    entity: str
    entity_id: int
    action: str
    detail: str | None
    created_at: datetime
