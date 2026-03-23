from pydantic import BaseModel, Field, computed_field
from datetime import datetime
from typing import Optional


class ProxyBase(BaseModel):
    """Base proxy schema."""
    ip: str
    port: int = Field(ge=1, le=65535)
    protocol: str = Field(pattern="^(http|https|socks4|socks5)$")
    country: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    anonymity: Optional[str] = None


class ProxyCreate(ProxyBase):
    """Schema for creating a proxy."""
    source: Optional[str] = None


class ProxyResponse(ProxyBase):
    """Schema for proxy response."""
    id: int
    speed: Optional[float] = None
    score: float = 0.0
    last_check: Optional[datetime] = None
    success_count: int = 0
    fail_count: int = 0
    is_active: bool = True
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def address(self) -> str:
        """Get proxy address as ip:port."""
        return f"{self.ip}:{self.port}"

    @computed_field
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return round((self.success_count / total) * 100, 2)

    class Config:
        from_attributes = True


class ProxyListResponse(BaseModel):
    """Schema for paginated proxy list."""
    items: list[ProxyResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProxyFilter(BaseModel):
    """Schema for filtering proxies."""
    protocol: Optional[str] = None
    country: Optional[str] = None
    anonymity: Optional[str] = None
    min_speed: Optional[float] = None
    max_speed: Optional[float] = None
    min_score: Optional[float] = None
    is_active: Optional[bool] = True


class ProxyStats(BaseModel):
    """Schema for proxy statistics."""
    total: int
    active: int
    inactive: int
    by_protocol: dict[str, int]
    by_country: dict[str, int]
    by_anonymity: dict[str, int]
    average_speed: Optional[float]
    average_score: float


class ValidationResult(BaseModel):
    """Schema for validation result."""
    proxy_id: int
    is_valid: bool
    speed: Optional[float] = None
    anonymity: Optional[str] = None
    error: Optional[str] = None
    test_url: Optional[str] = None
    response_ip: Optional[str] = None


class SingleValidationResponse(BaseModel):
    """Schema for single proxy validation response."""
    proxy_id: int
    is_valid: bool
    speed: Optional[float] = None
    anonymity: Optional[str] = None
    error: Optional[str] = None
    test_url: Optional[str] = None
    response_ip: Optional[str] = None
    proxy: Optional[ProxyResponse] = None  # Updated proxy data


class RefreshResponse(BaseModel):
    """Schema for refresh response."""
    message: str
    new_proxies: int
    total_proxies: int


class BulkValidationRequest(BaseModel):
    """Schema for bulk validation request."""
    proxy_ids: Optional[list[int]] = None
    validate_all: bool = False
    limit: int = Field(default=100, ge=0)  # 0 means no limit
    quick: bool = Field(default=False, description="Use quick validation mode (faster but less thorough)")


class ValidationProgress(BaseModel):
    """Schema for validation progress update."""
    total: int
    completed: int
    successful: int
    failed: int
    percent: float
    current_proxy: Optional[str] = None
    latest_result: Optional[ValidationResult] = None


class BrowseRequest(BaseModel):
    """Schema for browsing through proxy."""
    url: str
    timeout: int = Field(default=30, ge=5, le=60)


class BrowseResponse(BaseModel):
    """Schema for browse response."""
    success: bool
    url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    elapsed_ms: Optional[float] = None
    error: Optional[str] = None
    proxy_address: str
