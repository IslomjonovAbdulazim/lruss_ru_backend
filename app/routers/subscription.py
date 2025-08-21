from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
import re

from app.database import get_db
from app.models import User, UserSubscription, BusinessProfile
from app.schemas import (
    UserSubscriptionCreate, UserSubscriptionUpdate, UserSubscription as UserSubscriptionSchema,
    SubscriptionStatus, FinancialStats, BusinessProfile as BusinessProfileSchema,
    BusinessProfileUpdate
)
from app.dependencies import get_admin_user, get_current_user

router = APIRouter()


def version_compare(version1: str, version2: str) -> int:
    """
    Compare two version strings
    Returns: 1 if version1 > version2, 0 if equal, -1 if version1 < version2
    """

    def normalize_version(v):
        # Remove 'v' prefix if exists and split by dots
        clean_v = re.sub(r'^v', '', v.lower())
        parts = clean_v.split('.')
        # Convert to integers, pad with zeros if needed
        normalized = []
        for part in parts:
            try:
                normalized.append(int(part))
            except ValueError:
                normalized.append(0)
        return normalized

    v1_parts = normalize_version(version1)
    v2_parts = normalize_version(version2)

    # Pad shorter version with zeros
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for i in range(max_len):
        if v1_parts[i] > v2_parts[i]:
            return 1
        elif v1_parts[i] < v2_parts[i]:
            return -1

    return 0


