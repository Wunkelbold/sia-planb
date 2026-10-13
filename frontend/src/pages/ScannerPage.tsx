import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { getCurrentSession } from "../api/events";
import { getTicketsForScannedUser, updateScannedTicket, type ScannedTicket, type ScannedUserLookup } from "../api/scanner";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

function CameraReader({ onDecoded, onError }: { onDecoded: (text: string) => void; onError: (message: string) => void }) {
  const onDecodedRef = useRef(onDecoded);
  const onErrorRef = useRef(onError);
  useEffect(() => { onDecodedRef.current = onDecoded; }, [onDecoded]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => {
    let cancelled = false;
    let scanner: {
      clear: () => Promise<void>;
      render: (onSuccess: (decodedText: string) => void, onFailure: (message: string) => void) => void;
    } | null = null;

    async function startCamera() {
      try {
        const { Html5QrcodeScanner } = await import("html5-qrcode");
        if (cancelled) return;
        scanner = new Html5QrcodeScanner("ticket-qr-reader", {
          fps: 10,
          qrbox: { width: 240, height: 240 },
          rememberLastUsedCamera: true,
        }, false);
        scanner.render((decodedText) => onDecodedRef.current(decodedText), () => undefined);
      } catch {
        if (!cancelled) onErrorRef.current("Kamera konnte nicht gestartet werden. Prüfe die Kameraberechtigung oder gib den Benutzernamen manuell ein.");
      }
    }

    void startCamera();
    return () => {
      cancelled = true;
      if (scanner) void scanner.clear().catch(() => undefined);
    };
  }, []);

  return <div aria-label="QR-Code-Kamera" className="scanner-camera" id="ticket-qr-reader" />;
}

