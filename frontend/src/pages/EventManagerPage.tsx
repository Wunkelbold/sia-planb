import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";

import {
  createManagedEvent,
  createManagedRegistration,
  createManagedShift,
  deleteManagedEvent,
  deleteManagedRegistration,
  deleteManagedShift,
  getManagedEvents,
  updateManagedEvent,
  updateManagedRegistration,
  updateManagedShift,
  type ManagedEvent,
  type ManagedEventFields,
  type ManagedRegistrationFields,
  type ManagedShiftFields,
} from "../api/eventManager";
import { getCurrentSession } from "../api/events";
import AdminAssignmentManager from "../components/AdminAssignmentManager";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";
import OrganizerTaskManagerPage from "./OrganizerTaskManagerPage";

const emptyEvent: ManagedEventFields = {
  name: "",
  visibility: "public",
  place: "",
  date: "",
  end: "",
  description: "",
  move_shifts: true,
};

const emptyShift: ManagedShiftFields = { type: "", start: "", end: "" };
const emptyRegistration: ManagedRegistrationFields = {
  name: "",
  visibility: "public",
  accept: "geöffnet",
  deny: "erlaubt",
  start: "",
  end: "",
  price: "",
};

const EVENT_GRACE_PERIOD_MS = 12 * 60 * 60 * 1000;

function eventStartTime(value: string | null): number | null {
  if (!value) return null;
  const start = new Date(value).getTime();
  return Number.isNaN(start) ? null : start;
}

function toDateTimeInput(value: string | null): string {
  return value ? value.slice(0, 16) : "";
}

function parseWallClock(value: string): Date | null {
  if (!value) return null;
  const date = new Date(`${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function shiftWallClock(value: string, deltaMs: number): string {
  const date = parseWallClock(value);
  if (!date) return value;
  const shifted = new Date(date.getTime() + deltaMs);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}T${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`;
}

function formatOrganizerDate(value: string | null): string {
  if (!value) return "Termin folgt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Termin folgt";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function eventToForm(event: ManagedEvent): ManagedEventFields {
  return {
    name: event.name,
    visibility: event.visibility,
    place: event.place,
    date: toDateTimeInput(event.date),
    end: toDateTimeInput(event.end),
    description: event.description,
    move_shifts: true,
  };
}

function shiftToForm(shift: ManagedEvent["shifts"][number]): ManagedShiftFields {
  return {
    type: shift.type,
    start: toDateTimeInput(shift.start),
    end: toDateTimeInput(shift.end),
  };
}

function registrationToForm(option: ManagedEvent["registration_options"][number]): ManagedRegistrationFields {
  return {
    name: option.name,
    visibility: option.visibility,
    accept: option.accept,
    deny: option.deny,
    start: toDateTimeInput(option.start),
    end: toDateTimeInput(option.end),
    price: option.price == null ? "" : String(option.price),
  };
}

function VisibilitySelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <select onChange={(event) => onChange(event.target.value)} value={value}>
      <option value="public">Öffentlich</option>
      <option value="student">Studierende</option>
      <option value="member">Mitglieder</option>
      <option value="private">Privat</option>
    </select>
  );
}

function EventFields({
  values,
  onChange,
  editing = false,
}: {
  values: ManagedEventFields;
  onChange: (field: keyof ManagedEventFields, value: string | boolean) => void;
  editing?: boolean;
}) {
  return (
    <div className="manager-form-grid">
      <label className="profile-field manager-form-grid__wide">
        <span>Eventname</span>
        <input maxLength={50} onChange={(e) => onChange("name", e.target.value)} required value={values.name} />
      </label>
      <label className="profile-field">
        <span>Sichtbarkeit</span>
        <VisibilitySelect onChange={(value) => onChange("visibility", value)} value={values.visibility} />
      </label>
      <label className="profile-field">
        <span>Ort</span>
        <input maxLength={50} onChange={(e) => onChange("place", e.target.value)} value={values.place} />
      </label>
      <label className="profile-field">
        <span>Beginn</span>
        <input onChange={(e) => onChange("date", e.target.value)} required type="datetime-local" value={values.date} />
      </label>
      <label className="profile-field">
        <span>Ende</span>
        <input onChange={(e) => onChange("end", e.target.value)} type="datetime-local" value={values.end} />
      </label>
      <label className="profile-field manager-form-grid__wide">
        <span>Beschreibung</span>
        <textarea maxLength={300} onChange={(e) => onChange("description", e.target.value)} rows={4} value={values.description} />
      </label>
      {editing && (
        <label className="manager-checkbox manager-form-grid__wide">
          <input
            checked={values.move_shifts !== false}
            onChange={(e) => onChange("move_shifts", e.target.checked)}
            type="checkbox"
          />
          <span>Helferschichten, Anmeldungen und Aufgaben mitverschieben</span>
        </label>
      )}
    </div>
  );
}

