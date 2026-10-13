export type FeeCategory = "full" | "reduced" | "student" | "training" | "exempt" | "special";
export type BillingPeriod = "march" | "september";

export interface FinanceMembership {
  uid: string;
  user_uid: string | null;
  username: string;
  role?: string;
  surname: string;
  lastname: string;
  email: string;
  email_confirmed: boolean;
  hs_email: string;
  hs_email_confirmed: boolean;
  status: "active" | "ended";
  fee_category: FeeCategory;
  member_since: string | null;
  ended_at: string | null;
  special_rate_cents: number | null;
  special_rate_valid_until: string | null;
  balance_cents?: number;
}

export interface FinanceCharge {
  uid: string;
  kind: "drink" | "membership" | "event_ticket";
  name: string;
  registration_id?: number | null;
  registration_name?: string | null;
  event_name?: string | null;
  event_date?: string | null;
  fee_category: string | null;
  cycle_year: number | null;
  quantity: number;
  unit_price_cents: number;
  amount_cents: number;
  due_date: string | null;
  status: "open" | "partially_paid" | "paid" | "cancelled" | "waived";
  allocated_cents: number;
  remaining_cents: number;
  legacy_paid_override?: boolean;
  created_at: string | null;
  status_at: string | null;
  status_note: string;
}

export interface FinancePayment {
  uid: string;
  amount_cents: number;
  method: "bank_transfer" | "cash" | "other";
  reference: string;
  note: string;
  received_at: string | null;
  voided_at: string | null;
  void_reason: string;
  allocated_cents?: number;
  unallocated_cents?: number;
  allocations?: Array<{
    charge_uid: string;
    charge_name: string;
    allocated_cents: number;
    active_allocated_cents: number;
    charge_remaining_cents: number;
    released: boolean;
    history?: Array<{ from_amount_cents: number; to_amount_cents: number; source: string; note: string; changed_at: string }>;
  }>;
}

export interface FinancePaymentMatchSuggestion {
  payment_amount_cents: number;
  available_amount_cents?: number;
  total_cents: number;
  remainder_cents: number;
  all_open_charges: boolean;
  charges: FinanceCharge[];
}

export type FinanceMailKind = "payment_reminder" | "student_verification";

export interface FinanceMailDraft {
  kind: FinanceMailKind;
  subject_template: string;
  body_template: string;
  minimum_balance_cents: number;
  cycle_year: number | null;
  selected_recipient_keys: string[] | null;
  version: number;
  updated_by_username: string;
  updated_at: string | null;
}

export interface FinanceMailCandidate {
  key: string;
  user_uid: string;
  membership_uid: string | null;
  username: string;
  display_name: string;
  email: string;
  email_source: string;
  balance_cents: number | null;
  can_select: boolean;
  default_selected: boolean;
  selected: boolean;
  reasons: string[];
}

export interface FinanceMailPreview {
  kind: FinanceMailKind;
  draft_version: number;
  minimum_balance_cents?: number;
  cycle_year?: number;
  selected_recipient_keys: string[] | null;
  selection_is_saved: boolean;
  scope_user_uid: string | null;
  summary: Record<string, number>;
  candidates: FinanceMailCandidate[];
  draft: FinanceMailDraft;
  mail_test_email: string;
}

export interface FinanceMailCampaignSummary {
  uid: string;
  kind: FinanceMailKind;
  source: string;
  test_only: boolean;
  cycle_year: number | null;
  minimum_balance_cents: number | null;
  subject_template: string;
  body_template: string;
  created_by_username: string;
  created_at: string | null;
  completed_at: string | null;
  status: string;
  counts: Record<string, number | boolean | string>;
  recipient_status_counts: Record<string, number>;
  recipient_count: number;
}

export interface FinanceMailCampaignRecipient {
  key: string;
  username: string;
  display_name: string;
  user_uid: string | null;
  email: string;
  balance_cents: number | null;
  activity: {
    charges?: Array<{ kind: string; name: string; amount_cents: number; status: string; created_at: string | null; due_date: string | null }>;
    payments?: Array<{ amount_cents: number; method: string; reference: string; received_at: string | null; voided: boolean }>;
    charges_truncated?: boolean;
    payments_truncated?: boolean;
  };
  status: string;
  reason: string;
  error_message: string;
  subject: string;
  body: string;
  attempted_at: string | null;
  completed_at: string | null;
}

