import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";

import {
  deleteAdminContact,
  deleteAdminUser,
  getAdminContacts,
  getAdminRoleRequests,
  getAdminUsers,
  reviewAdminRoleRequest,
  setAdminContactHandled,
  updateAdminUser,
  type AdminUser,
  type AdminUserForm,
} from "../api/admin";
import { getCurrentSession } from "../api/events";
import { getAdminFinance } from "../api/finance";
import EventManagerPage from "./EventManagerPage";
import { getManagedTasks, type ManagedTaskOverviewItem } from "../api/tasks";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

const AdminFinancePanel = lazy(() => import("./FinancePages").then((module) => ({ default: module.AdminFinancePanel })));
const AdminDrinkMenuPanel = lazy(() => import("./DrinkMenuPages").then((module) => ({ default: module.AdminDrinkMenuPanel })));

type AdminTab = "users" | "role-requests" | "contacts" | "events" | "tasks" | "finances" | "drinks";

function userToForm(user: AdminUser): AdminUserForm {
  return {
    username: user.username,
    role: user.role,
    surname: user.surname,
    lastname: user.lastname,
    email: user.email,
    hs_email: user.hs_email,
    street: user.street,
    street_no: user.street_no,
    city: user.city,
    postalcode: user.postalcode,
    password: "",
    password_confirm: "",
    verify_mail: false,
  };
}

