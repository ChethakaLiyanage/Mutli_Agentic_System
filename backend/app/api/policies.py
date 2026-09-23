"""Authenticated customer policy and coverage endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator.claim_repository import ClaimRepository, get_claim_repository
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.policy import MyPoliciesResponse, PolicySummaryResponse
from backend.app.security.dependencies import get_current_customer


router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/my-policies", response_model=MyPoliciesResponse)
async def list_my_policies(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_customer)],
    claim_repo: Annotated[ClaimRepository, Depends(get_claim_repository)],
) -> MyPoliciesResponse:
    """Return only policies owned by the authenticated customer."""
    try:
        claim_repo.ensure_default_policy(current_user.user_id)
        policies = claim_repo.list_policies_for_customer(current_user.user_id)
        response = [
            PolicySummaryResponse(
                policy_id=str(policy.get("policy_id") or ""),
                policy_number=str(policy.get("policy_number") or ""),
                insurance_type=str(policy.get("insurance_type") or "motor"),
                coverage_type=str(policy.get("coverage_type") or "full"),
                policy_type=str(policy.get("policy_type") or "full_comprehensive"),
                status=str(policy.get("status") or "active"),
                start_date=policy["start_date"],
                end_date=policy["end_date"],
                coverage_details=policy.get("coverage_details") or {},
                exclusions=policy.get("exclusions") or [],
            )
            for policy in policies
            if policy.get("policy_id") and policy.get("policy_number")
        ]
        return MyPoliciesResponse(policies=response, total=len(response))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policies",
        ) from error