import asyncio
import json
import time
from typing import Optional
from datetime import datetime

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Proxy
from ..schemas import (
    ProxyResponse,
    ProxyListResponse,
    ProxyStats,
    RefreshResponse,
    BulkValidationRequest,
    ValidationResult,
    SingleValidationResponse,
    ValidationProgress,
    BrowseRequest,
    BrowseResponse,
)
from ..services.fetcher import ProxyFetcher
from ..services.validator import ProxyValidator

router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("", response_model=ProxyListResponse)
async def list_proxies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    protocol: Optional[str] = Query(None, pattern="^(http|https|socks4|socks5)$"),
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    anonymity: Optional[str] = Query(None, pattern="^(transparent|anonymous|elite)$"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    is_active: Optional[bool] = Query(True),
    sort_by: str = Query("score", pattern="^(score|speed|last_check|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of proxies with filters."""
    # Build query
    query = select(Proxy)

    # Apply filters
    if protocol:
        query = query.where(Proxy.protocol == protocol)
    if country:
        query = query.where(Proxy.country == country.upper())
    if anonymity:
        query = query.where(Proxy.anonymity == anonymity)
    if min_score is not None:
        query = query.where(Proxy.score >= min_score)
    if is_active is not None:
        query = query.where(Proxy.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Proxy, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    proxies = result.scalars().all()

    return ProxyListResponse(
        items=[ProxyResponse.model_validate(p) for p in proxies],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/best", response_model=list[ProxyResponse])
async def get_best_proxies(
    limit: int = Query(10, ge=1, le=50),
    protocol: Optional[str] = Query(None, pattern="^(http|https|socks4|socks5)$"),
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
):
    """Get the best proxies by score."""
    query = select(Proxy).where(Proxy.is_active == True)

    if protocol:
        query = query.where(Proxy.protocol == protocol)
    if country:
        query = query.where(Proxy.country == country.upper())

    query = query.order_by(desc(Proxy.score)).limit(limit)

    result = await db.execute(query)
    proxies = result.scalars().all()

    return [ProxyResponse.model_validate(p) for p in proxies]


@router.get("/by-country/{country_code}", response_model=list[ProxyResponse])
async def get_proxies_by_country(
    country_code: str,
    limit: int = Query(50, ge=1, le=200),
    protocol: Optional[str] = Query(None, pattern="^(http|https|socks4|socks5)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get proxies for a specific country."""
    query = select(Proxy).where(
        Proxy.country == country_code.upper(),
        Proxy.is_active == True,
    )

    if protocol:
        query = query.where(Proxy.protocol == protocol)

    query = query.order_by(desc(Proxy.score)).limit(limit)

    result = await db.execute(query)
    proxies = result.scalars().all()

    return [ProxyResponse.model_validate(p) for p in proxies]


@router.get("/stats", response_model=ProxyStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get proxy statistics."""
    # Total counts
    total_result = await db.execute(select(func.count(Proxy.id)))
    total = total_result.scalar() or 0

    active_result = await db.execute(
        select(func.count(Proxy.id)).where(Proxy.is_active == True)
    )
    active = active_result.scalar() or 0

    # By protocol (only active proxies)
    protocol_result = await db.execute(
        select(Proxy.protocol, func.count(Proxy.id))
        .where(Proxy.is_active == True)
        .group_by(Proxy.protocol)
    )
    by_protocol = {row[0]: row[1] for row in protocol_result.fetchall()}

    # By country (top 20, only active)
    country_result = await db.execute(
        select(Proxy.country, func.count(Proxy.id))
        .where(Proxy.country.isnot(None), Proxy.is_active == True)
        .group_by(Proxy.country)
        .order_by(desc(func.count(Proxy.id)))
        .limit(20)
    )
    by_country = {row[0]: row[1] for row in country_result.fetchall()}

    # By anonymity (only active)
    anonymity_result = await db.execute(
        select(Proxy.anonymity, func.count(Proxy.id))
        .where(Proxy.anonymity.isnot(None), Proxy.is_active == True)
        .group_by(Proxy.anonymity)
    )
    by_anonymity = {row[0]: row[1] for row in anonymity_result.fetchall()}

    # Average metrics (only active with speed data)
    avg_speed_result = await db.execute(
        select(func.avg(Proxy.speed)).where(
            Proxy.speed.isnot(None),
            Proxy.is_active == True
        )
    )
    average_speed = avg_speed_result.scalar()

    avg_score_result = await db.execute(
        select(func.avg(Proxy.score)).where(Proxy.is_active == True)
    )
    average_score = avg_score_result.scalar() or 0

    return ProxyStats(
        total=total,
        active=active,
        inactive=total - active,
        by_protocol=by_protocol,
        by_country=by_country,
        by_anonymity=by_anonymity,
        average_speed=round(average_speed, 2) if average_speed else None,
        average_score=round(average_score, 2),
    )


@router.get("/{proxy_id}", response_model=ProxyResponse)
async def get_proxy(proxy_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single proxy by ID."""
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    return ProxyResponse.model_validate(proxy)


@router.post("/{proxy_id}/validate", response_model=SingleValidationResponse)
async def validate_single_proxy(
    proxy_id: int,
    quick: bool = Query(False, description="Use quick validation mode"),
    db: AsyncSession = Depends(get_db),
):
    """Validate a single proxy and return detailed results."""
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    validator = ProxyValidator()
    results = await validator.validate_and_update(db, [proxy], quick=quick)

    if not results:
        raise HTTPException(status_code=500, detail="Validation failed")

    validation_result = results[0]

    # Refresh proxy data after validation
    await db.refresh(proxy)

    return SingleValidationResponse(
        proxy_id=validation_result.proxy_id,
        is_valid=validation_result.is_valid,
        speed=validation_result.speed,
        anonymity=validation_result.anonymity,
        error=validation_result.error,
        test_url=validation_result.test_url,
        response_ip=validation_result.response_ip,
        proxy=ProxyResponse.model_validate(proxy),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_proxies(
    background_tasks: BackgroundTasks,
    protocol: Optional[str] = Query(None, pattern="^(http|https|socks4|socks5)$"),
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
):
    """Fetch new proxies from all sources."""
    fetcher = ProxyFetcher()
    new_count, total_fetched = await fetcher.refresh_proxies(
        db, protocol=protocol, country=country
    )

    # Get total count in database
    total_result = await db.execute(select(func.count(Proxy.id)))
    total_in_db = total_result.scalar() or 0

    return RefreshResponse(
        message=f"Fetched {total_fetched} proxies, added {new_count} new ones",
        new_proxies=new_count,
        total_proxies=total_in_db,
    )


@router.post("/validate", response_model=list[ValidationResult])
async def validate_proxies(
    request: BulkValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate proxies."""
    # Build query for proxies to validate
    query = select(Proxy)

    if request.proxy_ids:
        query = query.where(Proxy.id.in_(request.proxy_ids))
    elif not request.validate_all:
        # By default, validate active proxies that haven't been checked recently
        query = query.where(Proxy.is_active == True)

    # Apply limit only if > 0
    if request.limit > 0:
        query = query.limit(request.limit)

    result = await db.execute(query)
    proxies = result.scalars().all()

    if not proxies:
        return []

    validator = ProxyValidator()
    results = await validator.validate_and_update(db, list(proxies), quick=request.quick)

    return [
        ValidationResult(
            proxy_id=r.proxy_id,
            is_valid=r.is_valid,
            speed=r.speed,
            anonymity=r.anonymity,
            error=r.error,
        )
        for r in results
    ]


@router.post("/validate/stream")
async def validate_proxies_stream(
    request: BulkValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate proxies with streaming progress updates (SSE)."""
    # Build query for proxies to validate
    query = select(Proxy)

    if request.proxy_ids:
        query = query.where(Proxy.id.in_(request.proxy_ids))
    elif not request.validate_all:
        query = query.where(Proxy.is_active == True)

    # Apply limit only if > 0
    if request.limit > 0:
        query = query.limit(request.limit)

    result = await db.execute(query)
    proxies = list(result.scalars().all())

    if not proxies:
        async def empty_stream():
            yield f"data: {json.dumps({'total': 0, 'completed': 0, 'successful': 0, 'failed': 0, 'percent': 100, 'done': True})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    validator = ProxyValidator()

    async def progress_stream():
        try:
            async for progress in validator.validate_and_update_with_progress(db, proxies, quick=request.quick):
                # Build progress data
                data = {
                    "total": progress.total,
                    "completed": progress.completed,
                    "successful": progress.successful,
                    "failed": progress.failed,
                    "percent": round(progress.percent, 1),
                    "current_proxy": progress.current_proxy,
                    "done": False,
                }

                # Include latest result if available
                if progress.results:
                    latest = progress.results[0]
                    data["latest_result"] = {
                        "proxy_id": latest.proxy_id,
                        "is_valid": latest.is_valid,
                        "speed": latest.speed,
                        "error": latest.error,
                    }

                yield f"data: {json.dumps(data)}\n\n"

            # Send completion message
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a proxy."""
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    await db.delete(proxy)
    await db.commit()

    return {"message": "Proxy deleted"}


@router.delete("")
async def delete_inactive_proxies(db: AsyncSession = Depends(get_db)):
    """Delete all inactive proxies."""
    result = await db.execute(
        select(Proxy).where(Proxy.is_active == False)
    )
    proxies = result.scalars().all()

    count = len(proxies)
    for proxy in proxies:
        await db.delete(proxy)

    await db.commit()

    return {"message": f"Deleted {count} inactive proxies"}


@router.post("/{proxy_id}/browse", response_model=BrowseResponse)
async def browse_through_proxy(
    proxy_id: int,
    request: BrowseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Browse a URL through the specified proxy."""
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    proxy = result.scalar_one_or_none()

    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")

    proxy_address = f"{proxy.ip}:{proxy.port}"
    timeout = aiohttp.ClientTimeout(total=request.timeout)
    start_time = time.time()
    is_https = request.url.lower().startswith("https://")

    try:
        # Create appropriate session based on protocol
        if proxy.protocol in ("socks4", "socks5"):
            proxy_type = ProxyType.SOCKS5 if proxy.protocol == "socks5" else ProxyType.SOCKS4
            connector = ProxyConnector(
                proxy_type=proxy_type,
                host=proxy.ip,
                port=proxy.port,
                rdns=True,
            )
            session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            proxy_url = None
        else:
            session = aiohttp.ClientSession(timeout=timeout)
            proxy_url = f"http://{proxy.ip}:{proxy.port}"

        try:
            # For HTTPS URLs through HTTP proxy, we need ssl verification disabled
            # but the proxy must support CONNECT method
            async with session.get(request.url, proxy=proxy_url, ssl=False) as response:
                elapsed = (time.time() - start_time) * 1000

                # Read content (limit to 1MB)
                content = await response.text(errors='replace')
                if len(content) > 1024 * 1024:
                    content = content[:1024 * 1024] + "\n... [Content truncated]"

                # Get headers as dict
                headers = dict(response.headers)

                return BrowseResponse(
                    success=True,
                    url=str(response.url),
                    status_code=response.status,
                    content_type=response.content_type,
                    content=content,
                    headers=headers,
                    elapsed_ms=round(elapsed, 2),
                    proxy_address=proxy_address,
                )
        finally:
            await session.close()

    except aiohttp.ClientHttpProxyError as e:
        # HTTP proxy errors - often means proxy doesn't support HTTPS/CONNECT
        error_msg = "Proxy connection error"
        if is_https and proxy.protocol in ("http", "https"):
            error_msg = "HTTP proxy does not support HTTPS (CONNECT method). Try using HTTP URLs or a SOCKS proxy."
        return BrowseResponse(
            success=False,
            url=request.url,
            error=error_msg,
            proxy_address=proxy_address,
        )
    except aiohttp.ClientProxyConnectionError:
        return BrowseResponse(
            success=False,
            url=request.url,
            error="Cannot connect to proxy. The proxy may be offline or blocking connections.",
            proxy_address=proxy_address,
        )
    except aiohttp.ClientConnectorError:
        return BrowseResponse(
            success=False,
            url=request.url,
            error="Connection failed. Check if the target URL is accessible.",
            proxy_address=proxy_address,
        )
    except asyncio.TimeoutError:
        return BrowseResponse(
            success=False,
            url=request.url,
            error=f"Request timed out after {request.timeout} seconds.",
            proxy_address=proxy_address,
        )
    except aiohttp.ClientError as e:
        return BrowseResponse(
            success=False,
            url=request.url,
            error=f"Request failed: {type(e).__name__}",
            proxy_address=proxy_address,
        )
    except Exception as e:
        return BrowseResponse(
            success=False,
            url=request.url,
            error=str(e)[:200],
            proxy_address=proxy_address,
        )
