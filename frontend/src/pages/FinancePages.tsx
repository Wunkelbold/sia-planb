import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { getCurrentSession } from "../api/events";
import {
  archiveTallyItem,
  confirmFinancePaymentChargeSuggestion,
  createBillingRun,
  createFinanceMembership,
  createTallyItem,
  getFinanceMailCampaign,
  getFinanceMailCampaigns,
  getFinanceMailDraft,
  getAdminFinance,
  getAdminEventTickets,
  getAdminFinanceUser,
  getBillingPreview,
  getMyFinances,
  previewFinanceMailDraft,
  recordFinancePayment,
  requestMembership,
  requestStudentVerification,
  reviewMembershipRequest,
  saveFinanceMailDraft,
  sendFinanceMailDraft,
  submitTallyPurchase,
  testFinanceMailDraft,
  updateFinanceChargeStatus,
  updateAdminEventTicketStatus,
  updateFinanceInstructions,
  updateFinanceMembership,
  updateMembershipFeeRate,
  updateTallyItem,
  voidFinanceBillingRun,
  voidFinancePayment,
  type FinanceAdminOverview,
  type FinanceAccountUser,
  type FinanceBillingRun,
  type FinanceCharge,
  type FinanceEventTicket,
  type FinanceMembership,
  type FinanceMailCandidate,
  type FinanceMailDraft,
  type FinanceMailKind,
  type FinanceMailPreview,
  type FinancePayment,
  type FinancePaymentMatchSuggestion,
  type MembershipFeeRecalculation,
  type BillingPeriod,
  type FeeCategory,
  type MembershipRequest,
  type TallyItem,
} from "../api/finance";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

