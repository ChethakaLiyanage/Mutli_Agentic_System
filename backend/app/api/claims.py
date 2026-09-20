"""Authenticated customer and staff claim query endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.graph.state import WorkflowState
from backend.app.orchestrator.claim_repository import ClaimRepository, get_claim_repository
from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.orchestrator.repository import WorkflowRepository
from backend.app.schemas.auth import AuthenticatedUser, UserRole
from backend.app.schemas.claim import (
    ClaimDetailCustomerResponse,
    ClaimSummaryResponse,
    MyClaimsResponse,
)
from backend.app.schemas.document import ClaimDocumentResponse
from backend.app.security.dependencies import get_current_user
from backend.app.services.document_service import get_document_repository
from backend.app.services.persistence import get_application_repositories


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claims", tags=["claims"])


def _customer_status_explanation(wf_status: str | None, claim_status: str | None) -> str:
    if wf_status == WorkflowStatus.AWAITING_DOCUMENTS.value:
        return "Please upload the required documents to support your claim."
    if wf_status in (
        WorkflowStatus.DOCUMENTS_SUBMITTED.value,
        WorkflowStatus.FRAUD_TRIAGE.value,
    ):
        return "Your documents have been received and are undergoing initial verification."
    if wf_status in (
        WorkflowStatus.FRAUD_TRIAGE_COMPLETE.value,
        WorkflowStatus.REVIEW_SUMMARY_GENERATION.value,
        WorkflowStatus.AWAITING_ASSIGNMENT.value,
    ):
        return "Your claim has been submitted and is waiting to be assigned to a claims officer."
    if wf_status == WorkflowStatus.UNDER_HUMAN_REVIEW.value:
        return "Your claim has been assigned and is currently under review by a claims officer."
    if wf_status == WorkflowStatus.APPROVED.value or claim_status == "approved":
        return "Your claim has been approved by a claims officer."
    if wf_status == WorkflowStatus.REJECTED.value or claim_status == "rejected":
        return "Your claim has been reviewed and rejected."
    if wf_status == WorkflowStatus.MORE_INFORMATION_REQUIRED.value or claim_status == "more_information_required":
        return "Additional information is required before your claim can proceed."
    if wf_status == WorkflowStatus.ESCALATED.value or claim_status == "escalated":
        return "Your claim has been escalated for specialist assessment."
    return "Your claim is currently being processed by our team."


@router.get("/my-claims", response_model=MyClaimsResponse)
async def list_my_claims(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    claim_repo: Annotated[ClaimRepository, Depends(get_claim_repository)],
) -> MyClaimsResponse:
    """Retrieve all claims submitted by or accessible to the current customer."""
    try:
        claims = []
        try:
            claims = claim_repo.list_for_customer(current_user.user_id)
        except Exception as e:
            logger.warning("Failed to list claims from claim_repo: %s", e)
            claims = []

        workflows = get_application_repositories().workflows

        # Check user workflows in case active draft claims exist that are not yet in claims table
        known_claim_ids = {c.claim_id for c in claims if c.claim_id}
        try:
            pending_wfs = await workflows.list_by_status(None, limit=30)
            for wf in pending_wfs:
                if (
                    wf.authenticated_user_id == current_user.user_id
                    or (wf.claim_context and wf.claim_context.customer_id == current_user.user_id)
                ):
                    if wf.claim_context and wf.claim_context.claim_id:
                        if wf.claim_context.claim_id not in known_claim_ids:
                            known_claim_ids.add(wf.claim_context.claim_id)
                            draft_claim = wf.claim_context.model_copy(
                                update={
                                    "workflow_id": wf.workflow_id,
                                    "created_at": wf.created_at,
                                    "updated_at": wf.updated_at,
                                }
                            )
                            claims.append(draft_claim)
        except Exception:
            pass

        # Sort claims descending by created_at (newest first)
        def _sort_key(c):
            ca = getattr(c, "created_at", None)
            if ca:
                return ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
            return ""
        claims.sort(key=_sort_key, reverse=True)

        # Concurrent parallel lookup for active workflows only (bounded with timeout)
        active_wf_ids = list({
            claim.workflow_id
            for claim in claims[:15]
            if getattr(claim, "workflow_id", None) and getattr(claim, "claim_status", None) not in ("approved", "rejected")
        })
        wf_status_map: dict[str, str] = {}
        if active_wf_ids:
            async def _safe_get_wf_status(wid: str) -> tuple[str, str | None]:
                try:
                    wf = await asyncio.wait_for(workflows.get(wid), timeout=2.0)
                    return wid, (wf.current_status.value if wf else None)
                except Exception:
                    return wid, None

            results = await asyncio.gather(*[_safe_get_wf_status(wid) for wid in active_wf_ids], return_exceptions=True)
            for res in results:
                if isinstance(res, tuple) and res[1]:
                    wf_status_map[res[0]] = res[1]

        summaries: list[ClaimSummaryResponse] = []
        for claim in claims:
            wf_id = getattr(claim, "workflow_id", None)
            wf_status = wf_status_map.get(wf_id) if wf_id else None

            summaries.append(
                ClaimSummaryResponse(
                    claim_id=claim.claim_id or "",
                    claim_reference=claim.claim_reference,
                    workflow_id=wf_id,
                    policy_id=claim.policy_id,
                    policy_number=claim.policy_number,
                    incident_type=claim.incident_type.value if claim.incident_type else None,
                    incident_date=claim.incident_date,
                    incident_location=claim.incident_location,
                    incident_description=claim.incident_description,
                    claimed_amount=float(claim.claimed_amount) if claim.claimed_amount is not None else None,
                    claim_status=claim.claim_status,
                    workflow_status=wf_status or claim.claim_status,
                    created_at=getattr(claim, "created_at", None),
                    updated_at=getattr(claim, "updated_at", None),
                )
            )

        return MyClaimsResponse(claims=summaries, total=len(summaries))
    except Exception as error:
        logger.exception("Failed to list customer claims")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve claims",
        ) from error


@router.get("/{claim_id}", response_model=ClaimDetailCustomerResponse)
async def get_claim_detail(
    claim_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    claim_repo: Annotated[ClaimRepository, Depends(get_claim_repository)],
) -> ClaimDetailCustomerResponse:
    """Get customer-safe claim details including documents and authoritative human decision.

    PRIVACY INVARIANT: Fraud score, risk level, machine learning indicators,
    and internal staff summaries are strictly hidden.
    """
    try:
        claim = None
        try:
            claim = claim_repo.get_by_id(claim_id)
        except Exception:
            claim = None

        workflows = get_application_repositories().workflows
        wf: WorkflowState | None = None

        if claim is None:
            # Check active workflows
            try:
                pending_wfs = await workflows.list_by_status(None, limit=30)
                for candidate in pending_wfs:
                    if candidate.claim_context and candidate.claim_context.claim_id == claim_id:
                        claim = candidate.claim_context
                        wf = candidate
                        break
            except Exception:
                pass

        if claim is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Claim not found",
            )

        # Enforce access control
        is_owner = claim.customer_id == current_user.user_id
        is_staff = current_user.role in (UserRole.ADMIN, UserRole.CLAIMS_OFFICER)
        if not is_owner and not is_staff:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You are not authorized to view this claim",
            )

        # Retrieve documents
        doc_repo = get_document_repository()
        cust_id = claim.customer_id or current_user.user_id
        docs_raw = []
        try:
            docs_raw = await doc_repo.get_documents_for_claim(
                claim_id=claim.claim_id or claim_id,
                customer_id=cust_id,
            )
        except Exception:
            docs_raw = []

        documents: list[ClaimDocumentResponse] = []
        for doc in docs_raw:
            meta = doc.get("metadata") or {}
            fname = doc.get("file_name") or meta.get("original_filename") or "document.pdf"
            documents.append(
                ClaimDocumentResponse(
                    document_id=doc.get("document_id") or "",
                    claim_id=doc.get("claim_id") or claim_id,
                    customer_id=cust_id,
                    document_type=doc.get("document_type", "other"),
                    original_filename=meta.get("original_filename") or fname,
                    file_size_bytes=meta.get("file_size") or doc.get("file_size_bytes"),
                    content_type=meta.get("content_type") or doc.get("content_type"),
                    uploaded_at=doc.get("created_at") or meta.get("uploaded_at"),
                    download_url=f"/documents/{doc.get('document_id')}/download",
                )
            )

        # Retrieve workflow context if linked
        wf_status = None
        decision_val = None
        rejection_reason = None
        decided_at = None
        customer_explanation = None

        if wf is None and claim.workflow_id:
            try:
                wf = await asyncio.wait_for(workflows.get(claim.workflow_id), timeout=2.0)
            except Exception:
                wf = None

        if wf:
            wf_status = wf.current_status.value

            if wf.human_review_result:
                decision_val = wf.human_review_result.get("decision")
                decided_at = wf.human_review_result.get("decided_at")
                if decision_val in ("reject", "request_more_information"):
                    rejection_reason = wf.human_review_result.get("reason")

            if wf.guidance_result:
                g_data = wf.guidance_result.get("data") or {}
                customer_explanation = (
                    g_data.get("customer_guidance")
                    or g_data.get("status_explanation")
                )

        if not customer_explanation:
            customer_explanation = _customer_status_explanation(wf_status, claim.claim_status)

        return ClaimDetailCustomerResponse(
            claim_id=claim.claim_id or claim_id,
            claim_reference=claim.claim_reference,
            workflow_id=claim.workflow_id,
            policy_id=claim.policy_id,
            policy_number=claim.policy_number,
            incident_type=claim.incident_type.value if claim.incident_type else None,
            incident_date=claim.incident_date,
            incident_location=claim.incident_location,
            incident_description=claim.incident_description,
            claimed_amount=float(claim.claimed_amount) if claim.claimed_amount is not None else None,
            claim_status=claim.claim_status,
            workflow_status=wf_status or claim.claim_status,
            created_at=getattr(claim, "created_at", None),
            updated_at=getattr(claim, "updated_at", None),
            documents=documents,
            decision=decision_val,
            rejection_reason=rejection_reason,
            decided_at=decided_at,
            customer_explanation=customer_explanation,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to retrieve claim detail")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve claim details",
        ) from error
