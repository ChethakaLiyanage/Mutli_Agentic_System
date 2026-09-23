"""Admin-only customer management and policy assignment endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator.claim_repository import ClaimRepository, get_claim_repository
from backend.app.schemas.admin import (
    AdminCustomerCreateRequest,
    AdminCustomerListResponse,
    AdminCustomerResponse,
    PolicyCategory,
)
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.dependencies import get_current_admin, get_user_repository
from backend.app.security.password import hash_password
from backend.app.security.roles import UserRole
from backend.app.security.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
)
from backend.app.services.repository_errors import RepositoryError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/customers",
    response_model=AdminCustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer account with assigned motor policy category",
)
async def create_customer(
    request: AdminCustomerCreateRequest,
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    claim_repo: Annotated[ClaimRepository, Depends(get_claim_repository)],
) -> AdminCustomerResponse:
    """Create a new customer account with strictly assigned motor-policy category."""
    # Enforce allowed policy category
    if request.policy_type not in (
        PolicyCategory.FULL_COMPREHENSIVE,
        PolicyCategory.PARTIAL_COMPREHENSIVE,
        PolicyCategory.THIRD_PARTY,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported policy category: {request.policy_type}",
        )

    # Hash password with project's existing Argon2id implementation
    password_hash = hash_password(request.password)

    try:
        # Created user must always have role = customer (never trust client)
        user = await user_repo.create_user(
            email=str(request.email),
            password_hash=password_hash,
            role=UserRole.CUSTOMER,
        )
    except UserAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from error
    except RepositoryError as error:
        logger.exception("Admin customer persistence failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create customer account",
        ) from error

    # Create and link assigned motor policy
    try:
        policy = claim_repo.create_customer_policy(
            customer_id=user.user_id,
            policy_type=request.policy_type.value,
            status="active",
        )
    except Exception as error:
        logger.exception("Admin policy assignment failed for %s", user.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Customer created but failed to link motor policy",
        ) from error

    return AdminCustomerResponse(
        user_id=user.user_id,
        email=user.email,
        name=request.name,
        role="customer",
        policy_id=str(policy.get("policy_id") or ""),
        policy_number=str(policy.get("policy_number") or ""),
        policy_type=request.policy_type,
        created_at=user.created_at,
    )


@router.get(
    "/customers",
    response_model=AdminCustomerListResponse,
    status_code=status.HTTP_200_OK,
    summary="List customer accounts with assigned policy category",
)
async def list_customers(
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    claim_repo: Annotated[ClaimRepository, Depends(get_claim_repository)],
) -> AdminCustomerListResponse:
    """Return all customer accounts with their assigned motor-policy details."""
    try:
        users = await user_repo.list_users(role=UserRole.CUSTOMER)
        all_policies = claim_repo.list_all_policies()
        policies_by_customer: dict[str, dict] = {}
        for p in all_policies:
            cid = p.get("customer_id")
            if cid and (cid not in policies_by_customer or p.get("status") == "active"):
                policies_by_customer[cid] = p

        customers: list[AdminCustomerResponse] = []
        for u in users:
            pol = policies_by_customer.get(u.user_id) or {}
            pol_type_raw = pol.get("policy_type") or "full_comprehensive"
            try:
                cat = PolicyCategory(pol_type_raw)
            except ValueError:
                cat = PolicyCategory.FULL_COMPREHENSIVE

            customers.append(
                AdminCustomerResponse(
                    user_id=u.user_id,
                    email=u.email,
                    name=None,
                    role="customer",
                    policy_id=str(pol.get("policy_id") or ""),
                    policy_number=str(pol.get("policy_number") or "N/A"),
                    policy_type=cat,
                    created_at=u.created_at,
                )
            )

        return AdminCustomerListResponse(
            customers=customers,
            total=len(customers),
        )
    except Exception as error:
        logger.exception("Failed to list customers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve customers",
        ) from error
