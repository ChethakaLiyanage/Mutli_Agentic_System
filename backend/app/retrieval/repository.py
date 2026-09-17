from supabase import Client

from app.core.config import settings


class RetrievalRepository:
    def __init__(self, client: Client):
        self.client = client


    def get_policy_by_number(
        self,
        policy_number: str,
        user_id: str,
    ) -> dict | None:

        response = (
            self.client
            .table("policies")
            .select("*")
            .eq("policy_number", policy_number)
            .eq("customer_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]


    def get_policy_by_id(
        self,
        policy_id: str,
        user_id: str,
    ) -> dict | None:

        response = (
            self.client
            .table("policies")
            .select("*")
            .eq("id", policy_id)
            .eq("customer_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]


    def get_claim_by_id(
        self,
        claim_id: str,
        user_id: str,
    ) -> dict | None:

        response = (
            self.client
            .table("claims")
            .select("*")
            .eq("id", claim_id)
            .eq("customer_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]


    def get_claim_by_reference(
        self,
        claim_reference: str,
        user_id: str,
    ) -> dict | None:

        response = (
            self.client
            .table("claims")
            .select("*")
            .eq("claim_reference", claim_reference)
            .eq("customer_id", user_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]


    def get_policy_claim_history(
        self,
        policy_id: str,
        user_id: str,
        exclude_claim_id: str | None = None,
    ) -> list[dict]:

        query = (
            self.client
            .table("claims")
            .select(
                "id,"
                "claim_reference,"
                "claim_type,"
                "incident_date,"
                "claimed_amount,"
                "status"
            )
            .eq("policy_id", policy_id)
            .eq("customer_id", user_id)
        )

        if exclude_claim_id:
            query = query.neq(
                "id",
                exclude_claim_id,
            )

        response = query.execute()

        return response.data or []


    def get_claim_documents(
        self,
        claim_id: str,
        user_id: str,
    ) -> list[dict]:

        response = (
            self.client
            .table("claim_documents")
            .select("*")
            .eq("claim_id", claim_id)
            .eq("customer_id", user_id)
            .execute()
        )

        return response.data or []