export interface FinanceMailCampaignDetail {
  campaign: FinanceMailCampaignSummary;
  recipients: FinanceMailCampaignRecipient[];
}

export interface MembershipHistoryEvent {
  id: number;
  changed_at: string | null;
  changed_by: number | null;
  changed_by_username: string;
  from_status: string | null;
  to_status: string | null;
  from_fee_category: string | null;
  to_fee_category: string | null;
  from_member_since: string | null;
  to_member_since: string | null;
  from_special_rate_cents: number | null;
  to_special_rate_cents: number | null;
  note: string;
}

export interface FinanceChargeAdjustment {
  id: number;
  charge_uid: string;
  charge_name: string;
  cycle_year: number;
  from_amount_cents: number;
  to_amount_cents: number;
  from_fee_category: string | null;
  to_fee_category: string | null;
  from_due_date: string | null;
  to_due_date: string | null;
  changed_by_username: string;
  changed_at: string | null;
  source: string;
  note: string;
}

export interface MembershipFeeRecalculation {
  cycle_year: number;
  from_amount_cents: number;
  to_amount_cents: number;
  from_fee_category: string | null;
  to_fee_category: string;
  due_date: string | null;
}

export interface TallyItem {
  id: number;
  uid: string;
  name: string;
  price_cents: number | null;
  is_active: boolean;
}

export interface MembershipRequest {
  id: number;
  uid: string;
  user_uid: string | null;
  username: string;
  surname: string;
  lastname: string;
  email: string;
  request_type: "join" | "category";
  requested_category: FeeCategory;
  request_note: string;
  status: "pending" | "approved" | "rejected";
  submitted_at: string | null;
  review_note: string;
}

export interface FinanceAdminOverview {
  memberships: FinanceMembership[];
  finance_users: FinanceAccountUser[];
  available_users: Array<{ uid: string; username: string; surname: string; lastname: string; role: string }>;
  requests: MembershipRequest[];
  products: TallyItem[];
  fee_rates: Array<{ category: Exclude<FeeCategory, "special">; annual_amount_cents: number }>;
  payment_instructions: string;
  mail_test_email?: string;
}

export interface FinanceAccountUser {
  uid: string;
  username: string;
  surname: string;
  lastname: string;
  role: string;
  email: string;
  email_confirmed: boolean;
  hs_email: string;
  hs_email_confirmed: boolean;
  membership_uid: string | null;
  membership_status: "active" | "ended" | null;
  fee_category: FeeCategory | null;
  balance_cents: number;
  can_use_tally: boolean;
}

export interface FinanceUserDetail {
  user: FinanceAccountUser & {
    email?: string;
    email_confirmed?: boolean;
    hs_email?: string;
    hs_email_confirmed?: boolean;
  };
  membership: FinanceMembership | null;
  membership_history: MembershipHistoryEvent[];
  charges: FinanceCharge[];
  payments: FinancePayment[];
  charge_adjustments: FinanceChargeAdjustment[];
  balance_cents: number;
  unallocated_credit_cents: number;
  allocation_suggestion?: FinancePaymentMatchSuggestion;
  payment_instructions: string;
}

export interface MemberFinanceResponse {
  membership: FinanceMembership | null;
  can_use_tally?: boolean;
  pending_request: Pick<MembershipRequest, "uid" | "request_type" | "requested_category" | "submitted_at"> | null;
  cycle_year: number;
  products: TallyItem[];
  charges: FinanceCharge[];
  payments: FinancePayment[];
  charge_adjustments: FinanceChargeAdjustment[];
  balance_cents: number;
  unallocated_credit_cents: number;
  allocation_suggestion?: FinancePaymentMatchSuggestion;
  payment_instructions: string;
  student_verification?: {
    required: boolean;
    verified: boolean;
    email: string;
    verified_at: string | null;
  };
}

export interface BillingPreviewEntry {
  membership: FinanceMembership;
  cycle_year: number;
  due_date: string;
  amount_cents: number | null;
  effective_category: string;
  reason: string;
  needs_admin_review: boolean;
  already_billed: boolean;
  existing_status?: string | null;
  existing_amount_cents?: number | null;
  existing_due_date?: string | null;
  existing_period?: BillingPeriod | null;
  not_eligible?: boolean;
  verification_requested_at?: string | null;
  verification_at?: string | null;
}

