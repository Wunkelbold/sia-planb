import { useQuery } from "@tanstack/react-query";
import { useState, type KeyboardEvent, type ReactNode } from "react";

import { getCurrentSession } from "../api/events";
import { getMyProfile } from "../api/profile";

interface CalendarSubscribeButtonProps {
  children: ReactNode;
  className: string;
}

type CalendarKind = "public" | "personal";

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall through to the selection-based copy for browsers that deny clipboard access.
    }
  }

  const input = document.createElement("textarea");
  input.value = text;
  input.setAttribute("readonly", "");
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.appendChild(input);
  input.select();
  const copied = document.execCommand("copy");
  input.remove();
  if (!copied) throw new Error("Clipboard access failed");
}

function absoluteCalendarUrl(path: string): string {
  return new URL(path, window.location.origin).toString();
}

export function CalendarSubscribeButton({ children, className }: CalendarSubscribeButtonProps) {
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [copying, setCopying] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const profileQuery = useQuery({
    queryKey: ["my-profile"],
    queryFn: getMyProfile,
    enabled: dialogOpen && sessionQuery.data?.authenticated === true,
  });

  async function copyCalendar(kind: CalendarKind, path: string) {
    setCopying(true);
    setFeedback("");
    setError("");
    try {
      await copyText(absoluteCalendarUrl(path));
      setFeedback(kind === "public" ? "Öffentlicher Kalenderlink kopiert." : "Persönlicher Kalenderlink kopiert.");
      setDialogOpen(false);
    } catch {
      setError("Der Kalenderlink konnte nicht kopiert werden. Bitte erlaube den Zwischenablagezugriff.");
    } finally {
      setCopying(false);
    }
  }

  function handleButtonClick() {
    setFeedback("");
    setError("");
    if (sessionQuery.data?.authenticated) {
      setDialogOpen(true);
      return;
    }
    void copyCalendar("public", "/events.ics");
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") setDialogOpen(false);
  }

  const personalCalendarUrl = profileQuery.data?.personal_calendar_url;

  return (
    <div className="calendar-subscribe">
      <button
        className={className}
        disabled={sessionQuery.isLoading || sessionQuery.isError || copying}
        onClick={handleButtonClick}
        type="button"
      >
        {children}
      </button>
      {feedback && <span className="calendar-subscribe__status" role="status">{feedback}</span>}
      {error && !dialogOpen && <span className="calendar-subscribe__error" role="alert">{error}</span>}
      {sessionQuery.isError && (
        <span className="calendar-subscribe__error" role="alert">Kalenderoptionen konnten nicht geladen werden.</span>
      )}

      {dialogOpen && (
        <div
          className="calendar-choice-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setDialogOpen(false);
          }}
        >
          <section
            aria-labelledby="calendar-choice-title"
            aria-modal="true"
            className="calendar-choice-dialog"
            onKeyDown={handleDialogKeyDown}
            role="dialog"
          >
            <header className="calendar-choice-dialog__heading">
              <div>
                <p className="eyebrow eyebrow--muted">KALENDER ABONNIEREN</p>
                <h2 id="calendar-choice-title">Welchen Kalender möchtest du hinzufügen?</h2>
              </div>
              <button
                aria-label="Schließen"
                autoFocus
                className="dialog-close"
                onClick={() => setDialogOpen(false)}
                type="button"
              >×</button>
            </header>

            <div className="calendar-choice-options">
              <button
                className="calendar-choice-option"
                disabled={copying}
                onClick={() => void copyCalendar("public", "/events.ics")}
                type="button"
              >
                <span>
                  <strong>Öffentlicher Kalender</strong>
                  <small>Enthält die öffentlich sichtbaren Events.</small>
                </span>
                <span aria-hidden="true">↗</span>
              </button>

              <button
                className="calendar-choice-option"
                disabled={copying || profileQuery.isLoading || !personalCalendarUrl}
                onClick={() => personalCalendarUrl && void copyCalendar("personal", personalCalendarUrl)}
                type="button"
              >
                <span>
                  <strong>Persönlicher Kalender</strong>
                  <small>Enthält auch für deine Rolle sichtbare, nicht öffentliche Events sowie deine Schichten und Aufgaben.</small>
                </span>
                <span aria-hidden="true">↗</span>
              </button>
            </div>

            {profileQuery.isLoading && <p className="calendar-choice-message" role="status">Persönlicher Kalender wird geladen …</p>}
            {profileQuery.isError && <p className="calendar-choice-message" role="alert">Der persönliche Kalender konnte nicht geladen werden.</p>}
            {error && <p className="calendar-choice-message" role="alert">{error}</p>}
            <button className="calendar-choice-cancel" onClick={() => setDialogOpen(false)} type="button">Abbrechen</button>
          </section>
        </div>
      )}
    </div>
  );
}
