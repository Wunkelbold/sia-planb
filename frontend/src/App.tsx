import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router";
import type { FormEvent } from "react";

import {
  getRegistrationSetup,
  loginAccount,
  registerAccount,
  type CaptchaChallenge,
  type RegistrationValues,
} from "./api/auth";
import {
  getCurrentSession,
  getEventDetails,
  getMyTickets,
  getUpcomingEvents,
  postEventAction,
  type EventDetails,
  type UpcomingEvent,
} from "./api/events";
import {
  getMyRoleRequests,
  getMyProfile,
  requestEmailVerification,
  submitMyRoleRequest,
  updateMyProfile,
  type ProfileFormValues,
  type ProfileInfo,
} from "./api/profile";
import { joinEventTask, leaveEventTask } from "./api/tasks";
import { CalendarSubscribeButton } from "./components/CalendarSubscribeButton";
import { SiteFooter, SiteHeader } from "./components/SiteLayout";
import { ParticipationIndicators } from "./components/ParticipationIndicators";
import EventManagerPage from "./pages/EventManagerPage";
import EventTasksPage from "./pages/EventTasksPage";
import OrganizerTaskManagerPage from "./pages/OrganizerTaskManagerPage";
import ScannerPage from "./pages/ScannerPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import MyCommitmentsPage from "./pages/MyCommitmentsPage";
import { LegalPage } from "./pages/LegalPages";
import { ForgotPasswordPage, ResetPasswordPage } from "./pages/PasswordRecoveryPage";
import { ContactPage, DrinkMenuPage, HomePage, LocationPage, VereinPage } from "./pages/PublicPages";

const MemberFinancePage = lazy(() => import("./pages/FinancePages").then((module) => ({ default: module.MemberFinancePage })));

function formatEventDate(value: string | null): string {
  if (!value) return "Termin folgt";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Termin folgt";

  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatPreparationWindow(start: string | null, end: string | null): string {
  if (!start && !end) return "Zeit noch offen";
  if (!start) return `Bis ${formatEventDate(end)}`;
  if (!end) return formatEventDate(start);
  const endTime = new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(end));
  return `${formatEventDate(start)} – ${endTime}`;
}

const preparationStatusLabels: Record<string, string> = {
  TakeOverTask: "Offen",
  OnHold: "Pausiert",
  InProgress: "In Arbeit",
  Ready: "Bereit",
  Finished: "Abgeschlossen",
};

function formatDateParts(value: string | null) {
  if (!value) return { day: "--", month: "tba" };

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { day: "--", month: "tba" };

  return {
    day: new Intl.DateTimeFormat("de-DE", {
      timeZone: "Europe/Berlin",
      day: "2-digit",
    }).format(date),
    month: new Intl.DateTimeFormat("de-DE", {
      timeZone: "Europe/Berlin",
      month: "short",
    })
      .format(date)
      .replace(".", ""),
  };
}