export interface BillingRunMemberImpact {
  membership_uid: string;
  username: string;
  run_amount_cents: number;
  current_balance_cents: number;
  balance_after_void_cents: number;
}

export interface FinanceBillingRun {
  id: number;
  cycle_year: number;
  period: BillingPeriod;
  run_number: number;
  status: "issued" | "voided";
  due_date: string;
  created_at: string | null;
  created_by_username: string;
  voided_at: string | null;
  voided_by_username: string | null;
  void_reason: string;
  charge_count: number;
  open_charge_count: number;
  issued_amount_cents: number;
  open_amount_cents: number;
  cancelled_amount_cents: number;
  affected_members: BillingRunMemberImpact[];
}

export interface BillingPreviewResponse {
  cycle_year: number;
  period: BillingPeriod;
  due_date: string;
  run_created: boolean;
  active_run: FinanceBillingRun | null;
  runs: FinanceBillingRun[];
  members: BillingPreviewEntry[];
  total_to_issue_cents: number;
  charge_count: number;
}

export interface FinanceEventTicket {
  registration_id: number;
  event_id: number;
  event_name: string;
  event_visibility: string;
  event_date: string | null;
  registration_name: string;
  registration_visibility: string;
  user_uid: string;
  username: string;
  surname: string;
  lastname: string;
  role: string;
  price_cents: number | null;
  allocated_cents?: number;
  remaining_cents?: number | null;
  price_known: boolean;
  paid: boolean;
  ledger_linked: boolean;
  valid: boolean;
  status: "open" | "partially_paid" | "paid" | "cancelled";
  timestamp: string | null;
  created_by_username: string | null;
  cancelled_at: string | null;
  cancel_reason: string;
}

export interface FinanceEventTicketResponse {
  tickets: FinanceEventTicket[];
  open_amount_cents: number;
  open_unlinked_count: number;
}

async function financeRequest<T>(path: string, method = "GET", csrfToken?: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let payload: T & { error?: string; errors?: Record<string, string | string[]>; success?: boolean };
  try {
    payload = JSON.parse(await response.text()) as T & { error?: string; errors?: Record<string, string | string[]>; success?: boolean };
  } catch {
    const responseType = response.headers.get("content-type") || "non-JSON response";
    throw new Error(`Finanzanfrage fehlgeschlagen (HTTP ${response.status}; ${responseType}). Bitte lade die Seite neu und prüfe die Verbindung zum Finanzdienst.`);
  }
  if (!response.ok || payload.success === false) {
    const detail = Object.values(payload.errors ?? {}).flat()[0];
    throw new Error(payload.error || detail || `Finanzanfrage fehlgeschlagen (HTTP ${response.status}).`);
  }
  return payload;
}

export function getMyFinances() {
  return financeRequest<MemberFinanceResponse>("/api/v1/me/finances");
}

export function submitTallyPurchase(itemId: number, quantity: number, csrfToken: string) {
  return financeRequest<{ success: boolean; charge: FinanceCharge; balance_cents: number }>(
    "/api/v1/me/finance/purchases", "POST", csrfToken, { item_id: itemId, quantity },
  );
}

export function requestMembership(requestType: "join" | "category", category: FeeCategory, note: string, csrfToken: string) {
  return financeRequest<{ success: boolean; uid: string }>(
    "/api/v1/me/membership-requests", "POST", csrfToken,
    { request_type: requestType, requested_category: category, note },
  );
}

export function requestStudentVerification(csrfToken: string) {
  return financeRequest<{ success: boolean; cycle_year: number; already_verified?: boolean }>(
    "/api/v1/me/student-verification", "POST", csrfToken, {},
  );
}

export function getAdminFinance() {
  return financeRequest<FinanceAdminOverview>("/api/v1/manage/finance");
}

export function getAdminFinanceMember(uid: string) {
  return financeRequest<{ membership: FinanceMembership; membership_history: MembershipHistoryEvent[]; charges: FinanceCharge[]; payments: FinancePayment[]; payment_instructions: string }>(
    `/api/v1/manage/finance/memberships/${uid}`,
  );
}

