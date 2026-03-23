from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Proxy(Base):
    """Proxy database model."""

    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String(45), nullable=False)  # Support IPv6
    port = Column(Integer, nullable=False)
    protocol = Column(String(10), nullable=False)  # http/https/socks4/socks5
    country = Column(String(2), nullable=True)  # ISO country code
    country_name = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    anonymity = Column(String(20), nullable=True)  # transparent/anonymous/elite
    speed = Column(Float, nullable=True)  # milliseconds
    score = Column(Float, default=0.0)  # 0-100
    last_check = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def address(self) -> str:
        """Get proxy address as ip:port."""
        return f"{self.ip}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate from history."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100

    def __repr__(self) -> str:
        return f"<Proxy {self.protocol}://{self.ip}:{self.port}>"
