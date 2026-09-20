export interface PolicySummary {
  policy_id: string;
  policy_number: string;
  insurance_type: string;
  coverage_type: string;
  status: string;
  start_date: string;
  end_date: string;
  coverage_details: Record<string, unknown>;
  exclusions: unknown[];
}

export interface MyPoliciesResponse {
  policies: PolicySummary[];
  total: number;
}