export function getAdminFinanceUser(uid: string) {
  return financeRequest<FinanceUserDetail>(`/api/v1/manage/finance/users/${uid}`);
}

export function getAdminEventTickets(filters: { query?: string; status?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.query?.trim()) params.set("q", filters.query.trim());
  if (filters.status) params.set("status", filters.status);
  const suffix = params.size ? `?${params.toString()}` : "";
  return financeRequest<FinanceEventTicketResponse>(`/api/v1/manage/finance/event-tickets${suffix}`);
}

export function updateAdminEventTicketStatus(registrationIds: number[], paid: boolean, note: string, csrfToken: string) {
  return financeRequest<{ success: boolean; updated_count: number }>(
    "/api/v1/manage/finance/event-tickets/status",
    "PUT",
    csrfToken,
    { registration_ids: registrationIds, paid, note },
  );
}

export function createFinanceMembership(
  userUid: string,
  feeCategory: FeeCategory,
  memberSince: string,
  specialRateCents: number | null,
  csrfToken: string,
) {
  return financeRequest<{ success: boolean; membership: FinanceMembership }>(
    "/api/v1/manage/finance/memberships", "POST", csrfToken,
    { user_uid: userUid, fee_category: feeCategory, member_since: memberSince, special_rate_cents: specialRateCents },
  );
}

export function updateFinanceMembership(uid: string, values: Partial<FinanceMembership> & { note?: string }, csrfToken: string) {
  return financeRequest<{ success: boolean; membership: FinanceMembership; fee_adjustments: MembershipFeeRecalculation[] }>(
    `/api/v1/manage/finance/memberships/${uid}`, "PUT", csrfToken, values,
  );
}

export function reviewMembershipRequest(
  id: number,
  decision: "approve" | "reject",
  values: { fee_category?: FeeCategory; special_rate_cents?: number; special_rate_valid_until?: string; member_since?: string; note?: string },
  csrfToken: string,
) {
  return financeRequest(`/api/v1/manage/finance/requests/${id}/review`, "POST", csrfToken, { decision, ...values });
}

export function createTallyItem(name: string, priceCents: number, csrfToken: string) {
  return financeRequest<{ success: boolean; item: TallyItem }>(
    "/api/v1/manage/finance/products", "POST", csrfToken, { name, price_cents: priceCents },
  );
}

export function updateTallyItem(id: number, name: string, priceCents: number, active: boolean, csrfToken: string) {
  return financeRequest<{ success: boolean; item: TallyItem }>(
    `/api/v1/manage/finance/products/${id}`, "PUT", csrfToken,
    { name, price_cents: priceCents, is_active: active },
  );
}

export function archiveTallyItem(id: number, csrfToken: string) {
  return financeRequest<{ success: boolean; item: TallyItem }>(`/api/v1/manage/finance/products/${id}`, "DELETE", csrfToken);
}

export function updateMembershipFeeRate(category: Exclude<FeeCategory, "special">, amountCents: number, csrfToken: string) {
  return financeRequest<{ success: boolean; rate: { category: string; annual_amount_cents: number } }>(
    `/api/v1/manage/finance/rates/${category}`, "PUT", csrfToken,
    { annual_amount_cents: amountCents },
  );
}

export function updateFinanceInstructions(paymentInstructions: string, mailTestEmail: string, csrfToken: string) {
  return financeRequest<{ success: boolean; payment_instructions: string; mail_test_email: string }>(
    "/api/v1/manage/finance/settings", "PUT", csrfToken,
    { payment_instructions: paymentInstructions, mail_test_email: mailTestEmail },
  );
}

export function getBillingPreview(cycleYear: number, period: BillingPeriod = "march") {
  return financeRequest<BillingPreviewResponse>(
    `/api/v1/manage/finance/billing-preview/${cycleYear}?period=${period}`,
  );
}

export function getFinanceMailDraft(kind: FinanceMailKind) {
  return financeRequest<{ draft: FinanceMailDraft; mail_test_email: string }>(`/api/v1/manage/finance/mail-drafts/${kind}`);
}

export function saveFinanceMailDraft(
  kind: FinanceMailKind,
  values: Pick<FinanceMailDraft, "subject_template" | "body_template" | "minimum_balance_cents" | "cycle_year" | "selected_recipient_keys"> & { version: number },
  csrfToken: string,
) {
  return financeRequest<{ success: boolean; draft: FinanceMailDraft }>(
    `/api/v1/manage/finance/mail-drafts/${kind}`, "PUT", csrfToken, values,
  );
}

