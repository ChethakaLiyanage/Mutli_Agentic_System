import { ClaimDocumentItem } from "./review";

export interface ClaimSummary {
  claim_id: string;
  claim_reference?: string | null;
  workflow_id?: string | null;
  policy_id?: string | null;
  policy_number?: string | null;
  incident_type?: string | null;
  incident_date?: string | null;
  incident_location?: string | null;
  incident_description?: string | null;
  claimed_amount?: number | null;
  claim_status?: string | null;
  workflow_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ClaimDetailCustomer {
  claim_id: string;
  claim_reference?: string | null;
  workflow_id?: string | null;
  policy_id?: string | null;
  policy_number?: string | null;
  incident_type?: string | null;
  incident_date?: string | null;
  incident_location?: string | null;
  incident_description?: string | null;
  claimed_amount?: number | null;
  claim_status?: string | null;
  workflow_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  documents: ClaimDocumentItem[];
  decision?: string | null;
  rejection_reason?: string | null;
  decided_at?: string | null;
  customer_explanation?: string | null;
}

export interface MyClaimsResponse {
  claims: ClaimSummary[];
  total: number;
}