function EventCard({ event }: { event: UpcomingEvent }) {
  const dateParts = formatDateParts(event.date);

  return (
    <article className="event-card">
      <div className="event-card__poster">
        <img
          alt={`Plakat für ${event.name}`}
          loading="lazy"
          src={event.poster_url}
        />
        <div aria-label={formatEventDate(event.date)} className="date-stamp">
          <span className="date-stamp__day">{dateParts.day}</span>
          <span className="date-stamp__month">{dateParts.month}</span>
        </div>
      </div>

      <div className="event-card__content">
        <p className="event-card__date">{formatEventDate(event.date)}</p>
        <h3>{event.name}</h3>
        <p className="event-card__description">
          {event.description || "Weitere Informationen folgen in Kürze."}
        </p>
        <ParticipationIndicators event={event} />
        <div className="event-card__footer">
          <span className="event-card__place">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M12 22s8-7.2 8-13a8 8 0 1 0-16 0c0 5.8 8 13 8 13Z" />
              <circle cx="12" cy="9" r="2.5" />
            </svg>
            {event.place || "Ort folgt"}
          </span>
          {event.end && (
            <span className="event-card__end">
              bis {new Intl.DateTimeFormat("de-DE", {
                timeZone: "Europe/Berlin",
                hour: "2-digit",
                minute: "2-digit",
              }).format(new Date(event.end))}
            </span>
          )}
        </div>
        <Link className="event-card__link event-card__link--prominent" to={`/events/${event.id}`}>
          Eventdetails <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}

function EventsPage() {
  const [search, setSearch] = useState("");
  const eventsQuery = useQuery({
    queryKey: ["upcoming-events"],
    queryFn: getUpcomingEvents,
  });
  const events = eventsQuery.data ?? [];
  const filteredEvents = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("de-DE");
    if (!normalizedSearch) return events;

    return events.filter((event) =>
      [event.name, event.place, event.description]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase("de-DE").includes(normalizedSearch)),
    );
  }, [events, search]);

  return (
    <div className="site-shell">
      <SiteHeader />

      <main>
        <section aria-labelledby="hero-title" className="hero">
          <div className="hero__copy">
            <p className="eyebrow"><span className="eyebrow__dot" /> STUDENTENINITIATIVE ALBSTADT E.V.</p>
            <h1 id="hero-title">
              Gute Zeiten
              <br />
              <span>beginnen hier.</span>
            </h1>
            <p className="hero__intro">
              Zusammenkommen, Neues erleben und den Studienalltag hinter sich lassen.
              Entdecke, was als Nächstes im Plan B los ist.
            </p>
            <a className="hero__action" href="#events">
              Kommende Events entdecken
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M12 5v14m-7-7 7 7 7-7" />
              </svg>
            </a>
          </div>
          <div aria-hidden="true" className="hero-art">
            <div className="hero-art__ring hero-art__ring--outer" />
            <div className="hero-art__ring hero-art__ring--inner" />
            <span className="hero-art__letter">SIA</span>
            <span className="hero-art__caption">Gemeinsam<br />mehr erleben.</span>
            <span className="hero-art__spark hero-art__spark--one">✳</span>
            <span className="hero-art__spark hero-art__spark--two">✳</span>
          </div>
          <div aria-hidden="true" className="hero__index">01 <span /> EVENTS</div>
        </section>

        <section aria-labelledby="events-title" className="events-section" id="events">
          <div className="section-heading">
            <div>
              <p className="eyebrow eyebrow--muted">IM PLAN B</p>
              <h2 id="events-title">Kommende Events<span>.</span></h2>
              <p className="section-heading__subline">
                Gute Leute, gute Abende und immer ein Grund vorbeizuschauen.
              </p>
            </div>
            {!eventsQuery.isLoading && events.length > 0 && (
              <label className="search-field">
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m16 16 4 4" />
                </svg>
                <span className="visually-hidden">Events suchen</span>
                <input
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Event suchen"
                  type="search"
                  value={search}
                />
              </label>
            )}
          </div>

          {eventsQuery.isLoading && (
            <div aria-label="Events werden geladen" className="event-grid" role="status">
              {[0, 1, 2].map((item) => (
                <div aria-hidden="true" className="event-skeleton" key={item}>
                  <div className="event-skeleton__poster" />
                  <div className="event-skeleton__line" />
                  <div className="event-skeleton__line event-skeleton__line--short" />
                </div>
              ))}
            </div>
          )}

          {eventsQuery.isError && (
            <div className="message-panel" role="alert">
              <span className="message-panel__icon">!</span>
              <div>
                <h3>Events konnten gerade nicht geladen werden.</h3>
                <p>Bitte prüfe deine Verbindung und versuche es noch einmal.</p>
                <button className="text-button" onClick={() => void eventsQuery.refetch()} type="button">
                  Erneut versuchen <span aria-hidden="true">↗</span>
                </button>
              </div>
            </div>
          )}

          {!eventsQuery.isLoading && !eventsQuery.isError && events.length === 0 && (
            <div className="empty-state">
              <span aria-hidden="true" className="empty-state__icon">
                <svg viewBox="0 0 48 48">
                  <rect height="34" rx="4" width="36" x="6" y="9" />
                  <path d="M15 5v8m18-8v8M6 19h36m-26 9h7m-7 7h14" />
                </svg>
              </span>
              <p className="eyebrow eyebrow--muted">KALENDER-CHECK</p>
              <h3>Gerade sind keine Events geplant.</h3>
              <p>Schau bald wieder vorbei – das nächste gemeinsame Erlebnis kommt bestimmt.</p>
              <CalendarSubscribeButton className="calendar-subscribe-inline">Kalender abonnieren</CalendarSubscribeButton>
            </div>
          )}

          {!eventsQuery.isLoading && !eventsQuery.isError && events.length > 0 && (
            filteredEvents.length > 0 ? (
              <div className="event-grid">
                {filteredEvents.map((event) => <EventCard event={event} key={event.id} />)}
              </div>
            ) : (
              <div className="no-results">
                <p>Keine Events für „{search}“ gefunden.</p>
                <button className="text-button" onClick={() => setSearch("")} type="button">
                  Suche zurücksetzen
                </button>
              </div>
            )
          )}
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

function EventDetailPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number(eventIdParam);
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const eventQuery = useQuery({
    queryKey: ["event-details", eventId],
    queryFn: () => getEventDetails(eventId),
    enabled: Number.isInteger(eventId) && eventId > 0,
  });
  const actionMutation = useMutation({
    mutationFn: ({ path, csrfToken }: { path: string; csrfToken: string; message: string }) =>
      postEventAction(path, csrfToken),
    onMutate: () => {
      setActionMessage("");
      setActionError("");
    },
    onSuccess: async (_, action) => {
      setActionMessage(action.message);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["event-details", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["upcoming-events"] }),
      ]);
    },
    onError: (error) => {
      setActionError(error instanceof Error ? error.message : "Die Aktion ist fehlgeschlagen.");
    },
  });
  const preparationMutation = useMutation({
    mutationFn: ({ preparationId, action, csrfToken }: { preparationId: number; action: "join" | "leave"; csrfToken: string }) =>
      action === "join" ? joinEventTask(preparationId, csrfToken) : leaveEventTask(preparationId, csrfToken),
    onMutate: () => {
      setActionMessage("");
      setActionError("");
    },
    onSuccess: async (_, values) => {
      setActionMessage(values.action === "join" ? "Du hilfst bei der Vorbereitung mit." : "Du bist aus der Vorbereitung ausgetragen.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["event-details", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["my-commitments"] }),
        queryClient.invalidateQueries({ queryKey: ["upcoming-events"] }),
      ]);
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Vorbereitung konnte nicht aktualisiert werden."),
  });
  const session = sessionQuery.data;
  const details = eventQuery.data;

  function runAction(path: string, message: string) {
    const csrfToken = session?.csrf_token;
    if (!session?.authenticated || !csrfToken) {
      setActionError("Bitte melde dich an, um diese Aktion auszuführen.");
      return;
    }
    actionMutation.mutate({ path, csrfToken, message });
  }

  function runPreparationAction(preparation: EventDetails["preparations"][number], action: "join" | "leave") {
    const csrfToken = session?.csrf_token;
    if (!session?.authenticated || !csrfToken) {
      setActionError("Bitte melde dich an, um bei dieser Vorbereitung mitzuhelfen.");
      return;
    }
    preparationMutation.mutate({ preparationId: preparation.id, action, csrfToken });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="detail-page">
        <Link className="back-link" to="/events">
          <span aria-hidden="true">←</span> Alle Events
        </Link>

        {(eventQuery.isLoading || sessionQuery.isLoading) && (
          <div className="detail-loading" role="status">Event wird geladen …</div>
        )}

        {(eventQuery.isError || !Number.isInteger(eventId) || eventId <= 0) && (
          <div className="message-panel detail-error" role="alert">
            <span className="message-panel__icon">!</span>
            <div>
              <h1>Dieses Event ist nicht verfügbar.</h1>
              <p>Es wurde möglicherweise entfernt oder ist für dich nicht sichtbar.</p>
            </div>
          </div>
        )}

        {details && !eventQuery.isError && (
          <>
            <section aria-labelledby="event-detail-title" className="event-detail-hero">
              <div className="event-detail-hero__copy">
                <p className="eyebrow eyebrow--muted">EVENTDETAILS</p>
                <h1 id="event-detail-title">{details.event.name}</h1>
                <p className="event-detail__date">{formatEventDate(details.event.date)}</p>
                <p className="event-detail__place">
                  <svg aria-hidden="true" viewBox="0 0 24 24">
                    <path d="M12 22s8-7.2 8-13a8 8 0 1 0-16 0c0 5.8 8 13 8 13Z" />
                    <circle cx="12" cy="9" r="2.5" />
                  </svg>
                  {details.event.place || "Ort folgt"}
                  {details.event.end && (
                    <span>· bis {new Intl.DateTimeFormat("de-DE", {
                      timeZone: "Europe/Berlin",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(details.event.end))}</span>
                  )}
                </p>
              </div>
              <img alt={`Plakat für ${details.event.name}`} src={details.event.poster_url} />
            </section>

            <div className="event-detail-description">
              <p className="eyebrow eyebrow--muted">WAS DICH ERWARTET</p>
              <p>{details.event.description || "Weitere Informationen zu diesem Event folgen in Kürze."}</p>
            </div>

            {session?.authenticated && session.username && (
              <p className="signed-in-note">Angemeldet als <strong>{session.username}</strong></p>
            )}
            {actionMessage && <p className="action-feedback" role="status">{actionMessage}</p>}
            {actionError && <p className="action-feedback action-feedback--error" role="alert">{actionError}</p>}

            <div className="participation-grid">
              <section aria-labelledby="registration-title" className="participation-section event-participation-section">
                <div className="participation-section__heading">
                  <p className="eyebrow eyebrow--muted">DABEI SEIN</p>
                  <h2 id="registration-title">Anmeldung<span>.</span></h2>
                </div>
                {details.registrations.length === 0 ? (
                  <p className="participation-empty">Für dieses Event ist aktuell keine Anmeldung eingerichtet.</p>
                ) : (
                  <div className="participation-list">
                    {details.registrations.map((registration) => (
                      <article className="participation-card" key={registration.id}>
                        <div className="participation-card__copy">
                          <h3>{registration.name || "Teilnahme"}</h3>
                          <p>
                            {registration.price == null || Number(registration.price) === 0
                              ? "Kostenlos"
                              : Number(registration.price).toLocaleString("de-DE", {
                                  style: "currency",
                                  currency: "EUR",
                                })}
                            <span> · </span>
                            {registration.is_open ? "Anmeldung geöffnet" : "Anmeldung geschlossen"}
                          </p>
                          {(registration.start || registration.end) && (
                            <small>
                              {registration.start ? `Ab ${formatEventDate(registration.start)}` : "Jetzt"}
                              {registration.end ? ` · bis ${formatEventDate(registration.end)}` : ""}
                            </small>
                          )}
                        </div>
                        {!session?.authenticated ? (
                          <Link className="participation-button" to="/login">Anmelden</Link>
                        ) : registration.is_registered ? (
                          <div className="registration-state">
                            <span className="registration-state__badge">Angemeldet</span>
                            {registration.can_unregister ? (
                              <button
                                className="participation-button participation-button--quiet"
                                disabled={actionMutation.isPending}
                                onClick={() => runAction(
                                  `/api/events/event/${eventId}/unregister/${registration.id}`,
                                  "Du bist abgemeldet.",
                                )}
                                type="button"
                              >
                                Abmelden
                              </button>
                            ) : (
                              <small>Abmeldung nicht möglich</small>
                            )}
                          </div>
                        ) : registration.can_register ? (
                          <button
                            className="participation-button"
                            disabled={actionMutation.isPending}
                            onClick={() => runAction(
                              `/api/events/event/${eventId}/register/${registration.id}`,
                              "Du bist angemeldet.",
                            )}
                            type="button"
                          >
                            Anmelden
                          </button>
                        ) : (
                          <span className="registration-state__badge">
                            {registration.is_open ? "Nicht verfügbar" : "Geschlossen"}
                          </span>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section aria-labelledby="shifts-title" className="participation-section event-participation-section">
                <div className="participation-section__heading">
                  <p className="eyebrow eyebrow--muted">MIT ANPACKEN</p>
                  <h2 id="shifts-title">Helferschichten<span>.</span></h2>
                </div>
                {details.shifts.length === 0 ? (
                  <p className="participation-empty">Für dieses Event sind keine Helferschichten eingetragen.</p>
                ) : (
                  <div className="participation-list">
                    {details.shifts.map((shift) => (
                      <article className="participation-card" key={shift.id}>
                        <div className="participation-card__copy">
                          <h3>{shift.type || "Helferschicht"}</h3>
                          <p>
                            {shift.start ? formatEventDate(shift.start) : "Zeit folgt"}
                            {shift.end ? ` – ${new Intl.DateTimeFormat("de-DE", {
                              timeZone: "Europe/Berlin",
                              hour: "2-digit",
                              minute: "2-digit",
                            }).format(new Date(shift.end))}` : ""}
                          </p>
                          <small>
                            {shift.participants} {shift.participants === 1 ? "Person hilft" : "Personen helfen"}
                            {shift.helper_usernames.length > 0 ? ` · ${shift.helper_usernames.map((username) => `@${username}`).join(", ")}` : ""}
                          </small>
                        </div>
                        {shift.is_joined ? (
                          <div className="registration-state">
                            <span className="registration-state__badge">Eingetragen</span>
                            {session?.can_help && (
                              <button
                                className="participation-button participation-button--quiet"
                                disabled={actionMutation.isPending}
                                onClick={() => runAction(`/api/events/event/leaveshift/${shift.id}`, "Du hilfst bei dieser Schicht nicht mehr.")}
                                type="button"
                              >
                                Austragen
                              </button>
                            )}
                          </div>
                        ) : session?.can_help ? (
                          <button
                            className="participation-button"
                            disabled={actionMutation.isPending}
                            onClick={() => runAction(`/api/events/event/joinshift/${shift.id}`, "Danke, du hilfst bei dieser Schicht!")}
                            type="button"
                          >
                            Helfen
                          </button>
                        ) : !session?.authenticated ? (
                          <Link className="participation-button participation-button--quiet" to="/login">Anmelden</Link>
                        ) : (
                          <span className="registration-state__badge">Nicht verfügbar</span>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section aria-labelledby="preparations-title" className="participation-section event-participation-section event-preparations-section">
                <div className="participation-section__heading">
                  <p className="eyebrow eyebrow--muted">VORBEREITEN & MITHELFEN</p>
                  <h2 id="preparations-title">Vorbereitungen<span>.</span></h2>
                </div>
                {details.preparations.length === 0 ? (
                  <p className="participation-empty">Für dieses Event sind noch keine Vorbereitungen eingetragen.</p>
                ) : (
                  <div className="event-preparations-list">
                    {details.preparations.map((preparation) => (
                      <article className="event-preparation-item" key={preparation.id}>
                        <div className="event-preparation-item__copy">
                          <div className="event-preparation-item__title">
                            <strong>{preparation.name}</strong>
                            <span className={`event-preparation-status event-preparation-status--${preparation.status.toLowerCase()}`}>
                              {preparationStatusLabels[preparation.status] || "Geplant"}
                            </span>
                          </div>
                          {preparation.description && <p>{preparation.description}</p>}
                          <div className="event-preparation-item__meta">
                            <span>{formatPreparationWindow(preparation.timeframe_start, preparation.timeframe_end)}</span>
                            <span>{preparation.helper_count} {preparation.helper_count === 1 ? "Helfer:in" : "Helfer:innen"}</span>
                          </div>
                          <p className="event-preparation-item__helpers">
                            {preparation.helper_usernames.length > 0
                              ? `Mit: ${preparation.helper_usernames.map((username) => `@${username}`).join(", ")}`
                              : "Noch keine Helfer:innen"}
                          </p>
                        </div>
                        <div className="event-preparation-item__action">
                          {preparation.assigned_to_me ? (
                            preparation.can_leave ? (
                              <button className="participation-button participation-button--quiet" disabled={preparationMutation.isPending} onClick={() => runPreparationAction(preparation, "leave")} type="button">Austragen</button>
                            ) : <span className="registration-state__badge">Eingetragen</span>
                          ) : preparation.can_join ? (
                            <button className="participation-button" disabled={preparationMutation.isPending} onClick={() => runPreparationAction(preparation, "join")} type="button">Mithelfen</button>
                          ) : !session?.authenticated && preparation.visibility === "public" && preparation.is_open ? (
                            <Link className="participation-button participation-button--quiet" to="/login">Anmelden</Link>
                          ) : (
                            <span className="registration-state__badge">{preparation.is_open ? "Nicht verfügbar" : "Geschlossen"}</span>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function formatTicketPrice(price: number | string | null): string {
  if (price == null || Number(price) === 0) return "Kostenlos";
  return Number(price).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function profileToForm(profile: ProfileInfo): ProfileFormValues {
  return {
    username: profile.username,
    role: profile.role,
    surname: profile.surname,
    lastname: profile.lastname,
    email: profile.email,
    hs_email: profile.hs_email,
    street: profile.street,
    street_no: profile.street_no,
    city: profile.city,
    postalcode: profile.postalcode,
    password: "",
    password_confirm: "",
  };
}

function MyProfilePage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const profileQuery = useQuery({
    queryKey: ["my-profile"],
    queryFn: getMyProfile,
    enabled: sessionQuery.data?.authenticated === true,
  });
  const roleRequestsQuery = useQuery({
    queryKey: ["my-role-requests"],
    queryFn: getMyRoleRequests,
    enabled: sessionQuery.data?.authenticated === true,
  });
  const [values, setValues] = useState<ProfileFormValues>({
    username: "",
    role: "",
    surname: "",
    lastname: "",
    email: "",
    hs_email: "",
    street: "",
    street_no: "",
    city: "",
    postalcode: "",
    password: "",
    password_confirm: "",
  });
  const [feedback, setFeedback] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [roleRequestTarget, setRoleRequestTarget] = useState("");
  const [roleRequestNote, setRoleRequestNote] = useState("");
  const verificationMutation = useMutation({
    mutationFn: requestEmailVerification,
    onSuccess: () => setFeedback("Bestätigungsmail angefordert. Falls eine Adresse noch nicht bestätigt ist und die Wartezeit abgelaufen ist, wird eine Mail versendet."),
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "Bestätigungsmail konnte nicht angefordert werden."),
  });

  useEffect(() => {
    if (profileQuery.data) setValues(profileToForm(profileQuery.data));
  }, [profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: ({ formValues, csrfToken }: { formValues: ProfileFormValues; csrfToken: string }) =>
      updateMyProfile(formValues, csrfToken),
    onMutate: () => {
      setFeedback("");
      setErrorMessage("");
    },
    onSuccess: async (result) => {
      setValues(profileToForm(result.profile));
      setFeedback(
        result.verification_warning
          ? "Deine Änderungen wurden gespeichert. Die E-Mail-Bestätigung konnte gerade nicht versendet werden."
          : "Deine Änderungen wurden gespeichert.",
      );
      queryClient.setQueryData(["my-profile"], result.profile);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["current-session"] }),
        queryClient.invalidateQueries({ queryKey: ["my-tickets"] }),
        queryClient.invalidateQueries({ queryKey: ["my-role-requests"] }),
      ]);
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Dein Profil konnte nicht gespeichert werden.");
    },
  });
  const roleRequestMutation = useMutation({
    mutationFn: () => submitMyRoleRequest(roleRequestTarget, roleRequestNote, sessionQuery.data?.csrf_token || ""),
    onSuccess: async () => {
      setRoleRequestNote("");
      setFeedback("Dein Rollenänderungsantrag wurde an die Verwaltung gesendet.");
      setErrorMessage("");
      await queryClient.invalidateQueries({ queryKey: ["my-role-requests"] });
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "Rollenänderungsantrag konnte nicht gesendet werden."),
  });

  function updateField(field: keyof ProfileFormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  const session = sessionQuery.data;
  const profile = profileQuery.data;
  const roleRequests = roleRequestsQuery.data;
  useEffect(() => {
    if (roleRequests?.requestable_roles.length && !roleRequests.requestable_roles.includes(roleRequestTarget)) {
      setRoleRequestTarget(roleRequests.requestable_roles[0]);
    }
  }, [roleRequestTarget, roleRequests?.requestable_roles]);
  const verificationResult = searchParams.get("verification");
  const verificationMessage = verificationResult === "verified"
    ? "Deine E-Mail-Adresse wurde bestätigt."
    : verificationResult === "already"
      ? "Diese E-Mail-Adresse ist bereits bestätigt."
      : verificationResult === "invalid"
        ? "Der Bestätigungslink ist ungültig. Fordere im Profil einen neuen Link an."
        : verificationResult === "expired"
          ? "Der Bestätigungslink ist abgelaufen oder gehört zu keinem Konto."
          : "";
  const hasUnverifiedEmail = Boolean(
    profile && ((profile.email && !profile.email_confirmed) || (profile.hs_email && !profile.hs_email_confirmed)),
  );

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="profile-page">
        <div className="profile-page__heading">
          <p className="eyebrow eyebrow--muted">KONTO</p>
          <h1>Dein Profil<span>.</span></h1>
          <p>Halte deine Kontaktdaten aktuell und verwalte deinen persönlichen Kalender.</p>
        </div>
        {verificationMessage && (
          <p className={verificationResult === "verified" || verificationResult === "already" ? "action-feedback" : "action-feedback action-feedback--error"} role={verificationResult === "verified" || verificationResult === "already" ? "status" : "alert"}>
            {verificationMessage}
          </p>
        )}

        {(sessionQuery.isLoading || (session?.authenticated && profileQuery.isLoading)) && (
          <div className="detail-loading" role="status">Profil wird geladen …</div>
        )}

        {sessionQuery.isError && (
          <div className="message-panel" role="alert">
            <span className="message-panel__icon">!</span>
            <div>
              <h2>Dein Konto konnte nicht geprüft werden.</h2>
              <Link className="participation-button" to="/login">Einloggen</Link>
            </div>
          </div>
        )}

        {session && !session.authenticated && (
          <div className="message-panel" role="status">
            <span className="message-panel__icon">↗</span>
            <div>
              <h2>Melde dich an, um dein Profil zu verwalten.</h2>
              <Link className="participation-button" to="/login">Einloggen</Link>
            </div>
          </div>
        )}

        {session?.authenticated && profileQuery.isError && (
          <div className="message-panel" role="alert">
            <span className="message-panel__icon">!</span>
            <div>
              <h2>Dein Profil konnte nicht geladen werden.</h2>
              <button className="text-button" onClick={() => void profileQuery.refetch()} type="button">
                Erneut versuchen
              </button>
            </div>
          </div>
        )}

        {session?.authenticated && profile && (
          <>
            {feedback && <p className="action-feedback" role="status">{feedback}</p>}
            {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}

            {hasUnverifiedEmail && (
              <div className="message-panel">
                <span aria-hidden="true" className="message-panel__icon">✉</span>
                <div>
                  <h2>Bestätige deine E-Mail-Adresse</h2>
                  <p>Du kannst die Bestätigungsmail für deine noch nicht bestätigten Adressen erneut anfordern. Es gilt eine Wartezeit von fünf Minuten.</p>
                  <button
                    className="participation-button"
                    disabled={verificationMutation.isPending}
                    onClick={() => {
                      const csrfToken = session.csrf_token;
                      if (!csrfToken) {
                        setErrorMessage("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
                        return;
                      }
                      setErrorMessage("");
                      setFeedback("");
                      verificationMutation.mutate(csrfToken);
                    }}
                    type="button"
                  >
                    {verificationMutation.isPending ? "Wird angefordert …" : "Bestätigungsmail erneut anfordern"}
                  </button>
                </div>
              </div>
            )}

            <form
              className="profile-form"
              onSubmit={(event) => {
                event.preventDefault();
                const csrfToken = sessionQuery.data?.csrf_token;
                if (!csrfToken) {
                  setErrorMessage("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
                  return;
                }
                saveMutation.mutate({ formValues: values, csrfToken });
              }}
            >
              <div className="profile-form__section-heading">
                <p className="eyebrow eyebrow--muted">PERSÖNLICHE DATEN</p>
                <h2>Deine Angaben</h2>
              </div>

              <div className="profile-fields">
                <label className="profile-field">
                  <span>Benutzername</span>
                  <input autoComplete="username" maxLength={20} minLength={3} onChange={(e) => updateField("username", e.target.value)} required value={values.username} />
                  <small>Nur Buchstaben und Zahlen.</small>
                </label>
                <label className="profile-field">
                  <span>Rolle</span>
                  <select onChange={(e) => updateField("role", e.target.value)} value={values.role}>
                    {profile.roles.map((role) => <option key={role} value={role}>{role}</option>)}
                  </select>
                </label>
                <label className="profile-field">
                  <span>Vorname</span>
                  <input autoComplete="given-name" maxLength={20} onChange={(e) => updateField("surname", e.target.value)} value={values.surname} />
                </label>
                <label className="profile-field">
                  <span>Nachname</span>
                  <input autoComplete="family-name" maxLength={20} onChange={(e) => updateField("lastname", e.target.value)} value={values.lastname} />
                </label>
                <label className="profile-field">
                  <span>Ausweich-E-Mail</span>
                  <input autoComplete="email" maxLength={30} onChange={(e) => updateField("email", e.target.value)} type="email" value={values.email} />
                  <small className={profile.email_confirmed ? "profile-field__confirmed" : ""}>
                    {profile.email_confirmed ? "E-Mail bestätigt" : "Noch nicht bestätigt"}
                  </small>
                </label>
                <label className="profile-field">
                  <span>Hochschul-E-Mail</span>
                  <input autoComplete="email" maxLength={30} onChange={(e) => updateField("hs_email", e.target.value)} type="email" value={values.hs_email} />
                  <small className={profile.hs_email_confirmed ? "profile-field__confirmed" : ""}>
                    {profile.hs_email_confirmed ? "E-Mail bestätigt" : "Nur für Studierende, Format: @hs-albsig.de"}
                  </small>
                </label>
                <label className="profile-field">
                  <span>Straße</span>
                  <input autoComplete="street-address" maxLength={25} onChange={(e) => updateField("street", e.target.value)} value={values.street} />
                </label>
                <label className="profile-field">
                  <span>Hausnummer</span>
                  <input maxLength={10} onChange={(e) => updateField("street_no", e.target.value)} value={values.street_no} />
                </label>
                <label className="profile-field">
                  <span>Postleitzahl</span>
                  <input autoComplete="postal-code" inputMode="numeric" maxLength={5} onChange={(e) => updateField("postalcode", e.target.value)} value={values.postalcode} />
                </label>
                <label className="profile-field">
                  <span>Stadt</span>
                  <input autoComplete="address-level2" maxLength={25} onChange={(e) => updateField("city", e.target.value)} value={values.city} />
                </label>
              </div>

              <div className="profile-form__section-heading profile-form__section-heading--password">
                <p className="eyebrow eyebrow--muted">SICHERHEIT</p>
                <h2>Passwort ändern</h2>
                <p>Lass beide Felder leer, wenn du dein Passwort nicht ändern möchtest.</p>
              </div>
              <div className="profile-fields profile-fields--password">
                <label className="profile-field">
                  <span>Neues Passwort</span>
                  <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password", e.target.value)} type="password" value={values.password} />
                </label>
                <label className="profile-field">
                  <span>Passwort bestätigen</span>
                  <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password_confirm", e.target.value)} type="password" value={values.password_confirm} />
                </label>
              </div>
              <button className="participation-button profile-form__save" disabled={saveMutation.isPending} type="submit">
                {saveMutation.isPending ? "Wird gespeichert …" : "Änderungen speichern"}
              </button>
            </form>

            {roleRequestsQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Rollenanträge konnten nicht geladen werden.</p>}
            {roleRequests?.requestable_roles.length ? (
              <section aria-labelledby="role-request-title" className="profile-role-request">
                <div>
                  <p className="eyebrow eyebrow--muted">ROLLENÄNDERUNG</p>
                  <h2 id="role-request-title">Rolle beantragen</h2>
                  <p>Zu öffentlichen Rollen kannst du jederzeit direkt wechseln. Für Mitglied kannst du hier einen Antrag stellen; Moderator und Admin werden durch die Verwaltung vergeben. Eine Beitragsmitgliedschaft wird separat beantragt.</p>
                </div>
                {roleRequests.pending_request ? (
                  <p className="action-feedback" role="status">
                    Dein Antrag von {roleRequests.pending_request.current_role} zu {roleRequests.pending_request.requested_role} wird geprüft.
                    {roleRequests.pending_request.request_note ? ` Begründung: ${roleRequests.pending_request.request_note}` : ""}
                  </p>
                ) : (
                  <form className="profile-role-request__form" onSubmit={(event) => {
                    event.preventDefault();
                    const csrfToken = session.csrf_token;
                    if (!csrfToken) {
                      setErrorMessage("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
                      return;
                    }
                    roleRequestMutation.mutate();
                  }}>
                    <label className="profile-field">
                      <span>Gewünschte Rolle</span>
                      <select onChange={(event) => setRoleRequestTarget(event.target.value)} value={roleRequestTarget}>
                        {roleRequests.requestable_roles.map((role) => <option key={role} value={role}>{role}</option>)}
                      </select>
                    </label>
                    <label className="profile-field">
                      <span>Begründung</span>
                      <textarea maxLength={1000} onChange={(event) => setRoleRequestNote(event.target.value)} required rows={3} value={roleRequestNote} />
                    </label>
                    <button className="participation-button" disabled={roleRequestMutation.isPending} type="submit">
                      {roleRequestMutation.isPending ? "Wird gesendet …" : "Rollenänderung beantragen"}
                    </button>
                  </form>
                )}
              </section>
            ) : null}

            <section aria-labelledby="personal-calendar-title" className="personal-calendar-card">
              <div>
                <p className="eyebrow eyebrow--muted">IMMER AKTUELL</p>
                <h2 id="personal-calendar-title">Dein persönlicher Kalender</h2>
                <p>Dieser Kalender enthält auch für deine Rolle sichtbare, nicht öffentliche Events sowie deine persönlichen Schichten und Aufgaben.</p>
              </div>
              <div className="personal-calendar-card__actions">
                <CalendarSubscribeButton className="participation-button">Kalender abonnieren</CalendarSubscribeButton>
              </div>
            </section>
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function MyRegistrationsPage() {
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const ticketsQuery = useQuery({
    queryKey: ["my-tickets"],
    queryFn: getMyTickets,
    enabled: sessionQuery.data?.authenticated === true,
  });
  const session = sessionQuery.data;
  const tickets = ticketsQuery.data;

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="tickets-page">
        <div className="tickets-page__heading">
          <p className="eyebrow eyebrow--muted">PERSÖNLICHER BEREICH</p>
          <h1>Meine Tickets<span>.</span></h1>
          <p>Deine Anmeldungen und dein persönlicher Check-in-Code an einem Ort.</p>
        </div>

        {(sessionQuery.isLoading || (session?.authenticated && ticketsQuery.isLoading)) && (
          <div className="detail-loading" role="status">Deine Tickets werden geladen …</div>
        )}

        {sessionQuery.isError && (
          <div className="message-panel" role="alert">
            <span className="message-panel__icon">!</span>
            <div>
              <h2>Dein Konto konnte nicht geprüft werden.</h2>
              <p>Bitte lade die Seite erneut oder melde dich noch einmal an.</p>
              <Link className="participation-button" to="/login">Einloggen</Link>
            </div>
          </div>
        )}

        {session && !session.authenticated && (
          <div className="message-panel" role="status">
            <span className="message-panel__icon">↗</span>
            <div>
              <h2>Melde dich an, um deine Tickets zu sehen.</h2>
              <p>Nach dem Einloggen findest du hier deine Event-Anmeldungen und den Check-in-Code.</p>
              <Link className="participation-button" to="/login">Einloggen</Link>
            </div>
          </div>
        )}

        {session?.authenticated && ticketsQuery.isError && (
          <div className="message-panel" role="alert">
            <span className="message-panel__icon">!</span>
            <div>
              <h2>Deine Tickets konnten nicht geladen werden.</h2>
              <p>Bitte versuche es noch einmal.</p>
              <button className="text-button" onClick={() => void ticketsQuery.refetch()} type="button">
                Erneut versuchen
              </button>
            </div>
          </div>
        )}

        {session?.authenticated && tickets && (
          <div className="tickets-layout">
            <aside aria-label="Check-in-Code" className="checkin-card">
              <p className="eyebrow eyebrow--muted">DEIN CHECK-IN</p>
              <img alt="Dein persönlicher Check-in-QR-Code" src={tickets.checkin_qr} />
              <h2>Einmal scannen, fertig.</h2>
              <p>Zeige diesen Code am Einlass vor. Er enthält nur deine persönliche Check-in-Kennung.</p>
            </aside>

            <section aria-labelledby="my-registrations-title" className="my-registrations">
              <div className="participation-section__heading">
                <p className="eyebrow eyebrow--muted">DEINE EVENTS</p>
                <h2 id="my-registrations-title">Anmeldungen<span>.</span></h2>
              </div>
              {tickets.tickets.length === 0 ? (
                <div className="participation-empty">
                  <p>Du hast noch keine Tickets.</p>
                  <Link to="/events">Kommende Events ansehen <span aria-hidden="true">→</span></Link>
                </div>
              ) : (
                <div className="my-ticket-list">
                  {tickets.tickets.map((ticket) => {
                    const paymentStatus = ticket.payment_status ?? (ticket.paid ? "paid" : "open");
                    return (
                    <article className="my-ticket-card" key={ticket.id}>
                      <div className="my-ticket-card__top">
                        <div>
                          <p className="eyebrow eyebrow--muted">{ticket.registration_name || "Anmeldung"}</p>
                          <h3>{ticket.event.name}</h3>
                        </div>
                        <span className={`ticket-status${ticket.valid ? " ticket-status--valid" : ""}`}>
                          {ticket.valid ? "Gültig" : "Entwertet"}
                        </span>
                      </div>
                      <p className="my-ticket-card__event-date">{formatEventDate(ticket.event.date)}</p>
                      <div className="my-ticket-card__meta">
                        <span>{ticket.event.place || "Ort folgt"}</span>
                        <span>{formatTicketPrice(ticket.price)}</span>
                        {Number(ticket.price) > 0 && (
                          <span className={`ticket-payment${paymentStatus === "paid" ? " ticket-payment--paid" : paymentStatus === "partially_paid" ? " ticket-payment--partial" : ""}`}>
                            {paymentStatus === "paid"
                              ? "Bezahlt"
                              : paymentStatus === "partially_paid"
                                ? `Teilweise bezahlt · ${formatTicketPrice((ticket.remaining_cents ?? 0) / 100)} offen`
                                : "Noch offen"}
                          </span>
                        )}
                      </div>
                      <Link className="event-card__link" to={`/events/${ticket.event.id}`}>
                        {ticket.can_cancel ? "Anmeldung verwalten" : "Eventdetails"}
                        <span aria-hidden="true">→</span>
                      </Link>
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

function firstAuthError(result: { error?: string; errors?: Record<string, string[]> }, fallback: string) {
  return result.error || Object.values(result.errors ?? {}).flat()[0] || fallback;
}

function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const loginMutation = useMutation({
    mutationFn: ({ name, secret, csrfToken }: { name: string; secret: string; csrfToken: string }) =>
      loginAccount(name, secret, csrfToken),
    onSuccess: async (result) => {
      if (!result.success || !result.session) {
        setErrorMessage(firstAuthError(result, "Benutzername oder Passwort ist falsch."));
        return;
      }
      queryClient.setQueryData(["current-session"], result.session);
      await queryClient.invalidateQueries({ queryKey: ["current-session"] });
      navigate("/me/registrations", { replace: true });
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Anmeldung gerade nicht möglich.");
    },
  });

  useEffect(() => {
    if (sessionQuery.data?.authenticated) navigate("/me/registrations", { replace: true });
  }, [navigate, sessionQuery.data?.authenticated]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    const csrfToken = sessionQuery.data?.csrf_token;
    if (!csrfToken) {
      setErrorMessage("Deine Sitzung konnte nicht geprüft werden. Bitte lade die Seite neu.");
      return;
    }
    loginMutation.mutate({ name: username, secret: password, csrfToken });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="auth-page">
        <section aria-labelledby="login-title" className="auth-card">
          <p className="eyebrow eyebrow--muted">WILLKOMMEN ZURÜCK</p>
          <h1 id="login-title">Einloggen<span>.</span></h1>
          <p className="auth-card__intro">Melde dich an, um deine Events und Tickets zu verwalten.</p>
          {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}
          {sessionQuery.isError && (
            <p className="action-feedback action-feedback--error" role="alert">
              Die Sitzung konnte nicht geladen werden. Bitte versuche es erneut.
            </p>
          )}
          <form className="auth-form" onSubmit={submit}>
            <label className="profile-field">
              <span>Benutzername</span>
              <input
                autoComplete="username"
                maxLength={20}
                minLength={3}
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </label>
          <label className="profile-field">
            <span>Passwort</span>
              <input
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
              value={password}
            />
          </label>
          <p className="auth-card__switch auth-card__switch--forgot"><Link to="/forgot-password">Passwort vergessen?</Link></p>
          <button
              className="participation-button auth-form__submit"
              disabled={loginMutation.isPending || sessionQuery.isLoading}
              type="submit"
            >
              {loginMutation.isPending ? "Wird angemeldet …" : "Einloggen"}
            </button>
          </form>
          <p className="auth-card__switch">
            Noch kein Konto? <Link to="/register">Jetzt registrieren</Link>
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

const emptyRegistration: RegistrationValues = {
  username: "",
  password: "",
  password_confirm: "",
  role: "",
  surname: "",
  lastname: "",
  email: "",
  hs_email: "",
  street: "",
  street_no: "",
  city: "",
  postalcode: "",
  privacy_policy: false,
};

function RegisterPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });
  const setupQuery = useQuery({
    queryKey: ["registration-setup"],
    queryFn: getRegistrationSetup,
    enabled: sessionQuery.data?.authenticated === false,
  });
  const [values, setValues] = useState<RegistrationValues>(emptyRegistration);
  const [captchaOverride, setCaptchaOverride] = useState<CaptchaChallenge | null>(null);
  const [csrfOverride, setCsrfOverride] = useState("");
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [errorMessage, setErrorMessage] = useState("");
  const registerMutation = useMutation({
    mutationFn: ({ csrfToken, captcha }: { csrfToken: string; captcha: CaptchaChallenge }) =>
      registerAccount(values, captchaAnswer, captcha, csrfToken),
    onSuccess: async (result) => {
      if (!result.success || !result.session) {
        setErrors(result.errors ?? {});
        setErrorMessage(firstAuthError(result, "Bitte überprüfe deine Angaben und versuche es erneut."));
        if (result.captcha) setCaptchaOverride(result.captcha);
        if (result.csrf_token) setCsrfOverride(result.csrf_token);
        setCaptchaAnswer("");
        return;
      }
      queryClient.setQueryData(["current-session"], result.session);
      await queryClient.invalidateQueries({ queryKey: ["current-session"] });
      navigate("/me/registrations", { replace: true });
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Die Registrierung ist gerade nicht möglich.");
    },
  });

  useEffect(() => {
    if (sessionQuery.data?.authenticated) navigate("/me/registrations", { replace: true });
  }, [navigate, sessionQuery.data?.authenticated]);

  useEffect(() => {
    const roles = setupQuery.data?.roles;
    if (roles?.length && !values.role) {
      setValues((current) => ({ ...current, role: roles[0] }));
    }
  }, [setupQuery.data?.roles, values.role]);

  function updateField(field: keyof RegistrationValues, value: string | boolean) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function refreshCaptcha() {
    setCaptchaOverride(null);
    setCaptchaAnswer("");
    setErrors({});
    await setupQuery.refetch();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    setErrorMessage("");
    const csrfToken = csrfOverride || setupQuery.data?.csrf_token;
    const captcha = captchaOverride || setupQuery.data?.captcha;
    if (!csrfToken || !captcha) {
      setErrorMessage("Die Sicherheitsabfrage ist noch nicht bereit. Bitte lade eine neue.");
      return;
    }
    registerMutation.mutate({ csrfToken, captcha });
  }

  const captcha = captchaOverride || setupQuery.data?.captcha;
  const fieldError = (field: string) => errors[field]?.[0];

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="auth-page auth-page--register">
        <section aria-labelledby="register-title" className="auth-card auth-card--wide">
          <p className="eyebrow eyebrow--muted">TEIL DER COMMUNITY WERDEN</p>
          <h1 id="register-title">Konto erstellen<span>.</span></h1>
          <p className="auth-card__intro">Erstelle dein Konto, um dich für Events anzumelden und mitzuhelfen.</p>
          {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}
          {(sessionQuery.isError || setupQuery.isError) && (
            <p className="action-feedback action-feedback--error" role="alert">
              Das Registrierungsformular konnte nicht geladen werden.
            </p>
          )}

          <form className="auth-form" onSubmit={submit}>
            <div className="profile-fields">
              <label className="profile-field">
                <span>Benutzername</span>
                <input autoComplete="username" maxLength={20} minLength={3} onChange={(e) => updateField("username", e.target.value)} required value={values.username} />
                {fieldError("username") && <small className="auth-field-error">{fieldError("username")}</small>}
              </label>
              <label className="profile-field">
                <span>Rolle</span>
                <select onChange={(e) => updateField("role", e.target.value)} required value={values.role}>
                  {(setupQuery.data?.roles ?? []).map((role) => <option key={role} value={role}>{role}</option>)}
                </select>
                {fieldError("role") && <small className="auth-field-error">{fieldError("role")}</small>}
              </label>
              <label className="profile-field">
                <span>Passwort</span>
                <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password", e.target.value)} required type="password" value={values.password} />
                {fieldError("password") && <small className="auth-field-error">{fieldError("password")}</small>}
              </label>
              <label className="profile-field">
                <span>Passwort bestätigen</span>
                <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password_confirm", e.target.value)} required type="password" value={values.password_confirm} />
                {fieldError("password_confirm") && <small className="auth-field-error">{fieldError("password_confirm")}</small>}
              </label>
              <label className="profile-field">
                <span>Vorname</span>
                <input autoComplete="given-name" maxLength={20} onChange={(e) => updateField("surname", e.target.value)} value={values.surname} />
                {fieldError("surname") && <small className="auth-field-error">{fieldError("surname")}</small>}
              </label>
              <label className="profile-field">
                <span>Nachname</span>
                <input autoComplete="family-name" maxLength={20} onChange={(e) => updateField("lastname", e.target.value)} value={values.lastname} />
                {fieldError("lastname") && <small className="auth-field-error">{fieldError("lastname")}</small>}
              </label>
              <label className="profile-field">
                <span>Ausweich-E-Mail</span>
                <input autoComplete="email" maxLength={30} onChange={(e) => updateField("email", e.target.value)} type="email" value={values.email} />
                {fieldError("email") && <small className="auth-field-error">{fieldError("email")}</small>}
              </label>
              <label className="profile-field">
                <span>Hochschul-E-Mail{values.role === "Student" ? " *" : ""}</span>
                <input autoComplete="email" maxLength={30} onChange={(e) => updateField("hs_email", e.target.value)} required={values.role === "Student"} type="email" value={values.hs_email} />
                {fieldError("hs_email") && <small className="auth-field-error">{fieldError("hs_email")}</small>}
              </label>
              <label className="profile-field">
                <span>Straße</span>
                <input autoComplete="street-address" maxLength={25} onChange={(e) => updateField("street", e.target.value)} value={values.street} />
              </label>
              <label className="profile-field">
                <span>Hausnummer</span>
                <input maxLength={10} onChange={(e) => updateField("street_no", e.target.value)} value={values.street_no} />
              </label>
              <label className="profile-field">
                <span>Postleitzahl</span>
                <input autoComplete="postal-code" inputMode="numeric" maxLength={5} onChange={(e) => updateField("postalcode", e.target.value)} value={values.postalcode} />
                {fieldError("postalcode") && <small className="auth-field-error">{fieldError("postalcode")}</small>}
              </label>
              <label className="profile-field">
                <span>Stadt</span>
                <input autoComplete="address-level2" maxLength={25} onChange={(e) => updateField("city", e.target.value)} value={values.city} />
              </label>
            </div>

            <div className="captcha-field">
              <div className="captcha-field__heading">
                <label htmlFor="captcha-answer">Sicherheitsabfrage</label>
                <button className="text-button" disabled={setupQuery.isFetching} onClick={() => void refreshCaptcha()} type="button">
                  Neue Abfrage
                </button>
              </div>
              {captcha && <img alt="Zeichen aus dem CAPTCHA" src={captcha.image} />}
              <input
                autoComplete="off"
                id="captcha-answer"
                maxLength={6}
                minLength={6}
                onChange={(e) => setCaptchaAnswer(e.target.value)}
                placeholder="Zeichen eingeben"
                required
                value={captchaAnswer}
              />
              {fieldError("captcha") && <small className="auth-field-error">{fieldError("captcha")}</small>}
            </div>

            <label className="privacy-consent">
              <input
                checked={values.privacy_policy}
                onChange={(e) => updateField("privacy_policy", e.target.checked)}
                required
                type="checkbox"
              />
              <span>Ich akzeptiere die Verarbeitung meiner Daten nach der <Link rel="noreferrer" target="_blank" to="/datenschutz">Datenschutzerklärung</Link>.</span>
            </label>
            {fieldError("privacy_policy") && <small className="auth-field-error">{fieldError("privacy_policy")}</small>}

            <button className="participation-button auth-form__submit" disabled={registerMutation.isPending || setupQuery.isLoading} type="submit">
              {registerMutation.isPending ? "Konto wird erstellt …" : "Konto erstellen"}
            </button>
          </form>
          <p className="auth-card__switch">Schon registriert? <Link to="/login">Einloggen</Link></p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

function NotFoundPage() {
  return (
    <main className="not-found">
      <p className="eyebrow eyebrow--muted">404 · FALSCH ABGEBOGEN?</p>
      <h1>Diese Seite gibt es nicht.</h1>
      <Link className="hero__action" to="/events">Zurück zu den Events</Link>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<HomePage />} path="/" />
      <Route element={<EventsPage />} path="/events" />
      <Route element={<VereinPage />} path="/verein" />
      <Route element={<LocationPage />} path="/location" />
      <Route element={<DrinkMenuPage />} path="/getraenkekarte" />
      <Route element={<ContactPage />} path="/contact" />
      <Route element={<LegalPage document="privacy" />} path="/datenschutz" />
      <Route element={<LegalPage document="imprint" />} path="/impressum" />
      <Route element={<ScannerPage />} path="/scanner" />
      <Route element={<EventDetailPage />} path="/events/:eventId" />
      <Route element={<MyRegistrationsPage />} path="/me/registrations" />
      <Route element={<MyCommitmentsPage />} path="/me/commitments" />
      <Route element={<Suspense fallback={<div className="detail-loading" role="status">Finanzen werden geladen …</div>}><MemberFinancePage /></Suspense>} path="/me/finances" />
      <Route element={<MyProfilePage />} path="/me/profile" />
      <Route element={<LoginPage />} path="/login" />
      <Route element={<ForgotPasswordPage />} path="/forgot-password" />
      <Route element={<ResetPasswordPage />} path="/reset-password" />
      <Route element={<RegisterPage />} path="/register" />
      <Route element={<EventManagerPage />} path="/manage/events" />
      <Route element={<EventTasksPage />} path="/events/:eventId/tasks" />
      <Route element={<OrganizerTaskManagerPage />} path="/manage/events/:eventId/tasks" />
      <Route element={<AdminDashboardPage />} path="/admin" />
      <Route element={<NotFoundPage />} path="*" />
    </Routes>
  );
}