async def get_business_profile(db: AsyncSession) -> BusinessProfile:
    """Get business profile, create default if doesn't exist"""
    result = await db.execute(select(BusinessProfile))
    profile = result.scalar_one_or_none()

    if not profile:
        # Create default profile
        profile = BusinessProfile(
            required_app_version="1.0.0",
            company_name="Educational Platform"
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


@router.get("/check", response_model=SubscriptionStatus)
async def check_subscription(
        app_version: str = Query(..., description="Current app version (e.g., 1.2.3)"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Check user's premium subscription status with app version logic
    - If app version >= required version: Return mock 24h premium
    - If app version < required version: Check real subscription
    """

    # Get business profile to check required version
    profile = await get_business_profile(db)
    required_version = profile.required_app_version

    # Compare app versions
    version_comparison = version_compare(app_version, required_version)

    if version_comparison >= 0:
        # User has newer/equal version -> give mock premium (24 hours)
        now = datetime.utcnow()
        mock_end_date = now + timedelta(hours=24)

        return SubscriptionStatus(
            has_premium=True,
            subscription={
                "start_date": now.isoformat(),
                "end_date": mock_end_date.isoformat(),
                "is_mock": True,
                "days_remaining": 1,
                "reason": f"App version {app_version} eligible for premium access"
            },
            message="Premium access granted for updated app version"
        )

    else:
        # User has older version -> check real subscription
        now = datetime.utcnow()
        result = await db.execute(
            select(UserSubscription)
            .where(
                and_(
                    UserSubscription.user_id == current_user.id,
                    UserSubscription.is_active == True,
                    UserSubscription.end_date > now
                )
            )
            .order_by(UserSubscription.end_date.desc())
        )
        active_sub = result.scalar_one_or_none()

        if active_sub:
            days_remaining = (active_sub.end_date - now).days
            return SubscriptionStatus(
                has_premium=True,
                subscription={
                    "start_date": active_sub.start_date.isoformat(),
                    "end_date": active_sub.end_date.isoformat(),
                    "is_mock": False,
                    "days_remaining": max(0, days_remaining),
                    "amount_paid": active_sub.amount,
                    "currency": active_sub.currency
                },
                message="Active premium subscription"
            )
        else:
            return SubscriptionStatus(
                has_premium=False,
                subscription=None,
                message="No active premium subscription"
            )


@router.get("/admin/subscriptions", response_model=List[UserSubscriptionSchema])
async def get_subscriptions(
        admin_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        user_id: Optional[int] = Query(None),
        active_only: bool = Query(False)
):
    """Get all subscriptions with optional filters (admin only)"""

    query = select(UserSubscription).order_by(UserSubscription.created_at.desc())

    # Apply filters
    if user_id:
        query = query.where(UserSubscription.user_id == user_id)

    if active_only:
        now = datetime.utcnow()
        query = query.where(
            and_(
                UserSubscription.is_active == True,
                UserSubscription.end_date > now
            )
        )

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    subscriptions = result.scalars().all()

    return subscriptions


@router.get("/admin/financial", response_model=FinancialStats)
async def get_financial_stats(
        admin_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """Get comprehensive financial statistics (admin only)"""

    now = datetime.utcnow()

    # Total revenue (all time)
    total_revenue_result = await db.scalar(
        select(func.sum(UserSubscription.amount))
        .where(UserSubscription.is_active == True)
    )
    total_revenue = float(total_revenue_result or 0)

    # Monthly revenue (current month)
    current_month = now.month
    current_year = now.year
    monthly_revenue_result = await db.scalar(
        select(func.sum(UserSubscription.amount))
        .where(
            and_(
                UserSubscription.is_active == True,
                extract('month', UserSubscription.created_at) == current_month,
                extract('year', UserSubscription.created_at) == current_year
            )
        )
    )
    monthly_revenue = float(monthly_revenue_result or 0)

    # Yearly revenue (current year)
    yearly_revenue_result = await db.scalar(
        select(func.sum(UserSubscription.amount))
        .where(
            and_(
                UserSubscription.is_active == True,
                extract('year', UserSubscription.created_at) == current_year
            )
        )
    )
    yearly_revenue = float(yearly_revenue_result or 0)

    # Active subscriptions count
    active_subs_count = await db.scalar(
        select(func.count(UserSubscription.id))
        .where(
            and_(
                UserSubscription.is_active == True,
                UserSubscription.end_date > now
            )
        )
    )
    active_subscriptions = int(active_subs_count or 0)

    # Total paid subscriptions count
    total_subs_count = await db.scalar(
        select(func.count(UserSubscription.id))
        .where(UserSubscription.is_active == True)
    )
    total_paid_subscriptions = int(total_subs_count or 0)

    # Average subscription value
    average_value = total_revenue / total_paid_subscriptions if total_paid_subscriptions > 0 else 0

    # Revenue by month (last 12 months)
    revenue_by_month = []
    for i in range(12):
        target_date = now - timedelta(days=30 * i)
        target_month = target_date.month
        target_year = target_date.year

        month_revenue_result = await db.scalar(
            select(func.sum(UserSubscription.amount))
            .where(
                and_(
                    UserSubscription.is_active == True,
                    extract('month', UserSubscription.created_at) == target_month,
                    extract('year', UserSubscription.created_at) == target_year
                )
            )
        )

        month_count_result = await db.scalar(
            select(func.count(UserSubscription.id))
            .where(
                and_(
                    UserSubscription.is_active == True,
                    extract('month', UserSubscription.created_at) == target_month,
                    extract('year', UserSubscription.created_at) == target_year
                )
            )
        )

        revenue_by_month.insert(0, {
            "month": f"{target_year}-{target_month:02d}",
            "revenue": float(month_revenue_result or 0),
            "count": int(month_count_result or 0)
        })

    return FinancialStats(
        total_revenue=total_revenue,
        monthly_revenue=monthly_revenue,
        yearly_revenue=yearly_revenue,
        active_subscriptions=active_subscriptions,
        total_paid_subscriptions=total_paid_subscriptions,
        average_subscription_value=round(average_value, 2),
        revenue_by_month=revenue_by_month
    )


@router.get("/admin/business", response_model=BusinessProfileSchema)
async def get_business_profile_endpoint(
        admin_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """Get business profile (admin only)"""
    profile = await get_business_profile(db)
    return profile


@router.put("/admin/business", response_model=BusinessProfileSchema)
async def update_business_profile(
        profile_update: BusinessProfileUpdate,
        admin_user: User = Depends(get_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """Update business profile (admin only)"""

    profile = await get_business_profile(db)
    update_data = profile_update.dict(exclude_unset=True)

    # Validate version format if provided
    if "required_app_version" in update_data:
        version = update_data["required_app_version"]
        if not re.match(r'^\d+(\.\d+)*$', version):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid version format. Use format like '1.0.0'"
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return profile