interface ManagerAction {
  run: () => Promise<unknown>;
  message: string;
  after?: (result: unknown) => void;
}

export default function EventManagerPage({ embedded = false }: { embedded?: boolean } = {}) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const eventsQuery = useQuery({
    queryKey: ["managed-events"],
    queryFn: getManagedEvents,
    enabled: sessionQuery.data?.authenticated === true && sessionQuery.data.can_manage_events === true,
  });
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [newEvent, setNewEvent] = useState<ManagedEventFields>(emptyEvent);
  const [editEvent, setEditEvent] = useState<ManagedEventFields>(emptyEvent);
  const [shiftForm, setShiftForm] = useState<ManagedShiftFields>(emptyShift);
  const [registrationForm, setRegistrationForm] = useState<ManagedRegistrationFields>(emptyRegistration);
  const [editingShiftId, setEditingShiftId] = useState<number | null>(null);
  const [editingRegistrationId, setEditingRegistrationId] = useState<number | null>(null);
  const [activeParticipationForm, setActiveParticipationForm] = useState<"shift" | "registration" | null>(null);
  const shiftFormRef = useRef<HTMLFormElement>(null);
  const registrationFormRef = useRef<HTMLFormElement>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [hidePastEvents, setHidePastEvents] = useState(false);
  const events = eventsQuery.data?.events ?? [];
  const selectedEvent = events.find((event) => event.id === selectedEventId);
  const visibleEvents = useMemo(() => {
    const now = Date.now();
    const filteredEvents = hidePastEvents
      ? events.filter((event) => {
          const start = eventStartTime(event.date);
          return start === null || start + EVENT_GRACE_PERIOD_MS >= now;
        })
      : events;
    return [...filteredEvents].sort((left, right) => {
      const leftStart = eventStartTime(left.date);
      const rightStart = eventStartTime(right.date);
      if (leftStart === null && rightStart === null) return 0;
      if (leftStart === null) return 1;
      if (rightStart === null) return -1;
      return sortDirection === "asc" ? leftStart - rightStart : rightStart - leftStart;
    });
  }, [events, hidePastEvents, sortDirection]);

  const actionMutation = useMutation<unknown, Error, ManagerAction>({
    mutationFn: ({ run }) => run(),
    onMutate: () => {
      setNotice("");
      setError("");
    },
    onSuccess: async (result, action) => {
      action.after?.(result);
      setNotice(action.message);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["managed-events"] }),
        queryClient.invalidateQueries({ queryKey: ["upcoming-events"] }),
        queryClient.invalidateQueries({ queryKey: ["event-details"] }),
      ]);
    },
    onError: (actionError) => {
      setError(actionError.message || "Die Änderung konnte nicht gespeichert werden.");
    },
  });

  useEffect(() => {
    if (!selectedEvent) {
      setEditEvent(emptyEvent);
      setShiftForm(emptyShift);
      setRegistrationForm(emptyRegistration);
      setEditingShiftId(null);
      setEditingRegistrationId(null);
      setActiveParticipationForm(null);
      return;
    }
    setEditEvent(eventToForm(selectedEvent));
    setShiftForm(emptyShift);
    setRegistrationForm(emptyRegistration);
    setEditingShiftId(null);
    setEditingRegistrationId(null);
    setActiveParticipationForm(null);
  }, [selectedEvent?.id]);

  useEffect(() => {
    const form = activeParticipationForm === "shift"
      ? shiftFormRef.current
      : activeParticipationForm === "registration"
        ? registrationFormRef.current
        : null;
    if (!form) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    form.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  }, [activeParticipationForm]);

  function csrfToken(): string | null {
    const token = sessionQuery.data?.csrf_token;
    if (!token) {
      setError("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
      return null;
    }
    return token;
  }

  function runAction(run: () => Promise<unknown>, message: string, after?: (result: unknown) => void) {
    if (!csrfToken()) return;
    actionMutation.mutate({ run, message, after });
  }

  function updateEventField(field: keyof ManagedEventFields, value: string | boolean) {
    setEditEvent((current) => {
      if (field !== "date" || typeof value !== "string") return { ...current, [field]: value };
      const previous = parseWallClock(current.date);
      const next = parseWallClock(value);
      if (!previous || !next || !current.end) return { ...current, date: value };
      return { ...current, date: value, end: shiftWallClock(current.end, next.getTime() - previous.getTime()) };
    });
  }

  function openShiftForm(shift?: ManagedEvent["shifts"][number]) {
    setEditingRegistrationId(null);
    setRegistrationForm(emptyRegistration);
    setEditingShiftId(shift?.id ?? null);
    setShiftForm(shift ? shiftToForm(shift) : emptyShift);
    setActiveParticipationForm("shift");
  }

  function openRegistrationForm(registration?: ManagedEvent["registration_options"][number]) {
    setEditingShiftId(null);
    setShiftForm(emptyShift);
    setEditingRegistrationId(registration?.id ?? null);
    setRegistrationForm(registration ? registrationToForm(registration) : emptyRegistration);
    setActiveParticipationForm("registration");
  }

  function closeParticipationForm() {
    setActiveParticipationForm(null);
    setEditingShiftId(null);
    setEditingRegistrationId(null);
    setShiftForm(emptyShift);
    setRegistrationForm(emptyRegistration);
  }

  const session = sessionQuery.data;
  const ContentContainer = embedded ? "section" : "main";

  return (
    <div className={embedded ? "admin-workflow" : "site-shell"}>
      {!embedded && <SiteHeader />}
      <ContentContainer aria-label={embedded ? "Eventmanager" : undefined} className="event-manager-page">
        <header className="event-manager-heading">
          <p className="eyebrow eyebrow--muted">ORGANISATION</p>
          <h1>Eventmanager<span>.</span></h1>
          <p>Verwalte Veranstaltungen, Helferschichten und Anmeldungen.</p>
        </header>

        {(sessionQuery.isLoading || (session?.can_manage_events && eventsQuery.isLoading)) && (
          <div className="detail-loading" role="status">Eventverwaltung wird geladen …</div>
        )}

        {sessionQuery.isError && (
          <div className="message-panel" role="alert"><h2>Dein Konto konnte nicht geprüft werden.</h2></div>
        )}

        {session && !session.authenticated && (
          <div className="message-panel" role="status">
            <div>
              <h2>Melde dich an, um die Eventverwaltung zu öffnen.</h2>
              <Link className="participation-button" to="/login">Einloggen</Link>
            </div>
          </div>
        )}

        {session?.authenticated && !session.can_manage_events && (
          <div className="message-panel" role="alert">
            <div>
              <h2>Dir fehlt die Berechtigung für die Eventverwaltung.</h2>
              <p>Wende dich an eine Person aus dem Organisationsteam, wenn du Zugriff benötigst.</p>
              <Link className="participation-button participation-button--quiet" to="/">Zurück zu den Events</Link>
            </div>
          </div>
        )}

        {session?.can_manage_events && eventsQuery.isError && (
          <div className="message-panel" role="alert">
            <div>
              <h2>Events konnten nicht geladen werden.</h2>
              <button className="text-button" onClick={() => void eventsQuery.refetch()} type="button">Erneut versuchen</button>
            </div>
          </div>
        )}

        {session?.can_manage_events && eventsQuery.data && (
          <>
            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}

            {session.can_create_events && (
              <details className="organizer-panel organizer-create-panel">
                <summary>Neues Event erstellen</summary>
                <div className="organizer-panel__body">
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const token = csrfToken();
                      if (!token) return;
                      runAction(
                        () => createManagedEvent(newEvent, token),
                        "Event wurde erstellt.",
                        (result) => {
                          const created = result as ManagedEvent;
                          setNewEvent(emptyEvent);
                          setSelectedEventId(created.id);
                        },
                      );
                    }}
                  >
                    <EventFields onChange={(field, value) => setNewEvent((current) => ({ ...current, [field]: value }))} values={newEvent} />
                    <button className="participation-button" disabled={actionMutation.isPending} type="submit">Event erstellen</button>
                  </form>
                </div>
              </details>
            )}

            <section aria-labelledby="managed-events-title" className="managed-events-section">
              <div className="participation-section__heading managed-events-heading">
                <div>
                  <p className="eyebrow eyebrow--muted">ALLE VERANSTALTUNGEN</p>
                  <h2 id="managed-events-title">Events verwalten<span>.</span></h2>
                </div>
                <div className="managed-events-toolbar">
                  <label className="profile-field">
                    <span>Sortierung</span>
                    <select onChange={(event) => setSortDirection(event.target.value === "asc" ? "asc" : "desc")} value={sortDirection}>
                      <option value="desc">Neueste zuerst</option>
                      <option value="asc">Älteste zuerst</option>
                    </select>
                  </label>
                  <label className="manager-checkbox">
                    <input checked={hidePastEvents} onChange={(event) => setHidePastEvents(event.target.checked)} type="checkbox" />
                    <span>Vergangene ausblenden</span>
                  </label>
                </div>
              </div>
              {events.length === 0 ? (
                <p className="participation-empty">Es gibt noch keine Events. Lege oben das erste an.</p>
              ) : visibleEvents.length === 0 ? (
                <p className="participation-empty">Keine Events für die aktuellen Filter. Passe die Filter an, um wieder Events zu sehen.</p>
              ) : (
                <div className="managed-event-list">
                  {visibleEvents.map((event) => (
                    <article className={`managed-event-row${selectedEventId === event.id ? " managed-event-row--selected" : ""}`} key={event.id}>
                      <button className="managed-event-row__select" onClick={() => setSelectedEventId(event.id)} type="button">
                        <span className="managed-event-row__name">{event.name}</span>
                        <span className="managed-event-row__meta">
                          {formatOrganizerDate(event.date)} <span>·</span> {event.place || "Ort folgt"}
                        </span>
                      </button>
                      {session.can_edit_events && (
                        <button className="text-button" onClick={() => setSelectedEventId(event.id)} type="button">Bearbeiten</button>
                      )}
                      {session.can_delete_events && (
                        <button
                          className="text-button text-button--danger"
                          onClick={() => {
                            if (window.confirm(`„${event.name}“ wirklich löschen?`)) {
                              const token = csrfToken();
                              if (token) runAction(
                                () => deleteManagedEvent(event.id, token),
                                "Event wurde gelöscht.",
                                () => setSelectedEventId((selected) => selected === event.id ? null : selected),
                              );
                            }
                          }}
                          type="button"
                        >Löschen</button>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>

            {selectedEvent && (
              <section aria-labelledby="selected-event-title" className="selected-event-panel">
                <div className="participation-section__heading">
                  <p className="eyebrow eyebrow--muted">EVENT-KONFIGURATION</p>
                  <h2 id="selected-event-title">{selectedEvent.name}<span>.</span></h2>
                </div>

                {session.can_edit_events && (
                  <form className="organizer-panel organizer-panel__body organizer-edit-form" onSubmit={(event) => {
                    event.preventDefault();
                    const token = csrfToken();
                    if (token) runAction(
                      () => updateManagedEvent(selectedEvent.id, editEvent, token),
                      "Eventänderungen wurden gespeichert.",
                    );
                  }}>
                    <h3>Eventdaten</h3>
                    <EventFields editing onChange={updateEventField} values={editEvent} />
                    <button className="participation-button" disabled={actionMutation.isPending} type="submit">Event speichern</button>
                  </form>
                )}

                {session.can_manage_tasks && <OrganizerTaskManagerPage embedded eventId={selectedEvent.id} />}

                {session.can_manage_shifts && (
                  <div className="organizer-subsection organizer-subsection--shifts">
                    <div className="organizer-subsection__heading">
                      <div>
                        <p className="organizer-subsection__kicker">MIT ANPACKEN</p>
                        <h3>Helferschichten</h3>
                      </div>
                      <div className="organizer-subsection__tools">
                        <span>{selectedEvent.shifts.length}</span>
                        {activeParticipationForm !== "shift" && <button aria-label="Neue Helferschicht hinzufügen" className="organizer-add-button" onClick={() => openShiftForm()} type="button">+ Schicht</button>}
                      </div>
                    </div>
                    {selectedEvent.shifts.map((shift) => (
                      <article className="organizer-item" key={shift.id}>
                        <div>
                          <strong>{shift.type}</strong>
                          <small>{formatOrganizerDate(shift.start)} · {shift.participants} Helfer:innen</small>
                        </div>
                        <div className="organizer-item__actions">
                          <button aria-label={`Helferschicht ${shift.type} bearbeiten`} className="text-button" onClick={() => openShiftForm(shift)} type="button">Bearbeiten</button>
                          <button className="text-button text-button--danger" onClick={() => {
                            const token = csrfToken();
                            if (token && window.confirm("Diese Helferschicht löschen?")) {
                              runAction(
                                () => deleteManagedShift(selectedEvent.id, shift.id, token),
                                "Helferschicht wurde gelöscht.",
                                () => { if (editingShiftId === shift.id) closeParticipationForm(); },
                              );
                            }
                          }} type="button">Löschen</button>
                        </div>
                        <AdminAssignmentManager
                          assignedUsers={shift.assigned_users || []}
                          csrfToken={session.csrf_token || ""}
                          eventId={selectedEvent.id}
                          kind="shift"
                          targetId={shift.id}
                        />
                      </article>
                    ))}
                    {activeParticipationForm === "shift" && <form className="organizer-inline-form" ref={shiftFormRef} tabIndex={-1} onSubmit={(event) => {
                      event.preventDefault();
                      const token = csrfToken();
                      if (!token) return;
                      const run = () => editingShiftId
                        ? updateManagedShift(selectedEvent.id, editingShiftId, shiftForm, token)
                        : createManagedShift(selectedEvent.id, shiftForm, token);
                      runAction(run, editingShiftId ? "Helferschicht wurde geändert." : "Helferschicht wurde erstellt.", () => {
                        setShiftForm(emptyShift);
                        setEditingShiftId(null);
                        setActiveParticipationForm(null);
                      });
                    }}>
                      <h4>{editingShiftId ? "Helferschicht bearbeiten" : "Helferschicht hinzufügen"}</h4>
                      <div className="manager-form-grid">
                        <label className="profile-field">
                          <span>Bezeichnung</span>
                          <input maxLength={20} onChange={(e) => setShiftForm((current) => ({ ...current, type: e.target.value }))} required value={shiftForm.type} />
                        </label>
                        <label className="profile-field">
                          <span>Beginn</span>
                          <input onChange={(e) => setShiftForm((current) => ({ ...current, start: e.target.value }))} type="datetime-local" value={shiftForm.start} />
                        </label>
                        <label className="profile-field">
                          <span>Ende</span>
                          <input onChange={(e) => setShiftForm((current) => ({ ...current, end: e.target.value }))} type="datetime-local" value={shiftForm.end} />
                        </label>
                      </div>
                      <button className="participation-button" disabled={actionMutation.isPending} type="submit">{editingShiftId ? "Schicht speichern" : "Schicht hinzufügen"}</button>
                      <button className="text-button" onClick={closeParticipationForm} type="button">Abbrechen</button>
                    </form>}
                  </div>
                )}

                {session.can_manage_registration_options && (
                  <div className="organizer-subsection organizer-subsection--registrations">
                    <div className="organizer-subsection__heading">
                      <div>
                        <p className="organizer-subsection__kicker">TEILNAHME</p>
                        <h3>Anmeldungen</h3>
                      </div>
                      <div className="organizer-subsection__tools">
                        <span>{selectedEvent.registration_options.length}</span>
                        {activeParticipationForm !== "registration" && <button aria-label="Neue Anmeldung hinzufügen" className="organizer-add-button" onClick={() => openRegistrationForm()} type="button">+ Anmeldung</button>}
                      </div>
                    </div>
                    {selectedEvent.registration_options.map((option) => (
                      <article className="organizer-item" key={option.id}>
                        <div>
                          <strong>{option.name}</strong>
                          <small>{option.visibility} · {option.accept} · {option.deny}</small>
                        </div>
                        <div className="organizer-item__actions">
                          <button aria-label={`Anmeldung ${option.name} bearbeiten`} className="text-button" onClick={() => openRegistrationForm(option)} type="button">Bearbeiten</button>
                          <button className="text-button text-button--danger" onClick={() => {
                            const token = csrfToken();
                            if (token && window.confirm("Diese Anmeldemöglichkeit löschen?")) {
                              runAction(
                                () => deleteManagedRegistration(selectedEvent.id, option.id, token),
                                "Anmeldemöglichkeit wurde gelöscht.",
                                () => { if (editingRegistrationId === option.id) closeParticipationForm(); },
                              );
                            }
                          }} type="button">Löschen</button>
                        </div>
                        <AdminAssignmentManager
                          assignedUsers={option.participants || []}
                          csrfToken={session.csrf_token || ""}
                          eventId={selectedEvent.id}
                          kind="registration"
                          targetId={option.id}
                        />
                      </article>
                    ))}
                    {activeParticipationForm === "registration" && <form className="organizer-inline-form" ref={registrationFormRef} tabIndex={-1} onSubmit={(event) => {
                      event.preventDefault();
                      const token = csrfToken();
                      if (!token) return;
                      const run = () => editingRegistrationId
                        ? updateManagedRegistration(selectedEvent.id, editingRegistrationId, registrationForm, token)
                        : createManagedRegistration(selectedEvent.id, registrationForm, token);
                      runAction(run, editingRegistrationId ? "Anmeldemöglichkeit wurde geändert." : "Anmeldemöglichkeit wurde erstellt.", () => {
                        setRegistrationForm(emptyRegistration);
                        setEditingRegistrationId(null);
                        setActiveParticipationForm(null);
                      });
                    }}>
                      <h4>{editingRegistrationId ? "Anmeldung bearbeiten" : "Anmeldung hinzufügen"}</h4>
                      <div className="manager-form-grid">
                        <label className="profile-field">
                          <span>Name</span>
                          <input maxLength={30} onChange={(e) => setRegistrationForm((current) => ({ ...current, name: e.target.value }))} required value={registrationForm.name} />
                        </label>
                        <label className="profile-field">
                          <span>Sichtbarkeit</span>
                          <VisibilitySelect onChange={(value) => setRegistrationForm((current) => ({ ...current, visibility: value }))} value={registrationForm.visibility} />
                        </label>
                        <label className="profile-field">
                          <span>Anmeldemodus</span>
                          <select onChange={(e) => setRegistrationForm((current) => ({ ...current, accept: e.target.value }))} value={registrationForm.accept}>
                            <option value="geöffnet">Geöffnet</option>
                            <option value="Zeitraum">Zeitraum</option>
                            <option value="geschlossen">Geschlossen</option>
                          </select>
                        </label>
                        <label className="profile-field">
                          <span>Abmeldung</span>
                          <select onChange={(e) => setRegistrationForm((current) => ({ ...current, deny: e.target.value }))} value={registrationForm.deny}>
                            <option value="erlaubt">Erlaubt</option>
                            <option value="verboten">Verboten</option>
                          </select>
                        </label>
                        <label className="profile-field">
                          <span>Beginn des Zeitraums</span>
                          <input onChange={(e) => setRegistrationForm((current) => ({ ...current, start: e.target.value }))} type="datetime-local" value={registrationForm.start} />
                        </label>
                        <label className="profile-field">
                          <span>Ende des Zeitraums{registrationForm.accept === "Zeitraum" ? " *" : ""}</span>
                          <input onChange={(e) => setRegistrationForm((current) => ({ ...current, end: e.target.value }))} required={registrationForm.accept === "Zeitraum"} type="datetime-local" value={registrationForm.end} />
                        </label>
                        <label className="profile-field">
                          <span>Preis in Euro</span>
                          <input min="0" onChange={(e) => setRegistrationForm((current) => ({ ...current, price: e.target.value }))} step="0.01" type="number" value={registrationForm.price} />
                        </label>
                      </div>
                      <button className="participation-button" disabled={actionMutation.isPending} type="submit">{editingRegistrationId ? "Anmeldung speichern" : "Anmeldung hinzufügen"}</button>
                      <button className="text-button" onClick={closeParticipationForm} type="button">Abbrechen</button>
                    </form>}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </ContentContainer>
      {!embedded && <SiteFooter />}
    </div>
  );
}