function formatPrice(price: number | string | null): string {
  if (price == null || Number(price) === 0) return "Kostenlos";
  return Number(price).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function ticketPaymentDisplay(ticket: ScannedTicket): { className: string; label: string } {
  const status = ticket.payment_status ?? (ticket.paid ? "paid" : "open");
  if (status === "paid") return { className: "ticket-payment--paid", label: "Bezahlt" };
  if (status === "partially_paid") {
    const remaining = ticket.remaining_cents == null ? "" : ` · ${formatPrice(ticket.remaining_cents / 100)} offen`;
    return { className: "ticket-payment--partial", label: `Teilweise bezahlt${remaining}` };
  }
  return { className: "", label: "Noch offen" };
}

export default function ScannerPage() {
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const [manualUsername, setManualUsername] = useState("");
  const [lastLookup, setLastLookup] = useState<ScannedUserLookup | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const session = sessionQuery.data;
  const lookupMutation = useMutation({
    mutationFn: ({ lookup, csrfToken }: { lookup: ScannedUserLookup; csrfToken: string }) => getTicketsForScannedUser(lookup, csrfToken),
    onMutate: () => {
      setFeedback("");
      setErrorMessage("");
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "QR-Code konnte nicht gelesen werden."),
  });
  const actionMutation = useMutation({
    mutationFn: ({ ticketId, action, csrfToken }: { ticketId: number; action: "validate" | "punch" | "paid" | "unpaid"; csrfToken: string }) =>
      updateScannedTicket(ticketId, action, csrfToken),
    onSuccess: async () => {
      setFeedback("Ticketstatus wurde aktualisiert.");
      if (session?.csrf_token && lastLookup) {
        await lookupMutation.mutateAsync({ lookup: lastLookup, csrfToken: session.csrf_token });
      }
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "Ticketstatus konnte nicht aktualisiert werden."),
  });

  function lookupUser(lookup: ScannedUserLookup) {
    const token = session?.csrf_token;
    if (!token) {
      setErrorMessage("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
      return;
    }
    const cleanedLookup: ScannedUserLookup = "username" in lookup
      ? { username: lookup.username.trim().toLowerCase() }
      : { uid: lookup.uid.trim() };
    const identifier = "username" in cleanedLookup ? cleanedLookup.username : cleanedLookup.uid;
    if (!identifier) {
      setErrorMessage("Gib einen Benutzernamen ein oder scanne einen Check-in-Code.");
      return;
    }
    setLastLookup(cleanedLookup);
    setErrorMessage("");
    lookupMutation.mutate({ lookup: cleanedLookup, csrfToken: token });
  }

  function lookupUsername(username: string) {
    lookupUser({ username });
  }

  function handleScan(decodedText: string) {
    setCameraActive(false);
    try {
      const parsed = JSON.parse(decodedText) as { uid?: unknown };
      if (typeof parsed.uid !== "string") throw new Error("Der QR-Code enthält keine gültige Check-in-Kennung.");
      lookupUser({ uid: parsed.uid });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Der QR-Code ist ungültig.");
    }
  }

  const tickets: ScannedTicket[] = lookupMutation.data ?? [];

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="scanner-page">
        <header className="scanner-page__heading">
          <p className="eyebrow eyebrow--muted">EVENT-EINLASS</p>
          <h1>Ticket-Scanner<span>.</span></h1>
          <p>Scanne den persönlichen Check-in-Code oder suche nach dem Benutzernamen.</p>
        </header>

        {sessionQuery.isLoading && <div className="detail-loading" role="status">Berechtigung wird geprüft …</div>}
        {sessionQuery.isError && <div className="message-panel" role="alert"><h2>Sitzung konnte nicht geladen werden.</h2></div>}
        {session && !session.authenticated && (
          <div className="message-panel" role="status"><div><h2>Melde dich an, um den Scanner zu verwenden.</h2><Link className="participation-button" to="/login">Einloggen</Link></div></div>
        )}
        {session?.authenticated && !session.can_scan_tickets && (
          <div className="message-panel" role="alert"><div><h2>Dir fehlt die Berechtigung für den Scanner.</h2><p>Der Scanner ist nur für berechtigte Teammitglieder verfügbar.</p></div></div>
        )}

        {session?.authenticated && session.can_scan_tickets && (
          <div className="scanner-layout">
            <section aria-labelledby="scanner-camera-heading" className="scanner-panel">
              <div className="participation-section__heading">
                <p className="eyebrow eyebrow--muted">KAMERA</p>
                <h2 id="scanner-camera-heading">QR-Code scannen<span>.</span></h2>
              </div>
              {cameraActive ? (
                <>
                  <CameraReader onDecoded={handleScan} onError={setErrorMessage} />
                  <button className="participation-button participation-button--quiet" onClick={() => setCameraActive(false)} type="button">Kamera schließen</button>
                </>
              ) : (
                <button className="participation-button" onClick={() => { setErrorMessage(""); setCameraActive(true); }} type="button">
                  Kamera starten
                </button>
              )}
              <form className="scanner-manual-form" onSubmit={(event) => { event.preventDefault(); lookupUsername(manualUsername); }}>
                <label className="profile-field">
                  <span>Benutzernamen manuell eingeben</span>
                  <input autoComplete="username" onChange={(event) => setManualUsername(event.target.value)} value={manualUsername} />
                </label>
                <button className="participation-button participation-button--quiet" disabled={lookupMutation.isPending} type="submit">Nutzer laden</button>
              </form>
            </section>

            <section aria-labelledby="scanner-tickets-heading" className="scanner-results">
              <div className="participation-section__heading">
                <p className="eyebrow eyebrow--muted">CHECK-IN</p>
                <h2 id="scanner-tickets-heading">Anmeldungen<span>.</span></h2>
              </div>
              {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}
              {feedback && <p className="action-feedback" role="status">{feedback}</p>}
              {lookupMutation.isPending && <p className="participation-empty" role="status">Nutzer wird gesucht …</p>}
              {!lookupMutation.isPending && lastLookup && tickets.length === 0 && !errorMessage && (
                <p className="participation-empty">Für dieses Konto sind keine Tickets vorhanden.</p>
              )}
              {tickets.length > 0 && (
                <div className="scanner-ticket-list">
                  <p className="scanner-ticket-list__user">Nutzer: <strong>{tickets[0].users}</strong></p>
                  {tickets.map((ticket) => {
                    const paymentDisplay = ticketPaymentDisplay(ticket);
                    return (
                    <article className="scanner-ticket-card" key={ticket.id}>
                      <div className="scanner-ticket-card__heading">
                        <div>
                          <p className="eyebrow eyebrow--muted">{ticket.rm_name}</p>
                          <h3>{ticket.price == null || Number(ticket.price) === 0 ? "Kostenlos" : formatPrice(ticket.price)}</h3>
                        </div>
                        <span className={`ticket-status${ticket.valid ? " ticket-status--valid" : ""}`}>
                          {ticket.valid ? "Gültig" : "Entwertet"}
                        </span>
                      </div>
                      {Number(ticket.price) > 0 && (
                        <p className={`ticket-payment${paymentDisplay.className ? ` ${paymentDisplay.className}` : ""}`}>
                          {paymentDisplay.label}
                        </p>
                      )}
                      <div className="scanner-ticket-card__actions">
                        {session.can_validate_tickets && !ticket.valid && (
                          <button className="participation-button" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ ticketId: ticket.id, action: "validate", csrfToken: session.csrf_token! })} type="button">Als gültig markieren</button>
                        )}
                        {session.can_punch_tickets && ticket.valid && (
                          <button className="participation-button participation-button--quiet" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ ticketId: ticket.id, action: "punch", csrfToken: session.csrf_token! })} type="button">Entwerten</button>
                        )}
                        {session.can_manage_ticket_payment && Number(ticket.price) > 0 && (
                          <button className="participation-button participation-button--quiet" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ ticketId: ticket.id, action: ticket.paid ? "unpaid" : "paid", csrfToken: session.csrf_token! })} type="button">
                            {ticket.paid ? "Zahlung zurücksetzen" : "Als bezahlt markieren"}
                          </button>
                        )}
                      </div>
                    </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