export function previewFinanceMailDraft(kind: FinanceMailKind, version: number, csrfToken: string, scopeUserUid?: string) {
  return financeRequest<FinanceMailPreview>(
    `/api/v1/manage/finance/mail-drafts/${kind}/preview`, "POST", csrfToken,
    { version, ...(scopeUserUid ? { scope_user_uid: scopeUserUid } : {}) },
  );
}

export function testFinanceMailDraft(kind: FinanceMailKind, version: number, csrfToken: string) {
  return financeRequest<{ success: boolean; campaign_uid: string; recipient_email: string }>(
    `/api/v1/manage/finance/mail-drafts/${kind}/test`, "POST", csrfToken, { version },
  );
}

export function sendFinanceMailDraft(
  kind: FinanceMailKind,
  version: number,
  selectedRecipientKeys: string[],
  csrfToken: string,
  scopeUserUid?: string,
) {
  return financeRequest<{ success: boolean; campaign_uid: string; selected: number; counts: Record<string, number | boolean | string> }>(
    `/api/v1/manage/finance/mail-drafts/${kind}/send`, "POST", csrfToken,
    { version, selected_recipient_keys: selectedRecipientKeys, ...(scopeUserUid ? { scope_user_uid: scopeUserUid } : {}) },
  );
}

export function getFinanceMailCampaigns(kind: FinanceMailKind) {
  return financeRequest<{ campaigns: FinanceMailCampaignSummary[] }>(`/api/v1/manage/finance/mail-campaigns?kind=${kind}`);
}

export function getFinanceMailCampaign(uid: string) {
  return financeRequest<FinanceMailCampaignDetail>(`/api/v1/manage/finance/mail-campaigns/${uid}`);
}

export function createBillingRun(cycleYear: number, period: BillingPeriod, csrfToken: string) {
  return financeRequest<{ success: boolean; cycle_year: number; period: BillingPeriod; run_number: number; due_date: string; created_count: number; total_cents: number }>(
    "/api/v1/manage/finance/billing-runs", "POST", csrfToken, { cycle_year: cycleYear, period },
  );
}

export function voidFinanceBillingRun(runId: number, reason: string, csrfToken: string) {
  return financeRequest<{ success: boolean; run: FinanceBillingRun; voided_charge_count: number; affected_members: BillingRunMemberImpact[] }>(
    `/api/v1/manage/finance/billing-runs/${runId}/void`, "POST", csrfToken, { reason },
  );
}

export function recordFinancePayment(
  userUid: string,
  values: { amount_cents: number; method: "bank_transfer" | "cash" | "other"; reference: string; note: string; received_at: string },
  csrfToken: string,
) {
  return financeRequest<{ success: boolean; payment: FinancePayment; balance_cents: number; match_suggestion: FinancePaymentMatchSuggestion }>(
    `/api/v1/manage/finance/users/${userUid}/payments`, "POST", csrfToken, values,
  );
}

export function confirmFinancePaymentChargeSuggestion(
  userUid: string,
  paymentUid: string | null,
  chargeUids: string[],
  csrfToken: string,
) {
  return financeRequest<{ success: boolean; confirmed_count: number; total_cents: number; balance_cents: number }>(
    paymentUid
      ? `/api/v1/manage/finance/users/${userUid}/payments/${paymentUid}/confirm-charges`
      : `/api/v1/manage/finance/users/${userUid}/allocations/confirm`,
    "POST",
    csrfToken,
    { charge_uids: chargeUids },
  );
}

export function voidFinancePayment(uid: string, reason: string, csrfToken: string) {
  return financeRequest<{ success: boolean; payment: FinancePayment; balance_cents: number }>(
    `/api/v1/manage/finance/payments/${uid}/void`, "POST", csrfToken, { reason },
  );
}

export function updateFinanceChargeStatus(uid: string, status: "open" | "paid" | "cancelled", note: string, csrfToken: string) {
  return financeRequest<{ success: boolean; charge: FinanceCharge; balance_cents: number }>(
    `/api/v1/manage/finance/charges/${uid}/status`, "PUT", csrfToken, { status, note },
  );
}