function formattedLastLogin(value: string | null) {
  if (!value) return "Noch nie angemeldet";
  const [date, time] = value.replace("T", " ").split(" ");
  const [year, month, day] = date.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}${time ? ` ${time.slice(0, 5)}` : ""}`;
}

function formattedTaskDeadline(value: string | null) {
  if (!value) return "Kein Termin";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Ungültiger Termin";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

const taskPriorityRank: Record<string, number> = { niedrig: 1, mittel: 2, hoch: 3 };
const taskPriorityLabels: Record<string, string> = { niedrig: "Niedrig", mittel: "Mittel", hoch: "Hoch" };
const taskStatusLabels: Record<string, string> = {
  TakeOverTask: "Offen",
  OnHold: "Pausiert",
  InProgress: "In Arbeit",
  Ready: "Bereit",
  Finished: "Abgeschlossen",
};

function AdminUsersPanel({ csrfToken, canView, canUpdate, canDelete, currentUsername }: { csrfToken: string; canView: boolean; canUpdate: boolean; canDelete: boolean; currentUsername: string }) {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: getAdminUsers, enabled: canView });
  const [search, setSearch] = useState("");
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [form, setForm] = useState<AdminUserForm | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [lastLoginDescending, setLastLoginDescending] = useState(true);
  const users = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("de-DE");
    return (usersQuery.data?.users ?? [])
      .filter((user) => [user.username, user.surname, user.lastname, user.email, user.role]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("de-DE").includes(normalizedSearch)))
      .sort((left, right) => {
        if (!left.last_login) return right.last_login ? 1 : 0;
        if (!right.last_login) return -1;
        const order = left.last_login.localeCompare(right.last_login);
        return lastLoginDescending ? -order : order;
      });
  }, [lastLoginDescending, search, usersQuery.data?.users]);
  const updateMutation = useMutation({
    mutationFn: ({ user, values }: { user: AdminUser; values: AdminUserForm }) => updateAdminUser(user.uid, values, csrfToken),
    onSuccess: async (result) => {
      setEditingUser(null);
      setForm(null);
      setNotice(result.verification_warning
        ? "Nutzerdaten gespeichert; die Verifizierungsmail konnte nicht gestartet werden."
        : "Nutzerdaten gespeichert.");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setError(error instanceof Error ? error.message : "Nutzer konnte nicht gespeichert werden."),
  });
  const deleteMutation = useMutation({
    mutationFn: (user: AdminUser) => deleteAdminUser(user.uid, csrfToken),
    onSuccess: async () => {
      setNotice("Nutzerkonto gelöscht.");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (error) => setError(error instanceof Error ? error.message : "Nutzerkonto konnte nicht gelöscht werden."),
  });

  useEffect(() => {
    setError("");
    if (editingUser) setForm(userToForm(editingUser));
  }, [editingUser]);

  function updateField(field: keyof AdminUserForm, value: string | boolean) {
    setForm((current) => current ? { ...current, [field]: value } : current);
  }

  return (
    <section aria-labelledby="admin-users-title" className="admin-panel">
      <div className="admin-panel__heading">
        <div><p className="eyebrow eyebrow--muted">KONTEN UND ROLLEN</p><h2 id="admin-users-title">Benutzerverwaltung<span>.</span></h2></div>
        <label className="search-field admin-search">
          <span className="visually-hidden">Benutzer suchen</span>
          <input onChange={(event) => setSearch(event.target.value)} placeholder="Benutzer suchen" type="search" value={search} />
        </label>
      </div>
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      {!canView && <p className="participation-empty">Dir fehlt die Berechtigung, Benutzerkonten zu lesen.</p>}
      {usersQuery.isLoading && <p className="participation-empty" role="status">Benutzer werden geladen …</p>}
      {usersQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Benutzer konnten nicht geladen werden.</p>}
      {!usersQuery.isLoading && users.length === 0 && <p className="participation-empty">Keine Benutzer gefunden.</p>}
      {users.length > 0 && (
        <div className="admin-user-list-scroll">
          <table aria-label="Benutzerliste" className="admin-user-table">
            <thead>
              <tr>
                <th scope="col">Benutzer</th>
                <th scope="col">Rolle</th>
                <th scope="col">E-Mail</th>
                <th scope="col">Hochschul-E-Mail</th>
                <th aria-sort={lastLoginDescending ? "descending" : "ascending"} scope="col">
                  <button className="admin-sort-button" onClick={() => setLastLoginDescending((descending) => !descending)} type="button">
                    Zuletzt aktiv <span aria-hidden="true">{lastLoginDescending ? "↓" : "↑"}</span>
                  </button>
                </th>
                <th scope="col"><span className="visually-hidden">Aktionen</span></th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.uid}>
                  <td>
                    <div className="admin-user-table__identity">
                      <span aria-hidden="true" className="admin-user-avatar">{(user.surname || user.username).slice(0, 1).toLocaleUpperCase("de-DE")}</span>
                      <span><strong>{user.username}</strong><small>{[user.surname, user.lastname].filter(Boolean).join(" ") || "Name nicht hinterlegt"}</small></span>
                    </div>
                  </td>
                  <td><span className="admin-user-card__role">{user.role}</span></td>
                  <td><span className="admin-user-table__email">{user.email || "—"}</span>{user.email && <small className="admin-user-table__verification">{user.email_confirmed ? "Bestätigt" : "Nicht bestätigt"}</small>}</td>
                  <td><span className="admin-user-table__email">{user.hs_email || "—"}</span>{user.hs_email && <small className="admin-user-table__verification">{user.hs_email_confirmed ? "Bestätigt" : "Nicht bestätigt"}</small>}</td>
                  <td><time>{formattedLastLogin(user.last_login)}</time></td>
                  <td>
                    <div className="admin-user-card__actions">
                      {canUpdate && <button className="text-button" onClick={() => setEditingUser(user)} type="button">Bearbeiten</button>}
                      {canDelete && (
                        <button
                          className="text-button text-button--danger"
                          disabled={deleteMutation.isPending || user.username === currentUsername}
                          onClick={() => {
                            if (window.confirm(`Benutzerkonto „${user.username}“ wirklich löschen?`)) deleteMutation.mutate(user);
                          }}
                          type="button"
                          title={user.username === currentUsername ? "Das eigene Konto kann hier nicht gelöscht werden." : undefined}
                        >Löschen</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editingUser && form && (
        <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditingUser(null); }}>
          <section aria-labelledby="admin-user-edit-title" aria-modal="true" className="admin-edit-dialog" role="dialog">
            <header className="admin-edit-dialog__heading">
              <div><p className="eyebrow eyebrow--muted">BENUTZERKONTO</p><h2 id="admin-user-edit-title">{editingUser.username} bearbeiten</h2></div>
              <button aria-label="Schließen" className="dialog-close" onClick={() => setEditingUser(null)} type="button">×</button>
            </header>
            <form className="admin-edit-form" onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              updateMutation.mutate({ user: editingUser, values: form });
            }}>
              <div className="manager-form-grid">
                <label className="profile-field"><span>Benutzername</span><input maxLength={20} minLength={3} onChange={(e) => updateField("username", e.target.value)} required value={form.username} /></label>
                <label className="profile-field"><span>Rolle</span><select onChange={(e) => updateField("role", e.target.value)} value={form.role}>{(usersQuery.data?.roles ?? []).map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
                <label className="profile-field"><span>Vorname</span><input maxLength={20} onChange={(e) => updateField("surname", e.target.value)} value={form.surname} /></label>
                <label className="profile-field"><span>Nachname</span><input maxLength={20} onChange={(e) => updateField("lastname", e.target.value)} value={form.lastname} /></label>
                <label className="profile-field"><span>Ausweich-E-Mail</span><input maxLength={30} onChange={(e) => updateField("email", e.target.value)} type="email" value={form.email} /></label>
                <label className="profile-field"><span>Hochschul-E-Mail</span><input maxLength={30} onChange={(e) => updateField("hs_email", e.target.value)} type="email" value={form.hs_email} /></label>
                <label className="profile-field"><span>Straße</span><input maxLength={25} onChange={(e) => updateField("street", e.target.value)} value={form.street} /></label>
                <label className="profile-field"><span>Hausnummer</span><input maxLength={10} onChange={(e) => updateField("street_no", e.target.value)} value={form.street_no} /></label>
                <label className="profile-field"><span>Stadt</span><input maxLength={25} onChange={(e) => updateField("city", e.target.value)} value={form.city} /></label>
                <label className="profile-field"><span>Postleitzahl</span><input maxLength={5} onChange={(e) => updateField("postalcode", e.target.value)} value={form.postalcode} /></label>
                <label className="profile-field"><span>Neues Passwort</span><input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password", e.target.value)} type="password" value={form.password} /></label>
                <label className="profile-field"><span>Passwort bestätigen</span><input autoComplete="new-password" maxLength={30} minLength={8} onChange={(e) => updateField("password_confirm", e.target.value)} type="password" value={form.password_confirm} /></label>
              </div>
              <label className="manager-checkbox"><input checked={form.verify_mail} onChange={(e) => updateField("verify_mail", e.target.checked)} type="checkbox" /><span>Verifizierungsmail an hinterlegte, unbestätigte E-Mails senden</span></label>
              <div className="admin-edit-dialog__actions">
                <button className="participation-button" disabled={updateMutation.isPending} type="submit">{updateMutation.isPending ? "Wird gespeichert …" : "Nutzerdaten speichern"}</button>
                <button className="participation-button participation-button--quiet" onClick={() => setEditingUser(null)} type="button">Abbrechen</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}

function AdminContactsPanel({ canDelete, canHandle, csrfToken }: { canDelete: boolean; canHandle: boolean; csrfToken: string }) {
  const queryClient = useQueryClient();
  const contactsQuery = useQuery({ queryKey: ["admin-contacts"], queryFn: getAdminContacts });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState<"open" | "handled" | "all">("open");
  const deleteMutation = useMutation({
    mutationFn: (uid: string) => deleteAdminContact(uid, csrfToken),
    onSuccess: async () => {
      setNotice("Anfrage gelöscht.");
      await queryClient.invalidateQueries({ queryKey: ["admin-contacts"] });
    },
    onError: (error) => setError(error instanceof Error ? error.message : "Anfrage konnte nicht gelöscht werden."),
  });
  const handledMutation = useMutation({
    mutationFn: ({ uid, handled }: { uid: string; handled: boolean }) => setAdminContactHandled(uid, handled, csrfToken),
    onSuccess: async (_, values) => {
      setError("");
      setNotice(values.handled ? "Anfrage als erledigt markiert." : "Anfrage wieder geöffnet.");
      await queryClient.invalidateQueries({ queryKey: ["admin-contacts"] });
    },
    onError: (error) => setError(error instanceof Error ? error.message : "Bearbeitungsstatus konnte nicht gespeichert werden."),
  });
  const contacts = contactsQuery.data?.contacts ?? [];
  const openCount = contacts.filter((contact) => !contact.is_handled).length;
  const visibleContacts = contacts.filter((contact) => filter === "all" || (filter === "handled" ? contact.is_handled : !contact.is_handled));

  return (
    <section aria-labelledby="admin-contacts-title" className="admin-panel">
      <div className="admin-panel__heading">
        <div><p className="eyebrow eyebrow--muted">POSTEINGANG</p><h2 id="admin-contacts-title">Kontaktanfragen<span>.</span></h2></div>
        <span className="admin-count-badge">{openCount} offen</span>
      </div>
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      {contactsQuery.isLoading && <p className="participation-empty" role="status">Anfragen werden geladen …</p>}
      {contactsQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Anfragen konnten nicht geladen werden.</p>}
      {!contactsQuery.isLoading && !contactsQuery.isError && contacts.length > 0 && (
        <div aria-label="Kontaktanfragen filtern" className="admin-contact-filters">
          {(["open", "handled", "all"] as const).map((value) => (
            <button aria-pressed={filter === value} className={filter === value ? "is-active" : ""} key={value} onClick={() => setFilter(value)} type="button">
              {value === "open" ? `Offen (${openCount})` : value === "handled" ? "Erledigt" : "Alle"}
            </button>
          ))}
        </div>
      )}
      {!contactsQuery.isLoading && !contactsQuery.isError && visibleContacts.length === 0 && <p className="participation-empty">{filter === "handled" ? "Es gibt keine erledigten Kontaktanfragen." : filter === "all" ? "Es gibt keine Kontaktanfragen." : "Es gibt keine offenen Kontaktanfragen."}</p>}
      <div className="admin-contact-grid">
        {visibleContacts.map((contact) => (
          <article className={`admin-contact-card${contact.is_handled ? " admin-contact-card--handled" : ""}`} key={contact.uid}>
            <header>
              <div><p className="eyebrow eyebrow--muted">{contact.category}</p><h3>{[contact.surname, contact.lastname].filter(Boolean).join(" ") || "Anonym"}</h3>{contact.is_handled && <small>Erledigt{contact.handled_by_username ? ` von ${contact.handled_by_username}` : ""}</small>}</div>
              <div className="admin-contact-card__actions">
                {canHandle && <button className="text-button" disabled={handledMutation.isPending} onClick={() => handledMutation.mutate({ uid: contact.uid, handled: !contact.is_handled })} type="button">{contact.is_handled ? "Wieder öffnen" : "Als erledigt markieren"}</button>}
              {canDelete && <button className="text-button text-button--danger" disabled={deleteMutation.isPending} onClick={() => {
                if (window.confirm("Diese Kontaktanfrage wirklich löschen?")) deleteMutation.mutate(contact.uid);
              }} type="button">Löschen</button>}
              </div>
            </header>
            {contact.email
              ? <a className="admin-contact-card__email" href={`mailto:${contact.email}`}>{contact.email}</a>
              : <span className="admin-contact-card__email">Keine E-Mail angegeben</span>}
            <p className="admin-contact-card__message">{contact.message}</p>
            <small>{contact.creation || "Erstellungsdatum unbekannt"}{contact.handled_at ? ` · erledigt ${contact.handled_at}` : ""}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function AdminRoleRequestsPanel({ csrfToken, allowed }: { csrfToken: string; allowed: boolean }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const roleRequestsQuery = useQuery({
    queryKey: ["admin-role-requests"],
    queryFn: getAdminRoleRequests,
    enabled: allowed,
  });
  const reviewMutation = useMutation({
    mutationFn: ({ id, decision, note }: { id: number; decision: "approve" | "reject"; note: string }) =>
      reviewAdminRoleRequest(id, decision, note, csrfToken),
    onSuccess: async (_, values) => {
      setError("");
      setNotes((current) => ({ ...current, [values.id]: "" }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-role-requests"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
        queryClient.invalidateQueries({ queryKey: ["current-session"] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Rollenantrag konnte nicht bearbeitet werden."),
  });

  if (!allowed) return <p className="participation-empty">Dir fehlt die Berechtigung, Rollenänderungen zu prüfen.</p>;
  if (roleRequestsQuery.isLoading) return <p className="participation-empty" role="status">Rollenanträge werden geladen …</p>;
  if (roleRequestsQuery.isError) return <p className="action-feedback action-feedback--error" role="alert">Rollenanträge konnten nicht geladen werden.</p>;
  const requests = roleRequestsQuery.data?.requests ?? [];

  return (
    <section className="admin-role-requests">
      <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">BENUTZERROLLEN</p><h2>Rollenanträge<span>.</span></h2></div><span>{requests.length} offen</span></header>
       <p className="finance-help-text">Mitglied wird per Antrag vergeben. Öffentliche Rollen kann die Person selbst im Profil wechseln; Moderator und Admin werden durch die Verwaltung vergeben. Beitragsmitgliedschaften werden separat verwaltet.</p>
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      {requests.length === 0 ? <p className="participation-empty">Keine offenen Rollenänderungsanträge.</p> : (
        <div className="finance-request-list">
          {requests.map((item) => (
            <article className="finance-request-card" key={item.id}>
              <div className="finance-request-card__identity">
                <div><strong>{[item.surname, item.lastname].filter(Boolean).join(" ") || item.username}</strong><small>@{item.username} · {item.current_role} → {item.requested_role} · {formattedLastLogin(item.submitted_at)}</small></div>
                <span className="admin-user-card__role">{item.requested_role}</span>
              </div>
              <p>{item.request_note}</p>
              <label className="profile-field"><span>Prüfnotiz (bei Ablehnung erforderlich)</span><textarea maxLength={1000} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} rows={2} value={notes[item.id] || ""} /></label>
              <div className="finance-inline-actions">
                <button className="participation-button" disabled={reviewMutation.isPending} onClick={() => reviewMutation.mutate({ id: item.id, decision: "approve", note: notes[item.id] || "" })} type="button">Rolle genehmigen</button>
                <button className="text-button text-button--danger" disabled={reviewMutation.isPending || !(notes[item.id] || "").trim()} onClick={() => reviewMutation.mutate({ id: item.id, decision: "reject", note: notes[item.id] || "" })} type="button">Ablehnen</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function AdminTasksPanel({ allowed }: { allowed: boolean }) {
  const tasksQuery = useQuery({ queryKey: ["admin-task-overview"], queryFn: getManagedTasks, enabled: allowed });
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"deadline" | "priority">("deadline");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const allTasks = tasksQuery.data?.tasks ?? [];
  const tasks = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("de-DE");
    return allTasks
      .filter((task) => [task.name, task.event_name, task.priority, task.status]
        .some((value) => value.toLocaleLowerCase("de-DE").includes(normalizedSearch)))
      .sort((left, right) => {
        if (sortBy === "priority") {
          const priorityOrder = (taskPriorityRank[right.priority.toLowerCase()] || 0) - (taskPriorityRank[left.priority.toLowerCase()] || 0);
          if (priorityOrder) return sortDirection === "desc" ? priorityOrder : -priorityOrder;
        }
        let deadlineOrder = 0;
        if (!left.deadline) deadlineOrder = right.deadline ? 1 : 0;
        else if (!right.deadline) deadlineOrder = -1;
        else deadlineOrder = new Date(left.deadline).getTime() - new Date(right.deadline).getTime();
        if (sortBy === "deadline" && left.deadline && right.deadline && sortDirection === "desc") deadlineOrder *= -1;
        if (deadlineOrder) return deadlineOrder;
        if (sortBy === "priority") {
          const priorityOrder = (taskPriorityRank[right.priority.toLowerCase()] || 0) - (taskPriorityRank[left.priority.toLowerCase()] || 0);
          if (priorityOrder) return priorityOrder;
        }
        return left.name.localeCompare(right.name, "de-DE");
      });
  }, [allTasks, search, sortBy, sortDirection]);

  function chooseSort(nextSort: "deadline" | "priority") {
    if (sortBy === nextSort) setSortDirection((direction) => direction === "asc" ? "desc" : "asc");
    else {
      setSortBy(nextSort);
      setSortDirection(nextSort === "priority" ? "desc" : "asc");
    }
  }

  return (
    <section aria-labelledby="admin-tasks-title" className="admin-panel">
      <div className="admin-panel__heading">
        <div><p className="eyebrow eyebrow--muted">ÜBER ALLE EVENTS</p><h2 id="admin-tasks-title">Vorbereitungsübersicht<span>.</span></h2></div>
        {allowed && (
          <label className="search-field admin-search">
            <span className="visually-hidden">Vorbereitungen suchen</span>
            <input onChange={(event) => setSearch(event.target.value)} placeholder="Vorbereitungen suchen" type="search" value={search} />
          </label>
        )}
      </div>
      {!allowed && <p className="participation-empty">Dir fehlt die Berechtigung für diesen Bereich.</p>}
      {allowed && tasksQuery.isLoading && <p className="participation-empty" role="status">Vorbereitungen werden geladen …</p>}
      {allowed && tasksQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Vorbereitungsübersicht konnte nicht geladen werden.</p>}
      {allowed && tasksQuery.data && tasks.length === 0 && <p className="participation-empty">Keine passenden Vorbereitungen gefunden.</p>}
      {allowed && tasks.length > 0 && (
        <div className="admin-task-table-scroll">
          <table className="admin-task-table">
            <thead>
              <tr>
                <th scope="col">Vorbereitung</th>
                <th scope="col">Event</th>
                <th aria-sort={sortBy === "priority" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"} scope="col">
                  <button className="admin-sort-button" onClick={() => chooseSort("priority")} type="button">Priorität {sortBy === "priority" ? <span aria-hidden="true">{sortDirection === "asc" ? "↑" : "↓"}</span> : null}</button>
                </th>
                <th aria-sort={sortBy === "deadline" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"} scope="col">
                  <button className="admin-sort-button" onClick={() => chooseSort("deadline")} type="button">Fällig am {sortBy === "deadline" ? <span aria-hidden="true">{sortDirection === "asc" ? "↑" : "↓"}</span> : null}</button>
                </th>
                <th scope="col">Status</th>
                <th scope="col">Helfer:innen</th>
                <th scope="col"><span className="visually-hidden">Aktionen</span></th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task: ManagedTaskOverviewItem) => (
                <tr key={task.id}>
                  <td><strong>{task.name}</strong><small>{task.visibility}</small></td>
                  <td>{task.event_name}</td>
                  <td><span className={`admin-task-priority admin-task-priority--${task.priority.toLowerCase()}`}>{taskPriorityLabels[task.priority.toLowerCase()] || task.priority || "—"}</span></td>
                  <td>{formattedTaskDeadline(task.deadline)}</td>
                  <td>{taskStatusLabels[task.status] || task.status || "—"}</td>
                  <td>{task.helper_count}</td>
                  <td><Link className="event-card__link" to={`/manage/events/${task.event_id}/tasks`}>Öffnen <span aria-hidden="true">→</span></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function AdminDashboardPage() {
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const session = sessionQuery.data;
  const contactCountsQuery = useQuery({
    queryKey: ["admin-contacts"],
    queryFn: getAdminContacts,
    enabled: session?.can_manage_contacts === true,
  });
  const roleRequestCountsQuery = useQuery({
    queryKey: ["admin-role-requests"],
    queryFn: getAdminRoleRequests,
    enabled: session?.can_update_users === true,
  });
  const financeCountsQuery = useQuery({
    queryKey: ["admin-finance"],
    queryFn: getAdminFinance,
    enabled: session?.can_manage_finances === true,
  });
  const openContactCount = (contactCountsQuery.data?.contacts ?? []).filter((contact) => !contact.is_handled).length;
  const roleRequestCount = roleRequestCountsQuery.data?.requests.length ?? 0;
  const financeRequestCount = financeCountsQuery.data?.requests.length ?? 0;
  const tabs: Array<{ id: AdminTab; label: string; badge?: number }> = [
    { id: "users", label: "Benutzer" },
    ...(session?.can_update_users ? [{ id: "role-requests" as const, label: "Rollenanträge", badge: roleRequestCount }] : []),
    { id: "contacts", label: "Kontaktanfragen", badge: openContactCount },
    { id: "events", label: "Events" },
    { id: "tasks", label: "Vorbereitungen" },
  ];
  if (session?.can_manage_finances) tabs.push({ id: "finances", label: "Finanzen", badge: financeRequestCount });
  if (session?.can_manage_drink_menu) tabs.push({ id: "drinks", label: "Getränkekarte" });

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="admin-dashboard-page">
        <header className="admin-dashboard-heading">
          <p className="eyebrow eyebrow--muted">INTERNE VERWALTUNG</p>
          <h1>Admintool<span>.</span></h1>
          <p>Benutzer, Anfragen und Veranstaltungen verwalten.</p>
        </header>
        {sessionQuery.isLoading && <div className="detail-loading" role="status">Berechtigung wird geprüft …</div>}
        {sessionQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Dein Konto konnte nicht geprüft werden.</p>}
        {session && !session.authenticated && (
          <div className="message-panel" role="status"><div><h2>Melde dich an, um das Admintool zu öffnen.</h2><Link className="participation-button" to="/login">Einloggen</Link></div></div>
        )}
        {session?.authenticated && !session.can_admin_panel && (
          <div className="message-panel" role="alert"><div><h2>Dir fehlt die Berechtigung für das Admintool.</h2><Link className="participation-button participation-button--quiet" to="/events">Zurück zu den Events</Link></div></div>
        )}
        {session?.can_admin_panel && (
          <>
            <div aria-label="Admintool Bereiche" className="admin-tabs" role="tablist">
              {tabs.map((tab) => (
                <button aria-selected={activeTab === tab.id} className={activeTab === tab.id ? "admin-tab admin-tab--active" : "admin-tab"} key={tab.id} onClick={() => setActiveTab(tab.id)} role="tab" type="button">
                  {tab.label}{Boolean(tab.badge) && <span aria-hidden="true" className="admin-tab-indicator">{tab.badge}</span>}
                </button>
              ))}
            </div>
            <div className="admin-tab-panel" role="tabpanel">
              {activeTab === "users" && <AdminUsersPanel csrfToken={session.csrf_token || ""} canView={session.can_manage_users === true} canUpdate={session.can_update_users === true} canDelete={session.can_delete_users === true} currentUsername={session.username || ""} />}
              {activeTab === "role-requests" && <AdminRoleRequestsPanel allowed={session.can_update_users === true} csrfToken={session.csrf_token || ""} />}
              {activeTab === "contacts" && <AdminContactsPanel canDelete={session.can_delete_contacts === true} canHandle={session.can_manage_contacts === true} csrfToken={session.csrf_token || ""} />}
              {activeTab === "events" && session.can_manage_events === true && <EventManagerPage embedded />}
              {activeTab === "events" && session.can_manage_events !== true && <p className="participation-empty">Dir fehlt die Berechtigung für diesen Bereich.</p>}
              {activeTab === "tasks" && <AdminTasksPanel allowed={session.can_manage_tasks === true} />}
              {activeTab === "finances" && session.can_manage_finances === true && (
                <Suspense fallback={<p className="detail-loading" role="status">Finanzen werden geladen …</p>}>
                  <AdminFinancePanel csrfToken={session.csrf_token || ""} />
                </Suspense>
              )}
              {activeTab === "drinks" && session.can_manage_drink_menu === true && (
                <Suspense fallback={<p className="detail-loading" role="status">Getränkekarte wird geladen …</p>}>
                  <AdminDrinkMenuPanel csrfToken={session.csrf_token || ""} />
                </Suspense>
              )}
            </div>
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