function euros(cents: number | null | undefined) {
  return ((cents || 0) / 100).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function financeDate(value: string | null) {
  if (!value) return "Nicht angegeben";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function feeCategoryLabel(category: string) {
  if (category === "full" || category === "alumni") return "Vollbetrag";
  if (category === "reduced") return "Ermäßigt";
  if (category === "student") return "Student:in";
  if (category === "training") return "In Ausbildung";
  if (category === "exempt") return "Befreit";
  if (category === "special") return "Sonderbeitrag";
  return category;
}

function memberDisplayName(member: Pick<FinanceMembership, "surname" | "lastname" | "username">) {
  return [member.surname, member.lastname].filter(Boolean).join(" ") || member.username;
}

function feeRecalculationSummary(adjustments: MembershipFeeRecalculation[]) {
  if (!adjustments.length) return "Kein bereits ausgestellter Jahresbeitrag wurde geändert; neue Beiträge erscheinen im nächsten passenden Lauf.";
  return `Jahresbeiträge angepasst: ${adjustments.map((adjustment) => `Beitragsjahr ${adjustment.cycle_year}${adjustment.from_fee_category ? ` (${feeCategoryLabel(adjustment.from_fee_category)} → ${feeCategoryLabel(adjustment.to_fee_category)})` : ` (${feeCategoryLabel(adjustment.to_fee_category)})`}: ${euros(adjustment.from_amount_cents)} → ${euros(adjustment.to_amount_cents)}${adjustment.due_date ? `, fällig ${adjustment.due_date}` : ""}`).join("; ")}.`;
}

function chargeStatusLabel(charge: FinanceCharge) {
  if (charge.status === "paid") return charge.kind === "event_ticket" || charge.legacy_paid_override ? "Als bezahlt markiert" : "Bezahlt";
  if (charge.status === "partially_paid") return "Teilweise bezahlt";
  if (charge.status === "cancelled") return "Storniert";
  if (charge.status === "waived") return "Beitragsfrei";
  return "Offen";
}

function chargeAllocationSummary(charge: FinanceCharge) {
  if (charge.legacy_paid_override) return "Altbestand: manuell als bezahlt markiert";
  const allocated = charge.allocated_cents || 0;
  if (allocated <= 0 && charge.status !== "partially_paid") return "";
  return `${euros(allocated)} zugeordnet · ${euros(charge.remaining_cents ?? charge.amount_cents)} offen`;
}

function chargeAdjustmentSourceLabel(source: string) {
  if (source === "student_verification") return "Studentenstatus bestätigt";
  if (source === "membership_request_approved") return "Antrag genehmigt";
  if (source === "membership_edit") return "Mitgliedschaft geändert";
  return source;
}

function chargeTitle(charge: FinanceCharge) {
  if (charge.kind === "membership" && (charge.status === "waived" || charge.status === "cancelled")) {
    return `Mitgliedsbeitrag ${charge.cycle_year || ""}`.trim();
  }
  return charge.name;
}

function chargeDescription(charge: FinanceCharge) {
  if (charge.kind === "event_ticket") {
    return `${charge.event_name || "Event"} · ${charge.registration_name || "Ticket"} · ${financeDate(charge.event_date || charge.created_at)}`;
  }
  if (charge.kind === "membership") {
    const category = charge.amount_cents > 0 && charge.fee_category ? ` · ${feeCategoryLabel(charge.fee_category)}` : "";
    return `Mitgliedsbeitrag ${charge.cycle_year || ""}${category} · ${financeDate(charge.created_at)}`;
  }
  return `${charge.quantity} × ${euros(charge.unit_price_cents)} · ${financeDate(charge.created_at)}`;
}

const feeCategories: Array<{ value: FeeCategory; label: string }> = [
  { value: "full", label: "Vollbetrag (Alumni)" },
  { value: "reduced", label: "Ermäßigter Beitrag" },
  { value: "student", label: "Student:in" },
  { value: "training", label: "In Ausbildung" },
  { value: "exempt", label: "Befreiung beantragen" },
  { value: "special", label: "Sonderbeitrag beantragen" },
];

const adminFeeCategories: Array<{ value: FeeCategory; label: string }> = feeCategories.map((item) =>
  item.value === "exempt" ? { ...item, label: "Befreit (Ehrenmitglied)" } : { ...item, label: item.label.replace(" beantragen", "") },
);

function MemberRequestForm({
  requestType,
  initialCategory,
  csrfToken,
  onSuccess,
  onError,
}: {
  requestType: "join" | "category";
  initialCategory: FeeCategory;
  csrfToken: string;
  onSuccess: () => void;
  onError: (message: string) => void;
}) {
  const [category, setCategory] = useState<FeeCategory>(initialCategory);
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: () => requestMembership(requestType, category, note, csrfToken),
    onSuccess,
    onError: (error) => onError(error instanceof Error ? error.message : "Die Anfrage konnte nicht gesendet werden."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onError("");
    mutation.mutate();
  }

  return (
    <form className="finance-request-form" onSubmit={submit}>
      <label className="profile-field">
        <span>{requestType === "join" ? "Beitragskategorie" : "Gewünschte Kategorie"}</span>
        <select onChange={(event) => setCategory(event.target.value as FeeCategory)} value={category}>
          {feeCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      {category === "special" && (
        <label className="profile-field">
          <span>Begründung für den Sonderbeitrag</span>
          <textarea maxLength={1000} onChange={(event) => setNote(event.target.value)} required rows={3} value={note} />
        </label>
      )}
      <button className="participation-button" disabled={mutation.isPending} type="submit">
        {mutation.isPending ? "Wird gesendet …" : requestType === "join" ? "Beitragsmitgliedschaft beantragen" : "Beitragskategorie ändern beantragen"}
      </button>
    </form>
  );
}

export function MemberFinancePage() {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const financesQuery = useQuery({
    queryKey: ["my-finances"],
    queryFn: getMyFinances,
    enabled: sessionQuery.data?.authenticated === true,
  });
  const [quantity, setQuantity] = useState(1);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const data = financesQuery.data;
  const membership = data?.membership;
  const studentVerification = data?.student_verification;
  const purchaseMutation = useMutation({
    mutationFn: (itemId: number) => submitTallyPurchase(itemId, quantity, sessionQuery.data?.csrf_token || ""),
    onSuccess: async () => {
      setNotice("Dein Eintrag wurde zum Tally hinzugefügt.");
      setError("");
      setQuantity(1);
      await queryClient.invalidateQueries({ queryKey: ["my-finances"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Der Eintrag konnte nicht gespeichert werden."),
  });
  const requestMutation = useMutation({
    mutationFn: () => requestStudentVerification(sessionQuery.data?.csrf_token || ""),
    onSuccess: async () => {
      setNotice("Bestätigungsmail für den aktuellen Beitragszyklus wurde angefordert.");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["my-finances"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Die Bestätigungsmail konnte nicht angefordert werden."),
  });
  const requestSuccess = async () => {
    setNotice("Deine Anfrage wurde an die Verwaltung gesendet.");
    setError("");
    await queryClient.invalidateQueries({ queryKey: ["my-finances"] });
  };

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="finance-page">
        <header className="finance-page__heading">
          <p className="eyebrow eyebrow--muted">BENUTZERKONTO</p>
          <h1>{sessionQuery.data?.can_use_tally ? "Finanzen & Tally" : "Finanzen"}<span>.</span></h1>
          <p>{sessionQuery.data?.can_use_tally ? "Deine Tickets, Tally-Einträge, Beitragsmitgliedschaften und Zahlungen im Überblick." : "Deine Tickets, Beitragsmitgliedschaften und Zahlungen im Überblick."}</p>
        </header>
        {sessionQuery.isLoading && <p className="detail-loading" role="status">Konto wird geprüft …</p>}
        {sessionQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Dein Konto konnte nicht geprüft werden.</p>}
        {sessionQuery.data && !sessionQuery.data.authenticated && (
          <div className="message-panel" role="status"><div><h2>Melde dich an, um deine Finanzen zu sehen.</h2><Link className="participation-button" to="/login">Einloggen</Link></div></div>
        )}
        {sessionQuery.data?.authenticated && financesQuery.isLoading && <p className="detail-loading" role="status">Finanzen werden geladen …</p>}
        {sessionQuery.data?.authenticated && financesQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Deine Finanzen konnten nicht geladen werden.</p>}
        {sessionQuery.data?.authenticated && data && (
          <>
            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
            {!membership && (
              <section className="finance-empty-panel">
                <h2>Deine Beitragsmitgliedschaft ist noch nicht eingerichtet.</h2>
                {data.pending_request ? (
                  <p>Dein Antrag auf eine Beitragsmitgliedschaft ({feeCategoryLabel(data.pending_request.requested_category)}) wird von der Verwaltung geprüft.</p>
                ) : (
                  <>
                    <p>Du kannst eine Beitragsmitgliedschaft beantragen. Die Verwaltung prüft Beitragskategorie und Startdatum.</p>
                    <MemberRequestForm
                      csrfToken={sessionQuery.data.csrf_token || ""}
                      initialCategory="student"
                      onError={setError}
                      onSuccess={() => void requestSuccess()}
                      requestType="join"
                    />
                  </>
                )}
              </section>
            )}
            {membership && (
              <>
                {studentVerification?.required && membership.status === "active" && (
                  <section className="finance-info-panel">
                    <div>
                      <p className="eyebrow eyebrow--muted">BEITRAGSZYKLUS {data.cycle_year}</p>
                      <h2>Studentenstatus bestätigen</h2>
                      <p>{studentVerification.verified
                        ? `Deine Hochschul-E-Mail ist für diesen Beitragszyklus bestätigt (${studentVerification.email}).`
                        : `Bestätige ${studentVerification.email || "deine Hochschul-E-Mail"} erneut, damit für diesen Zyklus der Student:innenbeitrag gilt.`}</p>
                    </div>
                    {!studentVerification.verified && (
                      <button className="participation-button" disabled={requestMutation.isPending || !studentVerification.email} onClick={() => requestMutation.mutate()} type="button">
                        {requestMutation.isPending ? "Wird angefordert …" : "Bestätigungsmail senden"}
                      </button>
                    )}
                  </section>
                )}

                {membership.status === "active" && data.pending_request && (
                  <p className="action-feedback" role="status">Dein Antrag auf eine Änderung der Beitragskategorie ({feeCategoryLabel(data.pending_request.requested_category)}) wird geprüft.</p>
                )}
                {membership.status === "active" && !data.pending_request && (
                  <details className="finance-request-details">
                    <summary>Beitragskategorie ändern oder Sonderbeitrag beantragen</summary>
                    <MemberRequestForm
                      csrfToken={sessionQuery.data.csrf_token || ""}
                      initialCategory={membership.fee_category}
                      onError={setError}
                      onSuccess={() => void requestSuccess()}
                      requestType="category"
                    />
                  </details>
                )}

              </>
            )}
            {(membership || data.can_use_tally || data.charges.length > 0 || data.payments.length > 0) && (
              <section aria-label="Offener Saldo" className="finance-balance-card">
                <div>
                  <p className="eyebrow eyebrow--muted">AKTUELLER SALDO</p>
                  <strong>{euros(data.balance_cents)}</strong>
                  <p>{membership ? (membership.status === "active" ? `Beitragsmitgliedschaft · ${feeCategoryLabel(membership.fee_category)}` : "Beitragsmitgliedschaft beendet · offene Beträge bleiben sichtbar") : "Tickets und persönliche Buchungen; keine Beitragsmitgliedschaft"}</p>
                  {data.unallocated_credit_cents > 0 && <p>Nicht zugeordnetes Guthaben · {euros(data.unallocated_credit_cents)}</p>}
                </div>
                {membership && <span className={`finance-status finance-status--${membership.status}`}>{membership.status === "active" ? "Beitrag aktiv" : "Beitrag beendet"}</span>}
              </section>
            )}

            {data.can_use_tally && (
              <section aria-labelledby="tally-purchase-title" className="finance-section">
                <div className="finance-section__heading">
                  <div><p className="eyebrow eyebrow--muted">QR-TALLY</p><h2 id="tally-purchase-title">Getränk eintragen<span>.</span></h2></div>
                  <label className="profile-field finance-quantity"><span>Menge</span><input max="20" min="1" onChange={(event) => setQuantity(Number(event.target.value))} type="number" value={quantity} /></label>
                </div>
                {data.products.length === 0 ? <p className="participation-empty">Derzeit sind keine Tally-Artikel freigeschaltet.</p> : (
                  <div className="finance-product-grid">
                    {data.products.map((item) => (
                      <button className="finance-product-button" disabled={purchaseMutation.isPending} key={item.id} onClick={() => purchaseMutation.mutate(item.id)} type="button">
                        <span>{item.name}</span><strong>{euros(item.price_cents)}</strong><small>{quantity} × eintragen</small>
                      </button>
                    ))}
                  </div>
                )}
                <p className="finance-help-text">Tally-Zugriff richtet sich nach deiner Vereinsrolle „Mitglied“. Die Beitragsmitgliedschaft und ihr Jahreszyklus werden davon unabhängig verwaltet.</p>
              </section>
            )}

            {(membership || data.charges.length > 0 || data.payments.length > 0) && (
              <>
                <section aria-labelledby="finance-charges-title" className="finance-section">
                  <div className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">TICKETS, TALLY UND BEITRÄGE</p><h2 id="finance-charges-title">Buchungen<span>.</span></h2></div></div>
                  <p className="finance-help-text">Dein Saldo ergibt sich aus allen nicht stornierten Buchungen minus verbuchten Zahlungen. Zugeordnete Zahlungen zeigen zusätzlich, welche Buchungen ganz oder teilweise bezahlt sind; die Zuordnung verändert den Saldo nicht noch einmal.</p>
                  {data.charges.length === 0 ? <p className="participation-empty">Es gibt noch keine Buchungen.</p> : (
                    <div className="finance-ledger-list">
                      {data.charges.map((charge) => <FinanceChargeRow charge={charge} key={charge.uid} />)}
                    </div>
                  )}
                </section>

                {(data.charge_adjustments?.length ?? 0) > 0 && (
                  <section aria-labelledby="finance-charge-adjustments-title" className="finance-section">
                    <div className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">BEITRAGSABGLEICH</p><h2 id="finance-charge-adjustments-title">Beitragsanpassungen<span>.</span></h2></div></div>
                    <div className="finance-membership-history">
                      <ul>
                        {data.charge_adjustments.map((adjustment) => (
                          <li key={adjustment.id}>
                            <div>
                              <strong>{adjustment.charge_name} · {euros(adjustment.from_amount_cents)} → {euros(adjustment.to_amount_cents)}</strong>
                              <small>{chargeAdjustmentSourceLabel(adjustment.source)}{adjustment.note ? ` · ${adjustment.note}` : ""}</small>
                            </div>
                            <span>{adjustment.changed_by_username} · {financeDate(adjustment.changed_at)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </section>
                )}

                <section aria-labelledby="finance-payments-title" className="finance-section">
                  <div className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">ZAHLUNGSHISTORIE</p><h2 id="finance-payments-title">Zahlungen<span>.</span></h2></div></div>
                  {data.payments.length === 0 ? <p className="participation-empty">Es wurden noch keine Zahlungen verbucht.</p> : (
                    <div className="finance-ledger-list">
                      {data.payments.map((payment) => <FinancePaymentRow payment={payment} key={payment.uid} />)}
                    </div>
                  )}
                  {data.payment_instructions && <p className="finance-payment-instructions">{data.payment_instructions}</p>}
                </section>
              </>
            )}
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function FinanceChargeRow({ charge }: { charge: FinanceCharge }) {
  const allocationSummary = chargeAllocationSummary(charge);
  return (
    <article className={`finance-ledger-row finance-ledger-row--${charge.status}`}>
      <div><strong>{chargeTitle(charge)}</strong><small>{chargeDescription(charge)}</small>{allocationSummary && <small>{allocationSummary}</small>}{charge.status_note && <small>{charge.status_note}</small>}</div>
      <span className={`finance-status finance-status--${charge.status}`}>{chargeStatusLabel(charge)}</span>
      <strong>{euros(charge.amount_cents)}</strong>
    </article>
  );
}

function FinancePaymentRow({ payment }: { payment: FinancePayment }) {
  const method = payment.method === "bank_transfer" ? "Überweisung" : payment.method === "cash" ? "Bar" : "Sonstige";
  const allocationChanges = (payment.allocations || []).flatMap((allocation) => {
    const lastChange = allocation.history?.at(-1);
    return lastChange && lastChange.from_amount_cents !== 0
      ? [`${allocation.charge_name}: ${euros(lastChange.from_amount_cents)} → ${euros(lastChange.to_amount_cents)}${lastChange.note ? ` · ${lastChange.note}` : ""}`]
      : [];
  });
  return (
    <article className={`finance-ledger-row${payment.voided_at ? " finance-ledger-row--cancelled" : ""}`}>
      <div>
        <strong>{method}{payment.reference ? ` · ${payment.reference}` : ""}</strong>
        <small>{financeDate(payment.received_at)}{payment.note ? ` · ${payment.note}` : ""}{payment.voided_at ? " · Storniert" : ""}</small>
        {payment.allocations?.filter((allocation) => allocation.active_allocated_cents > 0).map((allocation) => (
          <small key={allocation.charge_uid}>→ {allocation.charge_name}: {euros(allocation.active_allocated_cents)}</small>
        ))}
        {allocationChanges.map((change, index) => <small key={`${payment.uid}-allocation-history-${index}`}>Zuordnung geändert · {change}</small>)}
        {!payment.voided_at && Boolean(payment.unallocated_cents) && <small>Nicht zugeordnet: {euros(payment.unallocated_cents)}</small>}
      </div>
      <span className={`finance-status ${payment.voided_at ? "finance-status--cancelled" : "finance-status--paid"}`}>{payment.voided_at ? "Storniert" : "Verbucht"}</span>
      <strong>− {euros(payment.amount_cents)}</strong>
    </article>
  );
}

type PendingPaymentMatchSuggestion = {
  userUid: string;
  payment: FinancePayment | null;
  suggestion: FinancePaymentMatchSuggestion;
};

type FinanceAdminTab = "members" | "billing" | "products" | "payments" | "event-tickets";

export function AdminFinancePanel({ csrfToken }: { csrfToken: string }) {
  const [tab, setTab] = useState<FinanceAdminTab>("members");
  const financeQuery = useQuery({ queryKey: ["admin-finance"], queryFn: getAdminFinance });
  const [selectedFinanceUserUid, setSelectedFinanceUserUid] = useState("");
  const overview = financeQuery.data;
  const financeUsers = overview?.finance_users?.length
    ? overview.finance_users
    : (overview?.memberships ?? []).map((membership) => ({
      uid: membership.user_uid || membership.uid,
      username: membership.username,
      surname: membership.surname,
      lastname: membership.lastname,
      role: membership.role || "Mitglied",
      email: membership.email,
      email_confirmed: membership.email_confirmed,
      hs_email: membership.hs_email,
      hs_email_confirmed: membership.hs_email_confirmed,
      membership_uid: membership.uid,
      membership_status: membership.status,
      fee_category: membership.fee_category,
      balance_cents: membership.balance_cents || 0,
      can_use_tally: true,
    }));
  const tabs: Array<{ id: FinanceAdminTab; label: string; badge?: number }> = [
    { id: "members", label: "Beitragsmitgliedschaften & Anträge", badge: overview?.requests.length ?? 0 },
    { id: "billing", label: "Jahresbeiträge" },
    { id: "products", label: "Tally-Artikel" },
    { id: "payments", label: "Salden & Zahlungen" },
    { id: "event-tickets", label: "Eventtickets" },
  ];

  return (
    <section aria-labelledby="admin-finance-title" className="admin-finance-panel">
      <header className="finance-section__heading">
        <div><p className="eyebrow eyebrow--muted">MITGLIEDERKONTO</p><h2 id="admin-finance-title">Finanzen<span>.</span></h2></div>
      </header>
      {financeQuery.isLoading && <p className="participation-empty" role="status">Finanzdaten werden geladen …</p>}
      {financeQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Finanzdaten konnten nicht geladen werden.</p>}
      {overview && (
        <>
          <div aria-label="Finanzverwaltung" className="finance-admin-tabs" role="tablist">
            {tabs.map((item) => <button aria-selected={tab === item.id} className={tab === item.id ? "finance-admin-tab finance-admin-tab--active" : "finance-admin-tab"} key={item.id} onClick={() => setTab(item.id)} role="tab" type="button">{item.label}{Boolean(item.badge) && <span aria-hidden="true" className="admin-tab-indicator">{item.badge}</span>}</button>)}
          </div>
          <div className="finance-admin-tab-panel" role="tabpanel">
            {tab === "members" && <AdminMembershipsTab csrfToken={csrfToken} overview={overview} onSelectMember={(uid) => { setSelectedFinanceUserUid(uid); setTab("payments"); }} />}
            {tab === "billing" && <AdminBillingTab csrfToken={csrfToken} />}
            {tab === "products" && <AdminProductsTab csrfToken={csrfToken} overview={overview} />}
            {tab === "payments" && <AdminPaymentsTab csrfToken={csrfToken} instructions={overview.payment_instructions} mailTestEmail={overview.mail_test_email || ""} financeUsers={financeUsers} selectedUid={selectedFinanceUserUid} />}
            {tab === "event-tickets" && <AdminEventTicketsTab csrfToken={csrfToken} />}
          </div>
        </>
      )}
    </section>
  );
}

function AdminMembershipsTab({
  csrfToken,
  overview,
  onSelectMember,
}: {
  csrfToken: string;
  overview: FinanceAdminOverview;
  onSelectMember: (uid: string) => void;
}) {
  const queryClient = useQueryClient();
  const [userUid, setUserUid] = useState(overview.available_users[0]?.uid || "");
  const [feeCategory, setFeeCategory] = useState<FeeCategory>("student");
  const [memberSince, setMemberSince] = useState(new Date().toISOString().slice(0, 10));
  const [specialRate, setSpecialRate] = useState("");
  const [editingMembership, setEditingMembership] = useState<FinanceMembership | null>(null);
  const [editFeeCategory, setEditFeeCategory] = useState<FeeCategory>("student");
  const [editSpecialRate, setEditSpecialRate] = useState("");
  const [editSpecialRateValidUntil, setEditSpecialRateValidUntil] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const createMutation = useMutation({
    mutationFn: () => createFinanceMembership(
      userUid,
      feeCategory,
      memberSince,
      feeCategory === "special" ? Math.round(Number(specialRate) * 100) : null,
      csrfToken,
    ),
    onSuccess: async () => {
      setNotice("Beitragsmitgliedschaft wurde angelegt.");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["admin-finance"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragsmitgliedschaft konnte nicht angelegt werden."),
  });
  const statusMutation = useMutation({
    mutationFn: ({ membership, status }: { membership: FinanceMembership; status: "active" | "ended" }) =>
      updateFinanceMembership(membership.uid, {
        status,
        fee_category: membership.fee_category,
        member_since: membership.member_since || new Date().toISOString().slice(0, 10),
        special_rate_cents: membership.special_rate_cents,
        special_rate_valid_until: membership.special_rate_valid_until,
      }, csrfToken),
    onSuccess: async (_, values) => {
      setNotice(values.status === "ended" ? "Beitragsmitgliedschaft wurde beendet." : "Beitragsmitgliedschaft wurde reaktiviert.");
      await queryClient.invalidateQueries({ queryKey: ["admin-finance"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragsmitgliedschaftsstatus konnte nicht geändert werden."),
  });
  const updateMembershipMutation = useMutation({
    mutationFn: () => {
      if (!editingMembership) throw new Error("Wähle zuerst ein Mitglied aus.");
      return updateFinanceMembership(editingMembership.uid, {
        fee_category: editFeeCategory,
        status: editingMembership.status,
        member_since: editingMembership.member_since || new Date().toISOString().slice(0, 10),
        special_rate_cents: editFeeCategory === "special" ? Math.round(Number(editSpecialRate) * 100) : null,
        special_rate_valid_until: editFeeCategory === "special" ? editSpecialRateValidUntil || null : null,
        note: changeNote,
      }, csrfToken);
    },
    onSuccess: async (result) => {
      setNotice(`Beitragskategorie wurde geändert. ${feeRecalculationSummary(result.fee_adjustments || [])}`);
      setError("");
      setEditingMembership(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-finance"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragskategorie konnte nicht geändert werden."),
  });

  function editFee(membership: FinanceMembership) {
    setEditingMembership(membership);
    setEditFeeCategory(membership.fee_category);
    setEditSpecialRate(membership.special_rate_cents == null ? "" : (membership.special_rate_cents / 100).toFixed(2));
    setEditSpecialRateValidUntil(membership.special_rate_valid_until || "");
    setChangeNote("");
    setError("");
  }

  return (
    <div className="finance-admin-content">
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">ROSTER</p><h3>Beitragsmitgliedschaft hinzufügen</h3></div></header>
        {overview.available_users.length === 0 ? <p className="participation-empty">Alle vorhandenen Konten haben bereits eine Beitragsmitgliedschaft.</p> : (
          <form className="manager-form-grid" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
            <label className="profile-field">
              <span>Konto auswählen</span>
              <select onChange={(event) => setUserUid(event.target.value)} required value={userUid}>
                {overview.available_users.map((user) => <option key={user.uid} value={user.uid}>{[user.surname, user.lastname].filter(Boolean).join(" ") || user.username} (@{user.username} · {user.role})</option>)}
              </select>
            </label>
            <label className="profile-field"><span>Beitragskategorie</span><select onChange={(event) => setFeeCategory(event.target.value as FeeCategory)} value={feeCategory}>{adminFeeCategories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label className="profile-field"><span>Eintrittsdatum</span><input onChange={(event) => setMemberSince(event.target.value)} required type="date" value={memberSince} /></label>
            {feeCategory === "special" && <label className="profile-field"><span>Sonderbeitrag pro Jahr (€)</span><input min="0" onChange={(event) => setSpecialRate(event.target.value)} required step="0.01" type="number" value={specialRate} /></label>}
            <button className="participation-button" disabled={createMutation.isPending} type="submit">{createMutation.isPending ? "Wird angelegt …" : "Beitragsmitgliedschaft anlegen"}</button>
          </form>
        )}
      </section>

      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">OFFENE ENTSCHEIDUNGEN</p><h3>Beitragsmitgliedschaftsanträge</h3></div><span className="admin-count-badge">{overview.requests.length}</span></header>
        {overview.requests.length === 0 ? <p className="participation-empty">Es gibt keine offenen Anträge.</p> : (
          <div className="finance-request-list">
            {overview.requests.map((item) => <MembershipRequestCard csrfToken={csrfToken} item={item} key={item.uid} />)}
          </div>
        )}
      </section>

      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">BEITRAGSMITGLIEDSCHAFTEN</p><h3>Mitgliederkonto</h3></div></header>
        <div className="finance-table-scroll">
          <table className="finance-table">
            <thead><tr><th>Mitglied</th><th>Kategorie</th><th>Status</th><th>Saldo</th><th>Beitritt</th><th>Aktionen</th></tr></thead>
            <tbody>
              {overview.memberships.map((membership) => (
                <tr key={membership.uid}>
                  <td><strong>{memberDisplayName(membership)}</strong><small>@{membership.username}</small></td>
                  <td>{feeCategoryLabel(membership.fee_category)}</td>
                  <td><span className={`finance-status finance-status--${membership.status}`}>{membership.status === "active" ? "Aktiv" : "Beendet"}</span></td>
                  <td>{euros(membership.balance_cents)}</td>
                  <td>{membership.member_since || "—"}</td>
                    <td className="finance-table__actions">
                      <button className="text-button" onClick={() => onSelectMember(membership.user_uid || membership.uid)} type="button">Konto</button>
                      <button className="text-button" onClick={() => editFee(membership)} type="button">Beitragsklasse</button>
                      <button className="text-button" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate({ membership, status: membership.status === "active" ? "ended" : "active" })} type="button">{membership.status === "active" ? "Beenden" : "Reaktivieren"}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {editingMembership && (
        <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditingMembership(null); }}>
          <section aria-labelledby="finance-category-edit-title" aria-modal="true" className="admin-edit-dialog" role="dialog">
            <header className="admin-edit-dialog__heading">
              <div><p className="eyebrow eyebrow--muted">DIREKTE ADMIN-ÄNDERUNG</p><h2 id="finance-category-edit-title">Beitragsklasse für {editingMembership.username}</h2></div>
              <button aria-label="Schließen" className="dialog-close" onClick={() => setEditingMembership(null)} type="button">×</button>
            </header>
            <p className="finance-help-text">Diese Änderung erfordert keinen Antrag des Mitglieds und wird mit Bearbeiter, Zeitpunkt und Notiz protokolliert. Die bestätigte Hochschul-E-Mail wird für den Student:innenbeitrag weiterhin pro Beitragszyklus benötigt.</p>
            <form className="admin-edit-form" onSubmit={(event) => { event.preventDefault(); updateMembershipMutation.mutate(); }}>
              <div className="manager-form-grid">
                <label className="profile-field"><span>Beitragsklasse</span><select onChange={(event) => setEditFeeCategory(event.target.value as FeeCategory)} value={editFeeCategory}>{adminFeeCategories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                {editFeeCategory === "special" && (
                  <>
                    <label className="profile-field"><span>Sonderbeitrag pro Jahr (€)</span><input min="0" onChange={(event) => setEditSpecialRate(event.target.value)} required step="0.01" type="number" value={editSpecialRate} /></label>
                    <label className="profile-field"><span>Gültig bis (optional)</span><input onChange={(event) => setEditSpecialRateValidUntil(event.target.value)} type="date" value={editSpecialRateValidUntil} /></label>
                  </>
                )}
                <label className="profile-field manager-form-grid__wide"><span>Änderungsnotiz</span><input maxLength={500} onChange={(event) => setChangeNote(event.target.value)} required value={changeNote} /></label>
              </div>
              <div className="admin-edit-dialog__actions"><button className="participation-button" disabled={updateMembershipMutation.isPending} type="submit">{updateMembershipMutation.isPending ? "Wird gespeichert …" : "Beitragsklasse speichern"}</button><button className="participation-button participation-button--quiet" onClick={() => setEditingMembership(null)} type="button">Abbrechen</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

function MembershipRequestCard({ csrfToken, item }: { csrfToken: string; item: MembershipRequest }) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<FeeCategory>(item.requested_category);
  const [specialRate, setSpecialRate] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: (decision: "approve" | "reject") => reviewMembershipRequest(item.id, decision, {
      fee_category: category,
      special_rate_cents: category === "special" ? Math.round(Number(specialRate) * 100) : undefined,
      member_since: new Date().toISOString().slice(0, 10),
      note,
    }, csrfToken),
    onSuccess: async () => {
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["admin-finance"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Anfrage konnte nicht bearbeitet werden."),
  });

  return (
    <article className="finance-request-card">
      <div className="finance-request-card__identity">
        <div><strong>{[item.surname, item.lastname].filter(Boolean).join(" ") || item.username}</strong><small>@{item.username} · {item.request_type === "join" ? "Beitragsmitgliedschaftsantrag" : "Beitragskategorieänderung"} · {financeDate(item.submitted_at)}</small></div>
        <span className="admin-user-card__role">{feeCategoryLabel(item.requested_category)}</span>
      </div>
      {item.request_note && <p>{item.request_note}</p>}
      <div className="manager-form-grid">
        <label className="profile-field"><span>Genehmigte Kategorie</span><select onChange={(event) => setCategory(event.target.value as FeeCategory)} value={category}>{adminFeeCategories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        {category === "special" && <label className="profile-field"><span>Sonderbeitrag pro Jahr (€)</span><input min="0" onChange={(event) => setSpecialRate(event.target.value)} required step="0.01" type="number" value={specialRate} /></label>}
        <label className="profile-field"><span>Prüfnotiz</span><input maxLength={500} onChange={(event) => setNote(event.target.value)} value={note} /></label>
      </div>
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      <div className="finance-inline-actions">
        <button className="participation-button" disabled={mutation.isPending} onClick={() => mutation.mutate("approve")} type="button">Genehmigen</button>
        <button className="text-button text-button--danger" disabled={mutation.isPending} onClick={() => mutation.mutate("reject")} type="button">Ablehnen</button>
      </div>
    </article>
  );
}

function AdminBillingTab({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const today = new Date();
  const month = today.getMonth() + 1;
  const initialPeriod: BillingPeriod = month >= 3 && month <= 9 ? "september" : "march";
  const initialYear = month >= 10 ? today.getFullYear() + 1 : today.getFullYear();
  const [cycleYear, setCycleYear] = useState(initialYear);
  const [period, setPeriod] = useState<BillingPeriod>(initialPeriod);
  const previewQuery = useQuery({ queryKey: ["finance-billing-preview", cycleYear, period], queryFn: () => getBillingPreview(cycleYear, period) });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [runToVoid, setRunToVoid] = useState<FinanceBillingRun | null>(null);
  const [showVerificationComposer, setShowVerificationComposer] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const runMutation = useMutation({
    mutationFn: () => createBillingRun(cycleYear, period, csrfToken),
    onSuccess: async (result) => {
      setNotice(`${result.period === "march" ? "März" : "September"}-Beitragslauf ${result.cycle_year}: ${result.created_count} Buchungen über ${euros(result.total_cents)} erstellt.`);
      setError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-billing-preview", cycleYear, period] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragslauf konnte nicht erstellt werden."),
  });
  const voidMutation = useMutation({
    mutationFn: () => {
      if (!runToVoid) throw new Error("Wähle zuerst einen Beitragslauf aus.");
      return voidFinanceBillingRun(runToVoid.id, voidReason, csrfToken);
    },
    onSuccess: async (result) => {
      setNotice(`Beitragslauf #${result.run.run_number} storniert; ${result.voided_charge_count} Buchungen archiviert. Account-Zahlungen bleiben erhalten.`);
      setError("");
      setRunToVoid(null);
      setVoidReason("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-billing-preview", cycleYear, period] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragslauf konnte nicht storniert werden."),
  });
  const preview = previewQuery.data;
  const requiresReview = preview?.members.some((member) => member.needs_admin_review && !member.already_billed) ?? false;
  const nextRunNumber = Math.max(0, ...(preview?.runs.map((run) => run.run_number) ?? [])) + 1;

  return (
    <div className="finance-admin-content">
      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">{period === "march" ? "MÄRZ-ZYKLUS" : "SEPTEMBER-ZYKLUS"}</p><h3>Mitgliedsbeiträge vorbereiten</h3></div></header>
        <p className="finance-help-text">Der März-Lauf berechnet Jahresbeiträge und den ersten Wintersemesteranteil für verifizierte Studierende. Der September-Lauf berechnet den Sommersemesteranteil. Studierende können durch eine höhere Zahlung Guthaben aufbauen; dieses wird automatisch mit späteren Buchungen verrechnet.</p>
        <div className="manager-form-grid">
          <label className="profile-field"><span>Abrechnungslauf</span><select onChange={(event) => setPeriod(event.target.value as BillingPeriod)} value={period}><option value="march">März · Jahresbeiträge / Wintersemester</option><option value="september">September · Sommersemester</option></select></label>
          <label className="profile-field finance-year-field"><span>Beitragsjahr</span><input max={new Date().getFullYear() + 5} min="2020" onChange={(event) => setCycleYear(Number(event.target.value))} type="number" value={cycleYear} /></label>
        </div>
        {notice && <p className="action-feedback" role="status">{notice}</p>}
        {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
        {previewQuery.isLoading && <p className="participation-empty" role="status">Beitragslauf wird berechnet …</p>}
        {previewQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Vorschau konnte nicht geladen werden.</p>}
        {preview && (
          <>
            <div className="finance-summary-strip"><span>Fällig am <strong>{preview.due_date}</strong></span><span>Vorgeschlagene Buchungen <strong>{preview.charge_count}</strong></span><span>Summe <strong>{euros(preview.total_to_issue_cents)}</strong></span></div>
            {preview.runs.length > 0 && (
              <section aria-labelledby="finance-run-history-title" className="finance-run-history">
                <header><h4 id="finance-run-history-title">Beitragslauf-Historie</h4><span>{preview.runs.length} Lauf/Läufe</span></header>
                {preview.runs.map((run) => (
                  <article className="finance-run-card" key={run.id}>
                    <div className="finance-run-card__summary">
                       <div><strong>{run.period === "september" ? "September" : "März"} · Lauf #{run.run_number} · {run.status === "issued" ? "Aktiv" : "Storniert"}</strong><small>Erstellt {financeDate(run.created_at)} von {run.created_by_username} · Fällig {run.due_date}</small></div>
                      <span>{euros(run.issued_amount_cents)} · {run.charge_count} Buchungen</span>
                    </div>
                    {run.status === "voided" ? (
                      <p className="finance-run-card__reason">Storniert {run.voided_at ? `am ${financeDate(run.voided_at)}` : ""}{run.voided_by_username ? ` von ${run.voided_by_username}` : ""}: {run.void_reason}</p>
                    ) : (
                      <>
                        {run.affected_members.length > 0 && <p className="finance-run-card__impact">Bei Stornierung werden noch <strong>{run.open_charge_count}</strong> nicht stornierte Buchungen über <strong>{euros(run.open_amount_cents)}</strong> aus dem Soll genommen. Account-Zahlungen bleiben erhalten; ein Guthaben kann entstehen.</p>}
                        <button className="text-button text-button--danger" disabled={voidMutation.isPending} onClick={() => { setRunToVoid(run); setVoidReason(""); setError(""); }} type="button">Beitragslauf stornieren</button>
                      </>
                    )}
                  </article>
                ))}
              </section>
            )}
            {requiresReview && <p className="action-feedback action-feedback--error" role="alert">Ein oder mehrere Sonderbeiträge benötigen erst einen genehmigten Betrag.</p>}
            <button className="participation-button participation-button--quiet" onClick={() => setShowVerificationComposer(true)} type="button">
              Studentenbestätigungen vorbereiten
            </button>
            <div className="finance-table-scroll">
              <table className="finance-table">
                <thead><tr><th>Mitglied</th><th>Beitragskategorie</th><th>Beitrag</th><th>Grund</th><th>Status</th></tr></thead>
                <tbody>
                  {preview.members.map((member) => (
                    <tr key={member.membership.uid}>
                    <td><strong>{memberDisplayName(member.membership)}</strong><small>@{member.membership.username}</small></td>
                      <td>{feeCategoryLabel(member.effective_category)}</td>
                      <td>{member.amount_cents === null ? "Betrag fehlt" : euros(member.amount_cents)}</td>
                      <td>{member.reason}</td>
                      <td>{member.already_billed
                        ? member.existing_status === "cancelled"
                          ? "Storniert"
                          : member.existing_status === "waived"
                            ? "Beitragsfrei"
                            : member.existing_period
                              ? `Bereits im ${member.existing_period === "march" ? "März" : "September"}-Lauf erstellt`
                              : "Bereits erstellt"
                        : member.not_eligible
                          ? "Nicht in diesem Lauf"
                          : member.amount_cents === 0 ? "Beitragsfrei" : "Vorschau"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="participation-button" disabled={runMutation.isPending || preview.run_created || preview.charge_count === 0 || requiresReview} onClick={() => runMutation.mutate()} type="button">
              {runMutation.isPending ? "Wird erstellt …" : `Beitragslauf #${nextRunNumber} erstellen`}
            </button>
          </>
        )}
      </section>
      <FinanceMailCampaignHistory kind="student_verification" />
      <FinanceRatesEditor csrfToken={csrfToken} />
      {showVerificationComposer && (
        <FinanceMailComposer
          csrfToken={csrfToken}
          kind="student_verification"
          onClose={() => setShowVerificationComposer(false)}
          onSent={(message) => {
            setNotice(message);
            void queryClient.invalidateQueries({ queryKey: ["finance-billing-preview", cycleYear, period] });
          }}
          suggestedCycleYear={cycleYear}
        />
      )}
      {runToVoid && (
        <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setRunToVoid(null); }}>
          <section aria-labelledby="void-billing-run-title" aria-modal="true" className="admin-edit-dialog finance-void-dialog" role="dialog">
            <header className="admin-edit-dialog__heading">
              <div><p className="eyebrow eyebrow--muted">BEITRAGSLAUF #{runToVoid.run_number}</p><h2 id="void-billing-run-title">Beitragslauf stornieren</h2></div>
              <button aria-label="Schließen" className="dialog-close" onClick={() => setRunToVoid(null)} type="button">×</button>
            </header>
            <p>Der Lauf und seine Buchungen bleiben in der Historie. Nicht stornierte Buchungen werden storniert. Account-Zahlungen bleiben erhalten und werden nicht einzelnen Gebühren zugeordnet.</p>
            {runToVoid.affected_members.length > 0 && (
              <div className="finance-void-impact">
                <h3>Voraussichtliche Salden</h3>
                {runToVoid.affected_members.map((member) => (
                  <p key={member.membership_uid}><strong>{member.username}</strong>: {euros(member.current_balance_cents)} → {euros(member.balance_after_void_cents)}{member.balance_after_void_cents < 0 ? " Guthaben" : ""}</p>
                ))}
              </div>
            )}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
            <form onSubmit={(event) => { event.preventDefault(); voidMutation.mutate(); }}>
              <label className="profile-field"><span>Grund für die Stornierung</span><textarea maxLength={1000} minLength={3} onChange={(event) => setVoidReason(event.target.value)} required rows={3} value={voidReason} /></label>
              <div className="admin-edit-dialog__actions"><button className="participation-button participation-button--quiet" onClick={() => setRunToVoid(null)} type="button">Abbrechen</button><button className="text-button text-button--danger" disabled={voidMutation.isPending} type="submit">{voidMutation.isPending ? "Wird storniert …" : "Lauf stornieren"}</button></div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}

function mailKindTitle(kind: FinanceMailKind) {
  return kind === "payment_reminder" ? "Zahlungserinnerungen" : "Studentenbestätigungen";
}

function mailReasonLabel(reason: string) {
  const labels: Record<string, string> = {
    no_positive_balance: "Kein positiver offener Saldo",
    below_threshold: "Saldo unter dem gewählten Mindestbetrag",
    no_confirmed_email: "Keine bestätigte E-Mail-Adresse",
    missing_hs_email: "Keine Hochschul-E-Mail hinterlegt",
    already_verified: "Für diese Adresse bereits bestätigt",
    cooldown: "Vor weniger als fünf Minuten bereits angefordert",
  };
  return labels[reason] || reason;
}

function mailOutcomeLabel(status: string) {
  const labels: Record<string, string> = {
    sending: "Versand läuft",
    completed: "Abgeschlossen",
    failed: "Versand fehlgeschlagen",
    legacy: "Historisch erfasst · Zustellung unbekannt",
    queued: "In Warteschlange",
    accepted: "Vom Mailserver angenommen",
    skipped: "Übersprungen",
    excluded: "Von der Verwaltung abgewählt",
    legacy_attempted: "Versandversuch gestartet · Ergebnis unbekannt",
  };
  return labels[status] || status;
}

function mailTextSnapshot(body: string) {
  return body
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'");
}

function FinanceMailCampaignHistory({ kind }: { kind: FinanceMailKind }) {
  const [expandedUid, setExpandedUid] = useState("");
  const campaignsQuery = useQuery({
    queryKey: ["finance-mail-campaigns", kind],
    queryFn: () => getFinanceMailCampaigns(kind),
    refetchInterval: (query) => query.state.data?.campaigns.some((campaign) => campaign.status === "sending") ? 2000 : false,
  });
  const detailQuery = useQuery({
    queryKey: ["finance-mail-campaign", expandedUid],
    queryFn: () => getFinanceMailCampaign(expandedUid),
    enabled: Boolean(expandedUid),
    refetchInterval: (query) => query.state.data?.campaign.status === "sending" ? 2000 : false,
  });

  return (
    <section aria-labelledby={`finance-mail-history-${kind}`} className="finance-admin-section finance-mail-history">
      <header className="finance-section__heading">
        <div><p className="eyebrow eyebrow--muted">VERSANDPROTOKOLL</p><h3 id={`finance-mail-history-${kind}`}>Mailverlauf · {mailKindTitle(kind)}</h3></div>
        <button className="text-button" disabled={campaignsQuery.isFetching} onClick={() => { void campaignsQuery.refetch(); }} type="button">Verlauf aktualisieren</button>
      </header>
      {campaignsQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Der Mailverlauf konnte nicht geladen werden.</p>}
      {campaignsQuery.isLoading && <p className="participation-empty" role="status">Mailverlauf wird geladen …</p>}
      {campaignsQuery.data?.campaigns.length === 0 && <p className="participation-empty">Für diesen E-Mail-Typ gibt es noch keine gespeicherten Kampagnen.</p>}
      <div className="finance-mail-history__list">
        {campaignsQuery.data?.campaigns.map((campaign) => (
          <article className="finance-mail-campaign-card" key={campaign.uid}>
            <div className="finance-mail-campaign-card__summary">
              <div>
                <strong>{campaign.test_only ? "Testmail · " : ""}{campaign.subject_template || mailKindTitle(kind)}</strong>
                <small>
                  {financeDate(campaign.created_at)} · {campaign.created_by_username || "Gelöschtes Konto"}
                  {campaign.cycle_year ? ` · Beitragsjahr ${campaign.cycle_year}` : ""}
                  {campaign.minimum_balance_cents !== null ? ` · Mindestbetrag ${euros(campaign.minimum_balance_cents)}` : ""}
                </small>
              </div>
              <span className={`finance-status finance-status--${campaign.status === "failed" ? "cancelled" : campaign.status === "sending" ? "open" : "paid"}`}>
                {mailOutcomeLabel(campaign.status)}
              </span>
            </div>
            <div className="finance-mail-campaign-card__counts">
              <span>{campaign.counts.selected ?? campaign.counts.queued ?? campaign.recipient_count} ausgewählt</span>
              {Object.entries(campaign.recipient_status_counts).map(([status, count]) => (
                <span key={status}>{count} {mailOutcomeLabel(status).toLowerCase()}</span>
              ))}
              {Number(campaign.counts.no_positive_balance || 0) > 0 && <span>{campaign.counts.no_positive_balance} ohne positiven Saldo</span>}
              {Number(campaign.counts.skipped_below_threshold || 0) > 0 && <span>{campaign.counts.skipped_below_threshold} unter Mindestbetrag</span>}
              {Number(campaign.counts.no_confirmed_email || 0) > 0 && <span>{campaign.counts.no_confirmed_email} ohne bestätigte E-Mail</span>}
            </div>
            <button className="text-button" onClick={() => setExpandedUid((current) => current === campaign.uid ? "" : campaign.uid)} type="button">
              {expandedUid === campaign.uid ? "Details schließen" : "Empfänger:innen und Mail ansehen"}
            </button>
            {expandedUid === campaign.uid && (
              <div className="finance-mail-campaign-card__details">
                {detailQuery.isFetching && <p className="participation-empty" role="status">Kampagnendetails werden geladen …</p>}
                {detailQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Kampagnendetails konnten nicht geladen werden.</p>}
                {detailQuery.data?.campaign.uid === campaign.uid && (
                  <>
                    {campaign.status === "legacy" && <p className="finance-help-text">Der frühere Datensatz zeigt, dass ein Versandversuch gestartet wurde. Ein tatsächlicher Mailserver-Status wurde damals nicht gespeichert.</p>}
                    <div className="finance-mail-campaign-card__copy">
                      <strong>{detailQuery.data.campaign.subject_template || "Betreff nicht gespeichert"}</strong>
                      <pre>{campaign.status === "legacy"
                        ? "Der damalige Nachrichtentext wurde nicht gespeichert."
                        : mailTextSnapshot(detailQuery.data.campaign.body_template || "")}</pre>
                    </div>
                    <div className="finance-mail-history__recipients">
                      {detailQuery.data.recipients.map((recipient, index) => (
                        <article className="finance-mail-history-recipient" key={`${recipient.key}-${index}`}>
                          <div>
                            <strong>{recipient.display_name || recipient.username || "Testadresse"}</strong>
                            <small>{recipient.username ? `@${recipient.username} · ` : ""}{recipient.email || "Keine Empfängeradresse"}</small>
                            {recipient.balance_cents !== null && <small>Saldo zum Versandzeitpunkt: {euros(recipient.balance_cents)}</small>}
                            {recipient.reason && <small>{recipient.reason}</small>}
                            {recipient.error_message && <small className="auth-field-error">{recipient.error_message}</small>}
                            {recipient.body && <details className="finance-mail-recipient-copy"><summary>Gesendete E-Mail ansehen</summary><strong>{recipient.subject}</strong><pre>{mailTextSnapshot(recipient.body)}</pre></details>}
                          </div>
                          <span className={`finance-status finance-status--${recipient.status === "failed" ? "cancelled" : recipient.status === "accepted" || recipient.status === "legacy_attempted" ? "paid" : recipient.status === "queued" ? "open" : "ended"}`}>
                            {mailOutcomeLabel(recipient.status)}
                          </span>
                        </article>
                      ))}
                      {detailQuery.data.recipients.length === 0 && <p className="participation-empty">Keine Empfänger:innen gespeichert.</p>}
                    </div>
                  </>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function FinanceMailComposer({
  kind,
  csrfToken,
  scopeUserUid,
  suggestedCycleYear,
  onClose,
  onSent,
}: {
  kind: FinanceMailKind;
  csrfToken: string;
  scopeUserUid?: string;
  suggestedCycleYear?: number;
  onClose: () => void;
  onSent: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const draftQuery = useQuery({
    queryKey: ["finance-mail-draft", kind],
    queryFn: () => getFinanceMailDraft(kind),
  });
  const [draft, setDraft] = useState<FinanceMailDraft | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [minimumBalance, setMinimumBalance] = useState("0");
  const [cycleYear, setCycleYear] = useState(suggestedCycleYear || new Date().getFullYear());
  const [selectedKeys, setSelectedKeys] = useState<string[] | null>(null);
  const [preview, setPreview] = useState<FinanceMailPreview | null>(null);
  const [previewStale, setPreviewStale] = useState(true);
  const [showSendConfirmation, setShowSendConfirmation] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!draftQuery.data?.draft || draft) return;
    const loaded = draftQuery.data.draft;
    setDraft(loaded);
    setSubject(loaded.subject_template);
    setBody(loaded.body_template);
    setMinimumBalance((loaded.minimum_balance_cents / 100).toFixed(2));
    setCycleYear(loaded.cycle_year || suggestedCycleYear || new Date().getFullYear());
    setSelectedKeys(scopeUserUid ? null : loaded.selected_recipient_keys);
  }, [draftQuery.data, draft, scopeUserUid, suggestedCycleYear]);

  const saveDraft = useMutation({
    mutationFn: (values: Parameters<typeof saveFinanceMailDraft>[1]) => saveFinanceMailDraft(kind, values, csrfToken),
    onSuccess: ({ draft: saved }) => {
      setDraft(saved);
      setSubject(saved.subject_template);
      setBody(saved.body_template);
      setMinimumBalance((saved.minimum_balance_cents / 100).toFixed(2));
      if (kind === "student_verification" && saved.cycle_year) setCycleYear(saved.cycle_year);
      if (!scopeUserUid) setSelectedKeys(saved.selected_recipient_keys);
      setError("");
      queryClient.setQueryData(["finance-mail-draft", kind], (current: { draft: FinanceMailDraft; mail_test_email: string } | undefined) => current ? { ...current, draft: saved } : current);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Der gemeinsame Entwurf konnte nicht gespeichert werden."),
  });

  const testMutation = useMutation({
    mutationFn: (version: number) => testFinanceMailDraft(kind, version, csrfToken),
    onSuccess: async (result) => {
      setNotice(`Testmail wurde an ${result.recipient_email} zur Übermittlung eingereiht. Das Ergebnis erscheint im Mailverlauf.`);
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["finance-mail-campaigns", kind] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Die Testmail konnte nicht eingereiht werden."),
  });

  const sendMutation = useMutation({
    mutationFn: ({ version, recipients }: { version: number; recipients: string[] }) => sendFinanceMailDraft(
      kind,
      version,
      recipients,
      csrfToken,
      scopeUserUid,
    ),
    onSuccess: async (result) => {
      setShowSendConfirmation(false);
      const label = kind === "payment_reminder" ? "Zahlungserinnerung" : "Studentenbestätigung";
      onSent(`${label}: ${result.selected} Mail(s) wurden zur Übermittlung eingereiht. Die einzelnen Ergebnisse stehen im Mailverlauf.`);
      await queryClient.invalidateQueries({ queryKey: ["finance-mail-campaigns", kind] });
      onClose();
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Die Kampagne konnte nicht gestartet werden."),
  });

  async function persistDraft() {
    if (!draft) throw new Error("Der gemeinsame Entwurf wird noch geladen.");
    const thresholdCents = kind === "payment_reminder" ? Math.round(Number(minimumBalance) * 100) : 0;
    if (!Number.isFinite(thresholdCents) || thresholdCents < 0) throw new Error("Bitte gib einen gültigen Mindestbetrag ein.");
    const selectionToSave = scopeUserUid ? draft.selected_recipient_keys : selectedKeys;
    const sameSelection = JSON.stringify(selectionToSave) === JSON.stringify(draft.selected_recipient_keys);
    const sameCycle = kind !== "student_verification" || (draft.cycle_year || suggestedCycleYear) === cycleYear;
    const sameDraft = draft.subject_template === subject
      && draft.body_template === body
      && draft.minimum_balance_cents === thresholdCents
      && sameCycle
      && sameSelection;
    if (sameDraft) return draft;
    const result = await saveDraft.mutateAsync({
      version: draft.version,
      subject_template: subject,
      body_template: body,
      minimum_balance_cents: thresholdCents,
      cycle_year: kind === "student_verification" ? cycleYear : null,
      selected_recipient_keys: selectionToSave,
    });
    setPreviewStale(true);
    return result.draft;
  }

  async function refreshPreview(): Promise<FinanceMailPreview | null> {
    setError("");
    setNotice("");
    try {
      const saved = await persistDraft();
      const result = await previewFinanceMailDraft(kind, saved.version, csrfToken, scopeUserUid);
      setPreview(result);
      if (scopeUserUid) {
        setSelectedKeys(null);
      } else if (result.draft.selected_recipient_keys !== null) {
        setSelectedKeys(result.candidates.filter((candidate) => candidate.selected).map((candidate) => candidate.key));
      } else {
        setSelectedKeys(null);
      }
      setPreviewStale(false);
      return result;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Die Empfängervorschau konnte nicht geladen werden.");
      return null;
    }
  }

  function candidateSelected(candidate: FinanceMailCandidate) {
    if (scopeUserUid) return candidate.selected;
    return selectedKeys === null ? candidate.selected : selectedKeys.includes(candidate.key);
  }

  function toggleCandidate(candidate: FinanceMailCandidate) {
    if (!candidate.can_select || scopeUserUid) return;
    setSelectedKeys((current) => {
      const currentSelection = current ?? (preview?.candidates.filter((item) => item.selected).map((item) => item.key) || []);
      return currentSelection.includes(candidate.key)
        ? currentSelection.filter((key) => key !== candidate.key)
        : [...currentSelection, candidate.key];
    });
  }

  function selectThresholdDefault() {
    if (!preview || scopeUserUid) return;
    setSelectedKeys(preview.candidates.filter((candidate) => candidate.default_selected).map((candidate) => candidate.key));
  }

  function selectedKeysForPreview(currentPreview: FinanceMailPreview) {
    if (scopeUserUid || selectedKeys === null) {
      return currentPreview.candidates.filter((candidate) => candidate.selected).map((candidate) => candidate.key);
    }
    return currentPreview.candidates
      .filter((candidate) => candidate.can_select && selectedKeys.includes(candidate.key))
      .map((candidate) => candidate.key);
  }

  async function sendTestEmail() {
    setError("");
    try {
      const saved = await persistDraft();
      testMutation.mutate(saved.version);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Der Entwurf konnte nicht gespeichert werden.");
    }
  }

  async function openSendConfirmation() {
    setError("");
    const currentPreview = !preview || previewStale ? await refreshPreview() : preview;
    if (!currentPreview) return;
    if (selectedKeysForPreview(currentPreview).length === 0) {
      setError("Es sind keine aktuell berechtigten Empfänger:innen ausgewählt.");
      return;
    }
    setShowSendConfirmation(true);
  }

  async function confirmSend() {
    setError("");
    try {
      const reviewedKeys = preview ? selectedKeysForPreview(preview) : [];
      const saved = await persistDraft();
      const freshPreview = await previewFinanceMailDraft(kind, saved.version, csrfToken, scopeUserUid);
      const freshSelected = freshPreview.candidates.filter((candidate) => candidate.selected).map((candidate) => candidate.key);
      if (reviewedKeys.length !== freshSelected.length || reviewedKeys.some((key) => !freshSelected.includes(key))) {
        setPreview(freshPreview);
        if (!scopeUserUid) setSelectedKeys(freshSelected);
        setPreviewStale(false);
        setShowSendConfirmation(false);
        setError("Empfängerauswahl oder Kontostand hat sich seit der Vorschau geändert. Bitte prüfe die aktualisierte Liste und bestätige erneut.");
        return;
      }
      if (freshSelected.length === 0) {
        setShowSendConfirmation(false);
        setError("Es sind keine Empfänger:innen ausgewählt.");
        return;
      }
      sendMutation.mutate({ version: saved.version, recipients: freshSelected });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Die Empfängerauswahl konnte nicht geprüft werden.");
    }
  }

  const selectedCount = preview
    ? preview.candidates.filter(candidateSelected).length
    : 0;
  const testAddress = draftQuery.data?.mail_test_email || "";

  return (
    <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !sendMutation.isPending) onClose(); }}>
      <section aria-labelledby="finance-mail-composer-title" aria-modal="true" className="admin-edit-dialog finance-mail-composer" role="dialog">
        <header className="admin-edit-dialog__heading">
          <div><p className="eyebrow eyebrow--muted">GEMEINSAMER ENTWURF</p><h2 id="finance-mail-composer-title">{mailKindTitle(kind)} vorbereiten</h2></div>
          <button aria-label="Schließen" className="dialog-close" disabled={sendMutation.isPending} onClick={onClose} type="button">×</button>
        </header>
        {draftQuery.isLoading && <p className="participation-empty" role="status">Gemeinsamer Mailentwurf wird geladen …</p>}
        {draftQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Gemeinsamer Mailentwurf konnte nicht geladen werden.</p>}
        {draft && (
          <>
            <p className="finance-mail-composer__saved">
              Version {draft.version} · zuletzt gespeichert {financeDate(draft.updated_at)}{draft.updated_by_username ? ` von ${draft.updated_by_username}` : ""}
            </p>
            {scopeUserUid && <p className="finance-help-text">Einzelne Zahlungserinnerung. Der gespeicherte gemeinsame Entwurf wird verwendet; Empfänger bleibt dieses Konto.</p>}
            <div className="finance-mail-composer__fields">
              {kind === "payment_reminder" ? (
                <label className="profile-field"><span>Mindestsaldo (€)</span><input min="0" onChange={(event) => { setMinimumBalance(event.target.value); setPreviewStale(true); }} step="0.01" type="number" value={minimumBalance} /><small>0,00 € umfasst jeden positiven Saldo; auch ein höherer Betrag gilt inklusive.</small></label>
              ) : (
                <label className="profile-field"><span>Beitragsjahr</span><input max={new Date().getFullYear() + 5} min="2020" onChange={(event) => { setCycleYear(Number(event.target.value)); setPreviewStale(true); }} type="number" value={cycleYear} /></label>
              )}
              <label className="profile-field"><span>Betreff</span><input maxLength={255} onChange={(event) => setSubject(event.target.value)} value={subject} /></label>
              <label className="profile-field finance-mail-composer__body"><span>Nachrichtentext</span><textarea maxLength={12000} onChange={(event) => setBody(event.target.value)} rows={9} value={body} /></label>
            </div>
            <p className="finance-help-text">
              {kind === "payment_reminder"
                ? "Platzhalter: {{name}}, {{balance}}, {{account_activity}}, {{payment_instructions}}, {{finance_url}}. Die Mail zeigt Kontobewegungen und aktuellen Nettosaldo."
                : "Platzhalter: {{name}}, {{cycle_year}}, {{verification_link}}. Der Bestätigungslink wird systemseitig eingefügt und ist in Testmails nicht funktionsfähig."}
            </p>
            <div className="finance-mail-composer__test">
              <span>Testadresse <strong>{testAddress || "Noch nicht konfiguriert"}</strong></span>
              <button className="participation-button participation-button--quiet" disabled={!testAddress || testMutation.isPending || saveDraft.isPending} onClick={() => { void sendTestEmail(); }} type="button">
                {testMutation.isPending ? "Testmail wird eingereiht …" : "Testmail senden"}
              </button>
            </div>
            <div className="finance-mail-composer__preview-heading">
              <div><h3>Empfänger:innen prüfen</h3>{previewStale && preview && <small>Vorschau aktualisieren, um aktuelle Salden und Bestätigungsstände zu laden.</small>}</div>
              <button className="text-button" disabled={saveDraft.isPending} onClick={() => { void refreshPreview(); }} type="button">{preview ? "Vorschau aktualisieren" : "Empfänger:innen laden"}</button>
            </div>
            {preview && (
              <>
                {preview.selection_is_saved && !scopeUserUid && <p className="finance-help-text">Die gespeicherte Empfängerauswahl bleibt erhalten. Mit „Vorauswahl wiederherstellen“ werden wieder alle aktuell berechtigten Personen gemäß Schwelle ausgewählt.</p>}
                <div className="finance-summary-strip">
                      <span>Ausgewählt <strong>{selectedCount}</strong></span>
                  {kind === "payment_reminder" ? (
                    <>
                      <span>Mit positivem Saldo <strong>{preview.summary.positive_balance || 0}</strong></span>
                      <span>Ohne positiven Saldo <strong>{preview.summary.no_positive_balance || 0}</strong></span>
                      <span>Ohne bestätigte Adresse <strong>{preview.summary.no_confirmed_email || 0}</strong></span>
                      <span>Unter Mindestbetrag <strong>{preview.summary.below_threshold || 0}</strong></span>
                    </>
                  ) : (
                    <>
                      <span>Bereits bestätigt <strong>{preview.summary.already_verified || 0}</strong></span>
                      <span>Ohne Hochschul-E-Mail <strong>{preview.summary.missing_hs_email || 0}</strong></span>
                      <span>Wartezeit <strong>{preview.summary.cooldown || 0}</strong></span>
                    </>
                  )}
                  {!scopeUserUid && (
                    <div className="finance-mail-composer__selection-actions">
                      <button className="text-button" onClick={() => setSelectedKeys(preview.candidates.filter((candidate) => candidate.can_select).map((candidate) => candidate.key))} type="button">Alle berechtigten auswählen</button>
                      <button className="text-button" onClick={() => setSelectedKeys([])} type="button">Alle abwählen</button>
                      <button className="text-button" onClick={selectThresholdDefault} type="button">Vorauswahl wiederherstellen</button>
                    </div>
                  )}
                </div>
                <div className="finance-mail-candidates-scroll">
                  <table className="finance-table finance-mail-candidates">
                    <thead><tr><th>Auswahl</th><th>Empfänger:in</th>{kind === "payment_reminder" && <th>Saldo</th>}<th>E-Mail / Grund</th></tr></thead>
                    <tbody>
                      {preview.candidates.map((candidate) => (
                        <tr key={candidate.key}>
                          <td><input aria-label={`${candidate.display_name} auswählen`} checked={candidateSelected(candidate)} disabled={!candidate.can_select || Boolean(scopeUserUid)} onChange={() => toggleCandidate(candidate)} type="checkbox" /></td>
                          <td><strong>{candidate.display_name}</strong><small>@{candidate.username}</small></td>
                          {kind === "payment_reminder" && <td>{euros(candidate.balance_cents)}</td>}
                          <td>
                            {candidate.email ? <strong>{candidate.email}</strong> : <span>Keine bestätigte Adresse</span>}
                            {candidate.email_source === "hs_email" && kind === "payment_reminder" && <small>Bestätigte Hochschul-E-Mail</small>}
                            {kind === "student_verification" && candidate.email && <small>Wird mit dieser Adresse zur Bestätigung angeschrieben</small>}
                            {candidate.reasons.map((reason) => <small className="finance-mail-candidate-reason" key={reason}>{mailReasonLabel(reason)}</small>)}
                          </td>
                        </tr>
                      ))}
                      {preview.candidates.length === 0 && <tr><td colSpan={kind === "payment_reminder" ? 4 : 3}>Es gibt keine passenden Konten.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
            <div className="admin-edit-dialog__actions finance-mail-composer__actions">
              <button className="participation-button participation-button--quiet" disabled={saveDraft.isPending || testMutation.isPending || sendMutation.isPending} onClick={() => { void persistDraft().then(() => setNotice("Gemeinsamer Entwurf gespeichert.")).catch((saveError: unknown) => setError(saveError instanceof Error ? saveError.message : "Entwurf konnte nicht gespeichert werden.")); }} type="button">{saveDraft.isPending ? "Wird gespeichert …" : "Entwurf speichern"}</button>
              <button className="participation-button" disabled={!preview || selectedCount === 0 || sendMutation.isPending || saveDraft.isPending} onClick={() => { void openSendConfirmation(); }} type="button">Versand prüfen · {selectedCount}</button>
            </div>
            {showSendConfirmation && (
              <section aria-labelledby="finance-mail-confirm-title" aria-modal="true" className="finance-mail-confirm" role="alertdialog">
                <h3 id="finance-mail-confirm-title">{selectedCount} E-Mail(s) versenden?</h3>
                <p>
                  {kind === "payment_reminder"
                    ? `Die aktuelle Vorauswahl umfasst ${selectedCount} Konto/Konten ab ${euros(Math.round(Number(minimumBalance) * 100))} Nettosaldo.`
                    : `Die aktuelle Vorauswahl umfasst ${selectedCount} aktive studentische Mitgliedschaft(en) für ${cycleYear}.`}
                </p>
                <div className="finance-mail-confirm__actions">
                  <button className="participation-button participation-button--quiet" disabled={sendMutation.isPending} onClick={() => setShowSendConfirmation(false)} type="button">Abbrechen</button>
                  <button className="participation-button" disabled={sendMutation.isPending} onClick={() => { void confirmSend(); }} type="button">{sendMutation.isPending ? "Wird eingereiht …" : `Jetzt an ${selectedCount} senden`}</button>
                </div>
              </section>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function FinanceRatesEditor({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const financeQuery = useQuery({ queryKey: ["admin-finance"], queryFn: getAdminFinance });
  const rates = financeQuery.data?.fee_rates ?? [];
  return (
    <section className="finance-admin-section">
      <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">PREISREGELN</p><h3>Jahresbeiträge verwalten</h3></div></header>
      <p className="finance-help-text">Vollbetrag, ermäßigte und Ausbildungsbeiträge sind Jahresbeiträge (Bestand: fällig im März; Neumitglieder: innerhalb von sechs Wochen). Für bestätigte Studierende gelten die Semesteranteile.</p>
      <div className="finance-rate-list">
        {(["full", "reduced", "student", "training", "exempt"] as const).map((category) => (
          <FinanceRateEditor csrfToken={csrfToken} key={category} onSaved={() => void queryClient.invalidateQueries({ queryKey: ["admin-finance"] })} rate={rates.find((entry) => entry.category === category)} category={category} />
        ))}
      </div>
    </section>
  );
}

function FinanceRateEditor({
  category,
  csrfToken,
  rate,
  onSaved,
}: {
  category: Exclude<FeeCategory, "special">;
  csrfToken: string;
  rate?: FinanceAdminOverview["fee_rates"][number];
  onSaved: () => void;
}) {
  const defaults = { full: 5000, reduced: 2500, student: 2000, training: 2000, exempt: 0 };
  const [amount, setAmount] = useState(((rate?.annual_amount_cents ?? defaults[category]) / 100).toFixed(2));
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => updateMembershipFeeRate(category, Math.round(Number(amount) * 100), csrfToken),
    onSuccess: () => { setError(""); onSaved(); },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Beitragssatz konnte nicht gespeichert werden."),
  });
  useEffect(() => {
    setAmount(((rate?.annual_amount_cents ?? defaults[category]) / 100).toFixed(2));
  }, [rate, category]);
  if (category === "exempt") {
    return (
      <div className="finance-rate-row">
        <strong>{feeCategoryLabel(category)}</strong>
        <span>0,00 € · Ehrenmitglieder</span>
      </div>
    );
  }
  return (
    <form className="finance-rate-row" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
      <strong>{feeCategoryLabel(category)}</strong>
      <label className="profile-field"><span>Jahresbetrag (€)</span><input min="0" onChange={(event) => setAmount(event.target.value)} required step="0.01" type="number" value={amount} /></label>
      {category === "student" ? (
        <p className="finance-help-text">Bestätigte Studierende sind bis zum Ende des Eintrittssemesters beitragsfrei. Danach gelten 9/12 im März nach dem Wintersemester oder 3/12 im September nach dem Sommersemester; in Folgejahren der volle Jahresbeitrag. Guthaben aus Vorauszahlungen wird automatisch verrechnet.</p>
      ) : category === "full" ? (
        <p className="finance-help-text">Alumni werden im Vollbetrag geführt.</p>
      ) : null}
      <button className="text-button" disabled={mutation.isPending} type="submit">Speichern</button>
      {error && <small className="auth-field-error">{error}</small>}
    </form>
  );
}

function AdminProductsTab({ csrfToken, overview }: { csrfToken: string; overview: FinanceAdminOverview }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState("");
  const createMutation = useMutation({
    mutationFn: () => createTallyItem(name.trim(), Math.round(Number(price) * 100), csrfToken),
    onSuccess: async () => {
      setName("");
      setPrice("");
      setError("");
      await queryClient.invalidateQueries({ queryKey: ["admin-finance"] });
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht erstellt werden."),
  });
  return (
    <div className="finance-admin-content">
      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">QR-TALLY</p><h3>Getränkeartikel</h3></div></header>
        <p className="finance-help-text">Preisänderungen gelten nur für zukünftige Einträge. Verwendete Artikel werden archiviert statt gelöscht; alte Buchungen behalten ihren ursprünglichen Preis.</p>
        {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
        <form className="manager-form-grid finance-new-item-form" onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
          <label className="profile-field"><span>Artikelname</span><input maxLength={80} onChange={(event) => setName(event.target.value)} required value={name} /></label>
          <label className="profile-field"><span>Preis (€)</span><input min="0.01" onChange={(event) => setPrice(event.target.value)} required step="0.01" type="number" value={price} /></label>
          <button className="participation-button" disabled={createMutation.isPending} type="submit">Artikel hinzufügen</button>
        </form>
      </section>
      <div className="finance-product-admin-list">
        {overview.products.map((item) => <TallyProductEditor csrfToken={csrfToken} item={item} key={item.id} />)}
      </div>
    </div>
  );
}

function TallyProductEditor({ csrfToken, item }: { csrfToken: string; item: TallyItem }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(item.name);
  const [price, setPrice] = useState(item.price_cents == null ? "" : (item.price_cents / 100).toFixed(2));
  const [active, setActive] = useState(item.is_active);
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: () => updateTallyItem(item.id, name.trim(), Math.round(Number(price) * 100), active, csrfToken),
    onSuccess: async () => { setError(""); await queryClient.invalidateQueries({ queryKey: ["admin-finance"] }); },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht aktualisiert werden."),
  });
  const archiveMutation = useMutation({
    mutationFn: () => archiveTallyItem(item.id, csrfToken),
    onSuccess: async () => await queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht archiviert werden."),
  });
  useEffect(() => {
    setName(item.name);
    setPrice(item.price_cents == null ? "" : (item.price_cents / 100).toFixed(2));
    setActive(item.is_active);
  }, [item]);
  return (
    <form className="finance-product-admin-row" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
      <label className="profile-field"><span>Artikel</span><input maxLength={80} onChange={(event) => setName(event.target.value)} required value={name} /></label>
      <label className="profile-field"><span>Preis (€)</span><input min="0.01" onChange={(event) => setPrice(event.target.value)} required step="0.01" type="number" value={price} /></label>
      <label className="manager-checkbox"><input checked={active} onChange={(event) => setActive(event.target.checked)} type="checkbox" /><span>Für Tally freigeschaltet</span></label>
      <div className="finance-inline-actions"><button className="text-button" disabled={mutation.isPending} type="submit">Speichern</button>{item.is_active && <button className="text-button text-button--danger" disabled={archiveMutation.isPending} onClick={() => archiveMutation.mutate()} type="button">Archivieren</button>}</div>
      {error && <small className="auth-field-error">{error}</small>}
    </form>
  );
}

function AdminPaymentsTab({ csrfToken, instructions, mailTestEmail, financeUsers, selectedUid }: {
  csrfToken: string;
  instructions: string;
  mailTestEmail: string;
  financeUsers: FinanceAccountUser[];
  selectedUid: string;
}) {
  const queryClient = useQueryClient();
  const [userUid, setUserUid] = useState(selectedUid || financeUsers[0]?.uid || "");
  const memberQuery = useQuery({
    queryKey: ["admin-finance-user", userUid],
    queryFn: () => getAdminFinanceUser(userUid),
    enabled: Boolean(userUid),
  });
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<"bank_transfer" | "cash" | "other">("bank_transfer");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [receivedAt, setReceivedAt] = useState(() => localDateTimeInput(new Date()));
  const [paymentInstructions, setPaymentInstructions] = useState(instructions);
  const [testEmailAddress, setTestEmailAddress] = useState(mailTestEmail);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [showMemberInfo, setShowMemberInfo] = useState(false);
  const [showReminderComposer, setShowReminderComposer] = useState(false);
  const [reminderScopeUserUid, setReminderScopeUserUid] = useState<string | undefined>();
  const [paymentSuggestion, setPaymentSuggestion] = useState<PendingPaymentMatchSuggestion | null>(null);
  const selectedUser = memberQuery.data?.user || financeUsers.find((user) => user.uid === userUid) || null;
  useEffect(() => { if (selectedUid) setUserUid(selectedUid); }, [selectedUid]);
  useEffect(() => { setPaymentInstructions(instructions); }, [instructions]);
  useEffect(() => { setTestEmailAddress(mailTestEmail); }, [mailTestEmail]);
  const paymentMutation = useMutation({
    mutationFn: () => recordFinancePayment(userUid, {
      amount_cents: Math.round(Number(amount) * 100),
      method,
      reference,
      note,
      received_at: receivedAt,
    }, csrfToken),
    onSuccess: async (result) => {
      setPaymentSuggestion({ userUid, payment: result.payment, suggestion: result.match_suggestion });
      setAmount(""); setReference(""); setNote(""); setNotice("Zahlung wurde verbucht."); setError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-finance-user", userUid] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Zahlung konnte nicht verbucht werden."),
  });
  const confirmPaymentMatchMutation = useMutation({
    mutationFn: (proposal: PendingPaymentMatchSuggestion) => confirmFinancePaymentChargeSuggestion(
      proposal.userUid,
      proposal.payment?.uid || null,
      proposal.suggestion.charges.map((charge) => charge.uid),
      csrfToken,
    ),
    onSuccess: async (result, proposal) => {
      setPaymentSuggestion(null);
      setNotice(`${result.confirmed_count} Buchung(en) über ${euros(result.total_cents)} wurden Zahlungszuordnungen hinzugefügt. Der Saldo verändert sich durch die Zuordnung nicht erneut.`);
      setError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-finance-user", proposal.userUid] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Der Zahlungsvorschlag konnte nicht übernommen werden. Bitte prüfe die offenen Buchungen und versuche es erneut."),
  });
  const statusMutation = useMutation({
    mutationFn: ({ charge, status, statusNote }: { charge: FinanceCharge; status: "open" | "paid" | "cancelled"; statusNote: string }) => updateFinanceChargeStatus(charge.uid, status, statusNote, csrfToken),
    onSuccess: async () => {
      setPaymentSuggestion(null);
      setNotice("Buchungsstatus wurde aktualisiert. Der Status ändert den Saldo nicht; Zahlungen werden separat verbucht.");
      setError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-finance-user", userUid] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Buchungsstatus konnte nicht aktualisiert werden."),
  });
  const voidMutation = useMutation({
    mutationFn: ({ payment, reason }: { payment: FinancePayment; reason: string }) => voidFinancePayment(payment.uid, reason, csrfToken),
    onSuccess: async (_result, variables) => {
      if (paymentSuggestion?.payment?.uid === variables.payment.uid) setPaymentSuggestion(null);
      setNotice("Zahlung wurde storniert und aus dem Saldo entfernt."); setError("");
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["admin-finance-user", userUid] }), queryClient.invalidateQueries({ queryKey: ["admin-finance"] })]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Zahlung konnte nicht storniert werden."),
  });
  const instructionsMutation = useMutation({
    mutationFn: () => updateFinanceInstructions(paymentInstructions, testEmailAddress, csrfToken),
    onSuccess: async () => { setNotice("Zahlungsinformationen und Testadresse gespeichert."); await queryClient.invalidateQueries({ queryKey: ["admin-finance"] }); },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Zahlungsinformationen konnten nicht gespeichert werden."),
  });

  function openReminderComposer(scopeUserUid?: string) {
    setReminderScopeUserUid(scopeUserUid);
    setShowReminderComposer(true);
  }

  function changeChargeStatus(charge: FinanceCharge, nextStatus: "open" | "paid" | "cancelled") {
    let statusNote = nextStatus === "paid" ? "Als bezahlt bestätigt" : nextStatus === "open" ? "Wieder geöffnet" : "";
    if (nextStatus === "cancelled") {
      statusNote = window.prompt("Grund für die Stornierung:")?.trim() || "";
      if (!statusNote) return;
    }
    statusMutation.mutate({ charge, status: nextStatus, statusNote });
  }

  return (
    <div className="finance-admin-content">
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">BENUTZERKONTO</p><h3>Konto auswählen</h3></div><button className="participation-button participation-button--quiet" onClick={() => openReminderComposer()} type="button">Zahlungserinnerung vorbereiten</button></header>
        <div className="finance-member-picker">
          <label className="profile-field finance-member-select">
              <span>Benutzerkonto</span>
              <select disabled={paymentMutation.isPending || confirmPaymentMatchMutation.isPending} onChange={(event) => { setUserUid(event.target.value); setShowMemberInfo(false); setPaymentSuggestion(null); }} value={userUid}>
                {financeUsers.map((user) => <option key={user.uid} value={user.uid}>{[user.surname, user.lastname].filter(Boolean).join(" ") || user.username} (@{user.username} · {user.role}) · {euros(user.balance_cents)}</option>)}
              </select>
            </label>
            {selectedUser && <button aria-label={`Informationen zu ${[selectedUser.surname, selectedUser.lastname].filter(Boolean).join(" ") || selectedUser.username}`} className="finance-info-button" onClick={() => setShowMemberInfo(true)} title="Kontoinformationen anzeigen" type="button">i</button>}
          </div>
        {memberQuery.isLoading && <p className="participation-empty" role="status">Mitgliedskonto wird geladen …</p>}
        {memberQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Mitgliedskonto konnte nicht geladen werden.</p>}
        {memberQuery.data && (
          <>
            <div className="finance-summary-strip">
              <span>Konto <strong>{[memberQuery.data.user.surname, memberQuery.data.user.lastname].filter(Boolean).join(" ") || memberQuery.data.user.username} (@{memberQuery.data.user.username})</strong></span>
              <span>Saldo <strong>{euros(memberQuery.data.balance_cents)}</strong></span>
              <span>Nicht zugeordnetes Guthaben <strong>{euros(memberQuery.data.unallocated_credit_cents || 0)}</strong></span>
              <span>App-Rolle <strong>{memberQuery.data.user.role}</strong></span>
              <span>Beitragsmitgliedschaft <strong>{memberQuery.data.membership ? (memberQuery.data.membership.status === "active" ? "Aktiv" : "Beendet") : "Nicht eingerichtet"}</strong></span>
              {memberQuery.data.membership && <span>Kategorie <strong>{feeCategoryLabel(memberQuery.data.membership.fee_category)}</strong></span>}
            </div>
            <button className="text-button" disabled={memberQuery.data.balance_cents <= 0} onClick={() => openReminderComposer(userUid)} type="button">Einzelne Zahlungserinnerung vorbereiten</button>
            {Boolean(memberQuery.data.unallocated_credit_cents && memberQuery.data.allocation_suggestion?.charges.length) && (
              <button
                className="text-button"
                disabled={confirmPaymentMatchMutation.isPending}
                onClick={() => setPaymentSuggestion({ userUid, payment: null, suggestion: memberQuery.data!.allocation_suggestion! })}
                type="button"
              >Vorschlag aus vorhandenem Guthaben öffnen ({euros(memberQuery.data.unallocated_credit_cents)})</button>
            )}
            <form className="finance-payment-form" onSubmit={(event) => { event.preventDefault(); paymentMutation.mutate(); }}>
              <h4>Zahlung manuell verbuchen</h4>
              <div className="manager-form-grid">
                <label className="profile-field"><span>Betrag (€)</span><input min="0.01" onChange={(event) => setAmount(event.target.value)} required step="0.01" type="number" value={amount} /></label>
                <label className="profile-field"><span>Zahlungsart</span><select onChange={(event) => setMethod(event.target.value as typeof method)} value={method}><option value="bank_transfer">Überweisung</option><option value="cash">Bar</option><option value="other">Sonstige</option></select></label>
                <label className="profile-field"><span>Eingegangen am</span><input onChange={(event) => setReceivedAt(event.target.value)} required type="datetime-local" value={receivedAt} /></label>
                <label className="profile-field"><span>Referenz (optional)</span><input maxLength={120} onChange={(event) => setReference(event.target.value)} value={reference} /></label>
                <label className="profile-field manager-form-grid__wide"><span>Notiz (optional)</span><input maxLength={1000} onChange={(event) => setNote(event.target.value)} value={note} /></label>
              </div>
              <button className="participation-button" disabled={paymentMutation.isPending || confirmPaymentMatchMutation.isPending} type="submit">{paymentMutation.isPending ? "Wird verbucht …" : "Zahlung verbuchen"}</button>
            </form>
            {paymentSuggestion?.userUid === userUid && (
              <section aria-labelledby="finance-payment-match-title" className="finance-payment-match" role="region">
                <header className="finance-payment-match__heading">
                  <div><p className="eyebrow eyebrow--muted">ZAHLUNGSABGLEICH</p><h4 id="finance-payment-match-title">Vorschlag zum Markieren als bezahlt</h4></div>
                  <span>{paymentSuggestion.payment
                    ? `${euros(paymentSuggestion.payment.amount_cents)} neue Zahlung · ${euros(paymentSuggestion.suggestion.available_amount_cents ?? paymentSuggestion.payment.amount_cents)} verfügbar`
                    : `${euros(paymentSuggestion.suggestion.available_amount_cents ?? paymentSuggestion.suggestion.payment_amount_cents)} Guthaben verfügbar`}</span>
                </header>
                {paymentSuggestion.suggestion.charges.length > 0 ? (
                  <>
                    <p className="finance-help-text">
                        {paymentSuggestion.suggestion.all_open_charges
                          ? paymentSuggestion.suggestion.remainder_cents === 0
                          ? "Alle offenen Buchungen passen genau zum verfügbaren Guthaben."
                          : `Alle offenen Buchungen werden vorgeschlagen; ${euros(paymentSuggestion.suggestion.remainder_cents)} bleiben als Guthaben übrig.`
                        : paymentSuggestion.suggestion.remainder_cents === 0
                          ? "Diese Kombination passt genau zum verfügbaren Guthaben."
                          : `Dies ist die passendste Kombination, ohne das verfügbare Guthaben zu überschreiten. ${euros(paymentSuggestion.suggestion.remainder_cents)} bleiben zunächst nicht zugeordnet.`}
                    </p>
                    <div className="finance-payment-match__summary">
                      <span>Vorgeschlagene Buchungen <strong>{paymentSuggestion.suggestion.charges.length}</strong></span>
                      <span>Summe <strong>{euros(paymentSuggestion.suggestion.total_cents)}</strong></span>
                    </div>
                    <ul className="finance-payment-match__list">
                      {paymentSuggestion.suggestion.charges.map((charge) => (
                        <li key={charge.uid}>
                          <span><strong>{chargeTitle(charge)}</strong><small>{chargeDescription(charge)}</small></span>
                          <strong>{euros(charge.remaining_cents)}</strong>
                        </li>
                      ))}
                    </ul>
                    <div className="finance-payment-match__actions">
                      <button
                        className="participation-button"
                        disabled={confirmPaymentMatchMutation.isPending || statusMutation.isPending}
                        onClick={() => confirmPaymentMatchMutation.mutate(paymentSuggestion)}
                        type="button"
                      >
                        {confirmPaymentMatchMutation.isPending ? "Wird übernommen …" : "Vorschlag übernehmen"}
                      </button>
                      <button
                        className="participation-button participation-button--quiet"
                        disabled={confirmPaymentMatchMutation.isPending}
                        onClick={() => { setPaymentSuggestion(null); setNotice("Vorschlag verworfen. Die offenen Buchungen bleiben unverändert."); }}
                        type="button"
                      >Vorschlag verwerfen</button>
                    </div>
                  </>
                ) : (
                  <div className="finance-payment-match__empty">
                    <p>Keine vollständige Buchung passt in das verfügbare Guthaben. Der Betrag bleibt unzugeordnet und kann beim nächsten Zahlungseingang erneut vorgeschlagen werden.</p>
                    <button className="participation-button participation-button--quiet" onClick={() => setPaymentSuggestion(null)} type="button">Vorschlag schließen</button>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </section>

      {memberQuery.data && (
        <section className="finance-admin-section">
          <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">KONTOAUSZUG</p><h3>Buchungen und Zahlungen</h3></div></header>
          <p className="finance-help-text">Der Saldo ergibt sich aus allen nicht stornierten Buchungen minus erfassten Zahlungen. Zahlungszuordnungen verteilen Zahlungseingänge auf einzelne Buchungen, ohne den Saldo ein zweites Mal zu verändern.</p>
          <div className="finance-ledger-list">
            {memberQuery.data.charges.map((charge) => (
              <article className="finance-ledger-row finance-ledger-row--admin" key={charge.uid}>
                <div><strong>{chargeTitle(charge)}</strong><small>{chargeDescription(charge)}</small>{chargeAllocationSummary(charge) && <small>{chargeAllocationSummary(charge)}</small>}{charge.status_note && <small>{charge.status_note}</small>}</div>
                <span className={`finance-status finance-status--${charge.status}`}>{chargeStatusLabel(charge)}</span>
                <strong>{euros(charge.amount_cents)}</strong>
                <div className="finance-inline-actions">
                  {charge.kind === "event_ticket" && charge.status === "open" && <button aria-label={`Als bezahlt markieren: ${charge.name}`} className="text-button" disabled={statusMutation.isPending || confirmPaymentMatchMutation.isPending} onClick={() => changeChargeStatus(charge, "paid")} type="button">Als bezahlt markieren</button>}
                  {charge.kind === "event_ticket" && charge.status === "paid" && <button className="text-button" disabled={statusMutation.isPending || confirmPaymentMatchMutation.isPending} onClick={() => changeChargeStatus(charge, "open")} type="button">Wieder öffnen</button>}
                  {charge.legacy_paid_override && <button className="text-button" disabled={statusMutation.isPending || confirmPaymentMatchMutation.isPending} onClick={() => changeChargeStatus(charge, "open")} type="button">Alte Markierung entfernen</button>}
                  {charge.status !== "cancelled" && charge.status !== "waived" && <button className="text-button text-button--danger" disabled={statusMutation.isPending || confirmPaymentMatchMutation.isPending} onClick={() => changeChargeStatus(charge, "cancelled")} type="button">Stornieren</button>}
                </div>
              </article>
            ))}
            {memberQuery.data.charges.length === 0 && <p className="participation-empty">Noch keine Buchungen.</p>}
          </div>
          {(memberQuery.data.charge_adjustments?.length ?? 0) > 0 && (
            <div className="finance-membership-history finance-charge-adjustment-history">
              <h4>Anpassungsverlauf der Jahresbeiträge</h4>
              <ul>
                {memberQuery.data.charge_adjustments.map((adjustment) => (
                  <li key={adjustment.id}>
                    <div>
                      <strong>{adjustment.charge_name} · {euros(adjustment.from_amount_cents)} → {euros(adjustment.to_amount_cents)}</strong>
                      <small>{chargeAdjustmentSourceLabel(adjustment.source)}{adjustment.from_due_date !== adjustment.to_due_date ? ` · Fälligkeit ${adjustment.from_due_date || "—"} → ${adjustment.to_due_date || "—"}` : ""}{adjustment.note ? ` · ${adjustment.note}` : ""}</small>
                    </div>
                    <span>{adjustment.changed_by_username} · {financeDate(adjustment.changed_at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="finance-ledger-list finance-payment-history">
            {memberQuery.data.payments.map((payment) => (
              <article className={`finance-ledger-row finance-ledger-row--admin${payment.voided_at ? " finance-ledger-row--cancelled" : ""}`} key={payment.uid}>
                <div>
                  <strong>{payment.method === "bank_transfer" ? "Überweisung" : payment.method === "cash" ? "Barzahlung" : "Sonstige Zahlung"}</strong>
                  <small>{financeDate(payment.received_at)}{payment.reference ? ` · ${payment.reference}` : ""}{payment.note ? ` · ${payment.note}` : ""}</small>
                  {payment.allocations?.filter((allocation) => allocation.active_allocated_cents > 0).map((allocation) => <small key={allocation.charge_uid}>→ {allocation.charge_name}: {euros(allocation.active_allocated_cents)}</small>)}
                  {payment.allocations?.flatMap((allocation) => {
                    const lastChange = allocation.history?.at(-1);
                    return lastChange && lastChange.from_amount_cents !== 0
                      ? [<small key={`${payment.uid}-${allocation.charge_uid}-history`}>Zuordnung geändert · {allocation.charge_name}: {euros(lastChange.from_amount_cents)} → {euros(lastChange.to_amount_cents)}{lastChange.note ? ` · ${lastChange.note}` : ""}</small>]
                      : [];
                  })}
                  {!payment.voided_at && Boolean(payment.unallocated_cents) && <small>Nicht zugeordnet: {euros(payment.unallocated_cents)}</small>}
                </div>
                <span className={`finance-status ${payment.voided_at ? "finance-status--cancelled" : "finance-status--paid"}`}>{payment.voided_at ? "Storniert" : "Verbucht"}</span>
                <strong>− {euros(payment.amount_cents)}</strong>
                {!payment.voided_at && <button className="text-button text-button--danger" disabled={voidMutation.isPending || (confirmPaymentMatchMutation.isPending && paymentSuggestion?.payment?.uid === payment.uid)} onClick={() => {
                  const confirmed = window.confirm("Diese Zahlung wird dauerhaft storniert und kann nicht rückgängig gemacht werden. Zugeordnete Buchungen werden wieder offen und der Saldo erhöht sich; der stornierte Zahlungseingang bleibt in der Historie. Zum Korrigieren muss eine neue Zahlung erfasst werden. Fortfahren?");
                  if (!confirmed) return;
                  const reason = window.prompt("Grund für die Stornierung der Zahlung:")?.trim();
                  if (reason) voidMutation.mutate({ payment, reason });
                }} type="button">Zahlung stornieren</button>}
              </article>
            ))}
          </div>
          {memberQuery.data.membership && (
            <div className="finance-membership-history">
              <h4>Änderungsverlauf der Beitragsmitgliedschaft</h4>
              {memberQuery.data.membership_history.length === 0 ? <p className="participation-empty">Noch keine Änderungen protokolliert.</p> : (
                <ul>
                  {memberQuery.data.membership_history.map((event) => (
                    <li key={event.id}>
                      <div><strong>{event.from_fee_category !== event.to_fee_category ? `${feeCategoryLabel(event.from_fee_category || "")} → ${feeCategoryLabel(event.to_fee_category || "")}` : `${event.from_status || "—"} → ${event.to_status || "—"}`}</strong><small>{event.note}</small></div>
                      <span>{event.changed_by_username} · {financeDate(event.changed_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      <FinanceMailCampaignHistory kind="payment_reminder" />

      <section className="finance-admin-section">
        <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">ZAHLUNGSWEG & MAILTEST</p><h3>Zahlungsinformationen und Testadresse</h3></div></header>
        <form className="finance-instructions-form" onSubmit={(event) => { event.preventDefault(); instructionsMutation.mutate(); }}>
          <label className="profile-field"><span>Überweisungs-/Zahlungsinformationen</span><textarea maxLength={2000} onChange={(event) => setPaymentInstructions(event.target.value)} rows={4} value={paymentInstructions} /></label>
          <label className="profile-field"><span>Konfigurierte Test-E-Mail-Adresse</span><input autoComplete="email" maxLength={255} onChange={(event) => setTestEmailAddress(event.target.value)} placeholder="test@example.org" type="email" value={testEmailAddress} /></label>
          <p className="finance-help-text">Testmails aus den gemeinsamen Entwürfen werden ausschließlich an diese Adresse gesendet.</p>
          <button className="text-button" disabled={instructionsMutation.isPending} type="submit">Zahlungs- und Testinformationen speichern</button>
        </form>
      </section>
      {showReminderComposer && (
        <FinanceMailComposer
          csrfToken={csrfToken}
          kind="payment_reminder"
          onClose={() => { setShowReminderComposer(false); setReminderScopeUserUid(undefined); }}
          onSent={setNotice}
          scopeUserUid={reminderScopeUserUid}
        />
      )}
      {showMemberInfo && memberQuery.data && (
        <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowMemberInfo(false); }}>
          <section aria-labelledby="finance-member-info-title" aria-modal="true" className="admin-edit-dialog finance-member-info-dialog" role="dialog">
            <header className="admin-edit-dialog__heading">
              <div><p className="eyebrow eyebrow--muted">BENUTZERKONTO</p><h2 id="finance-member-info-title">{[memberQuery.data.user.surname, memberQuery.data.user.lastname].filter(Boolean).join(" ") || memberQuery.data.user.username}</h2></div>
              <button aria-label="Schließen" className="dialog-close" onClick={() => setShowMemberInfo(false)} type="button">×</button>
            </header>
            <dl className="finance-member-info-list">
              <div><dt>Benutzername</dt><dd>@{memberQuery.data.user.username}</dd></div>
              <div><dt>App-Rolle (Zugriffsrechte)</dt><dd>{memberQuery.data.user.role || "Nicht hinterlegt"}</dd></div>
              <div><dt>Beitragsmitgliedschaft</dt><dd>{memberQuery.data.membership ? (memberQuery.data.membership.status === "active" ? "Aktiv" : "Beendet") : "Nicht eingerichtet"}</dd></div>
              {memberQuery.data.membership && <div><dt>Beitragskategorie</dt><dd>{feeCategoryLabel(memberQuery.data.membership.fee_category)} · seit {memberQuery.data.membership.member_since || "unbekannt"}</dd></div>}
              <div><dt>E-Mail</dt><dd>{memberQuery.data.user.email || "Nicht hinterlegt"}<small>{memberQuery.data.user.email ? (memberQuery.data.user.email_confirmed ? "Bestätigt" : "Nicht bestätigt") : ""}</small></dd></div>
              <div><dt>Hochschul-E-Mail</dt><dd>{memberQuery.data.user.hs_email || "Nicht hinterlegt"}<small>{memberQuery.data.user.hs_email ? (memberQuery.data.user.hs_email_confirmed ? "Bestätigt" : "Nicht bestätigt") : ""}</small></dd></div>
            </dl>
          </section>
        </div>
      )}
    </div>
  );
}

function AdminEventTicketsTab({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("open");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const ticketQuery = useQuery({
    queryKey: ["admin-finance-event-tickets", search, status],
    queryFn: () => getAdminEventTickets({ query: search, status: status === "all" ? undefined : status }),
  });
  const statusMutation = useMutation({
    mutationFn: async ({ registrationIds, paid, note }: { registrationIds: number[]; paid: boolean; note: string }) => {
      let updatedCount = 0;
      for (let index = 0; index < registrationIds.length; index += 500) {
        const result = await updateAdminEventTicketStatus(registrationIds.slice(index, index + 500), paid, note, csrfToken);
        updatedCount += result.updated_count;
      }
      return { updated_count: updatedCount };
    },
    onSuccess: async (result, variables) => {
      setSelectedIds([]);
      setError("");
      setNotice(`${result.updated_count} Ticket(s) wurden ${variables.paid ? "als bezahlt markiert" : "wieder geöffnet"}. Der Status wird nicht automatisch durch andere Zahlungen geändert.`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-finance-event-tickets"] }),
        queryClient.invalidateQueries({ queryKey: ["my-tickets"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance-user"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Ticketstatus konnte nicht aktualisiert werden."),
  });
  const tickets = ticketQuery.data?.tickets || [];
  const selectableTickets = tickets.filter((ticket) => ticket.status !== "cancelled");
  const selectedVisible = selectableTickets.filter((ticket) => selectedIds.includes(ticket.registration_id));
  const allVisibleSelected = selectableTickets.length > 0 && selectedVisible.length === selectableTickets.length;

  function toggleSelected(registrationId: number) {
    setSelectedIds((current) => current.includes(registrationId)
      ? current.filter((id) => id !== registrationId)
      : [...current, registrationId]);
  }

  function markTickets(registrationIds: number[], paid: boolean) {
    if (!registrationIds.length) return;
    statusMutation.mutate({
      registrationIds,
      paid,
      note: paid ? "Manuell im Eventticket-Finanzbereich als bezahlt markiert" : "Manuell im Eventticket-Finanzbereich wieder geöffnet",
    });
  }

  return (
    <section className="finance-admin-section finance-event-tickets">
      <header className="finance-section__heading">
        <div><p className="eyebrow eyebrow--muted">EVENTFINANZEN</p><h3>Eventtickets</h3></div>
      </header>
      <p className="finance-help-text">Eventtickets werden direkt über die Registrierung und das Benutzerkonto geführt. Sie erstellen keine Beitragsmitgliedschaft und lösen keine Jahresbeiträge aus. Nach einem erfassten Zahlungseingang ändert sich der Ticketstatus erst, wenn der Zuordnungsvorschlag bestätigt wird.</p>
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      {ticketQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Eventtickets konnten nicht geladen werden.</p>}
      {ticketQuery.data && (
        <>
          <div className="finance-summary-strip">
            <span>Offener gespeicherter Betrag <strong>{euros(ticketQuery.data.open_amount_cents)}</strong></span>
            <span>Nicht ins Gesamtkonto übernommener Altbestand <strong>{ticketQuery.data.open_unlinked_count}</strong></span>
          </div>
          <div className="finance-event-ticket-filters">
            <label className="profile-field">
              <span>Suche</span>
              <input onChange={(event) => { setSearch(event.target.value); setSelectedIds([]); }} placeholder="Name, Benutzername oder Event" value={search} />
            </label>
            <label className="profile-field">
              <span>Status</span>
              <select onChange={(event) => { setStatus(event.target.value); setSelectedIds([]); }} value={status}>
                <option value="open">Offen</option>
                <option value="paid">Bezahlt markiert</option>
                <option value="cancelled">Storniert</option>
                <option value="legacy">Altbestand ohne Preissnapshot</option>
                <option value="all">Alle</option>
              </select>
            </label>
          </div>
          {selectableTickets.length > 0 && (
            <div className="finance-bulk-actions">
              <button className="text-button" onClick={() => setSelectedIds(allVisibleSelected ? [] : selectableTickets.map((ticket) => ticket.registration_id))} type="button">
                {allVisibleSelected ? "Auswahl aufheben" : `Alle sichtbaren auswählen (${selectableTickets.length})`}
              </button>
              <button className="participation-button participation-button--quiet" disabled={!selectedVisible.length || statusMutation.isPending} onClick={() => markTickets(selectedVisible.map((ticket) => ticket.registration_id), true)} type="button">
                Ausgewählte als bezahlt markieren ({selectedVisible.length})
              </button>
            </div>
          )}
          <div className="finance-table-scroll">
            <table className="finance-table finance-event-ticket-table">
              <thead><tr><th>Auswahl</th><th>Teilnehmer:in</th><th>Event / Ticket</th><th>Betrag</th><th>Status</th><th>Aktion</th></tr></thead>
              <tbody>
                {tickets.map((ticket) => <FinanceEventTicketRow
                  key={ticket.registration_id}
                  onMark={(paid) => markTickets([ticket.registration_id], paid)}
                  selected={selectedIds.includes(ticket.registration_id)}
                  ticket={ticket}
                  toggleSelected={() => toggleSelected(ticket.registration_id)}
                  busy={statusMutation.isPending}
                />)}
              </tbody>
            </table>
          </div>
          {tickets.length === 0 && <p className="participation-empty">Keine passenden Eventtickets gefunden.</p>}
          {tickets.some((ticket) => !ticket.ledger_linked) && <p className="finance-help-text">Alte Tickets ohne verknüpfte Buchung werden nicht automatisch in den Gesamtsaldo übernommen. Du kannst ihren Status hier manuell aktualisieren.</p>}
        </>
      )}
    </section>
  );
}

function FinanceEventTicketRow({
  ticket,
  selected,
  busy,
  toggleSelected,
  onMark,
}: {
  ticket: FinanceEventTicket;
  selected: boolean;
  busy: boolean;
  toggleSelected: () => void;
  onMark: (paid: boolean) => void;
}) {
  const name = [ticket.surname, ticket.lastname].filter(Boolean).join(" ") || ticket.username;
  return (
    <tr className={ticket.status === "cancelled" ? "finance-event-ticket-row--cancelled" : undefined}>
      <td><input aria-label={`${name} ${ticket.event_name} auswählen`} checked={selected} disabled={ticket.status === "cancelled"} onChange={toggleSelected} type="checkbox" /></td>
      <td><strong>{name}</strong><small>@{ticket.username} · {ticket.role}</small></td>
      <td><strong>{ticket.event_name}</strong><small>{ticket.registration_name} · {financeDate(ticket.timestamp)}</small></td>
      <td>{ticket.price_cents === null ? "Altbestand · Preis nicht gespeichert" : ticket.price_cents === 0 ? "Kostenlos" : <>{euros(ticket.price_cents)}{ticket.status === "partially_paid" && ticket.remaining_cents != null && <small>Offen: {euros(ticket.remaining_cents)}</small>}</>}</td>
      <td><span className={`finance-status finance-status--${ticket.status}`}>{ticket.status === "cancelled" ? "Storniert" : ticket.status === "paid" ? "Bezahlt" : ticket.status === "partially_paid" ? "Teilweise bezahlt" : "Offen"}</span></td>
      <td>
        {ticket.status !== "cancelled" && <button className="text-button" disabled={busy} onClick={() => onMark(!ticket.paid)} type="button">{ticket.paid ? "Wieder öffnen" : "Als bezahlt markieren"}</button>}
        {ticket.status === "cancelled" && ticket.cancel_reason && <small>{ticket.cancel_reason}</small>}
      </td>
    </tr>
  );
}

function localDateTimeInput(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
