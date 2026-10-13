import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import type { FormEvent } from "react";

import { getCurrentSession } from "../api/events";
import AdminAssignmentManager from "../components/AdminAssignmentManager";
import {
  createEventTask,
  deleteEventTask,
  getManagedEventTasks,
  updateEventTask,
  type EventTask,
  type TaskFields,
} from "../api/tasks";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

const taskStatusLabel: Record<string, string> = {
  TakeOverTask: "Offen",
  OnHold: "Pausiert",
  InProgress: "In Arbeit",
  Ready: "Bereit",
  Finished: "Abgeschlossen",
};

const emptyTask: TaskFields = {
  name: "",
  description: "",
  status: "TakeOverTask",
  priority: "mittel",
  visibility: "public",
  deadline: "",
  timeframe_start: "",
  timeframe_end: "",
};

function dateTimeInput(value: string | null) {
  return value ? value.slice(0, 16) : "";
}

function taskToFields(task: EventTask): TaskFields {
  return {
    name: task.name,
    description: task.description,
    status: task.status,
    priority: task.priority,
    visibility: task.visibility,
    deadline: dateTimeInput(task.deadline),
    timeframe_start: dateTimeInput(task.timeframe_start),
    timeframe_end: dateTimeInput(task.timeframe_end),
  };
}

function taskTime(value: string | null) {
  if (!value) return "Nicht festgelegt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Nicht festgelegt";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function OrganizerTaskManagerPage({
  embedded = false,
  eventId: providedEventId,
}: {
  embedded?: boolean;
  eventId?: number;
} = {}) {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number(providedEventId ?? eventIdParam);
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const tasksQuery = useQuery({
    queryKey: ["manage-event-tasks", eventId],
    queryFn: () => getManagedEventTasks(eventId),
    enabled: sessionQuery.data?.can_manage_tasks === true && Number.isInteger(eventId) && eventId > 0,
  });
  const [taskForm, setTaskForm] = useState<TaskFields>(emptyTask);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [taskFormOpen, setTaskFormOpen] = useState(false);
  const taskEditorRef = useRef<HTMLElement>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const actionMutation = useMutation({
    mutationFn: ({ run }: { run: () => Promise<unknown>; message: string; after?: () => void }) => run(),
    onMutate: () => {
      setNotice("");
      setError("");
    },
    onSuccess: async (_, action) => {
      action.after?.();
      setNotice(action.message);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["manage-event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["managed-events"] }),
      ]);
    },
    onError: (actionError) => setError(actionError instanceof Error ? actionError.message : "Vorbereitung konnte nicht gespeichert werden."),
  });
  const board = tasksQuery.data;
  const session = sessionQuery.data;
  const editingTask = board?.tasks.find((task) => task.id === editingTaskId);
  const ContentContainer = embedded ? "section" : "main";

  useEffect(() => {
    if (editingTask) setTaskForm(taskToFields(editingTask));
    else if (!editingTaskId) setTaskForm(emptyTask);
  }, [editingTask, editingTaskId]);

  useEffect(() => {
    if (!taskFormOpen || !taskEditorRef.current) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    taskEditorRef.current.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  }, [taskFormOpen, editingTaskId]);

  function csrfToken() {
    const token = session?.csrf_token;
    if (!token) setError("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
    return token;
  }

  function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = csrfToken();
    if (!token) return;
    const run = editingTaskId
      ? () => updateEventTask(eventId, editingTaskId, taskForm, token)
      : () => createEventTask(eventId, taskForm, token);
    actionMutation.mutate({
      run,
      message: editingTaskId ? "Vorbereitung wurde geändert." : "Vorbereitung wurde erstellt.",
      after: () => {
        setTaskForm(emptyTask);
        setEditingTaskId(null);
        setTaskFormOpen(false);
      },
    });
  }

  function startNewPreparation() {
    setEditingTaskId(null);
    setTaskForm(emptyTask);
    setTaskFormOpen(true);
  }

  function editPreparation(task: EventTask) {
    setEditingTaskId(task.id);
    setTaskForm(taskToFields(task));
    setTaskFormOpen(true);
  }

  function closeTaskForm() {
    setEditingTaskId(null);
    setTaskForm(emptyTask);
    setTaskFormOpen(false);
  }

  return (
    <div className={embedded ? "embedded-preparation-manager" : "site-shell"}>
      {!embedded && <SiteHeader />}
      <ContentContainer aria-label={embedded ? "Vorbereitungsverwaltung" : undefined} className={embedded ? "organizer-subsection organizer-subsection--preparations" : "task-manager-page"}>
        {!embedded && <Link className="back-link" to="/manage/events"><span aria-hidden="true">←</span> Zurück zum Eventmanager</Link>}
        {(sessionQuery.isLoading || (session?.can_manage_tasks && tasksQuery.isLoading)) && (
          <div className="detail-loading" role="status">Vorbereitungen werden geladen …</div>
        )}
        {sessionQuery.isError && <div className="message-panel" role="alert"><h1>Konto konnte nicht geprüft werden.</h1></div>}
        {session && !session.authenticated && (
          <div className="message-panel" role="status">
            <div><h2>Melde dich an, um Vorbereitungen zu verwalten.</h2><Link className="participation-button" to="/login">Einloggen</Link></div>
          </div>
        )}
        {session?.authenticated && !session.can_manage_tasks && (
          <div className="message-panel" role="alert">
            <div>
              <h2>Dir fehlt die Berechtigung, Vorbereitungen zu verwalten.</h2>
              <Link className="participation-button participation-button--quiet" to="/">Zurück zu den Events</Link>
            </div>
          </div>
        )}
        {session?.can_manage_tasks && tasksQuery.isError && (
          <div className="message-panel" role="alert">
            <div><h2>Vorbereitungen konnten nicht geladen werden.</h2><button className="text-button" onClick={() => void tasksQuery.refetch()} type="button">Erneut versuchen</button></div>
          </div>
        )}
        {session?.can_manage_tasks && board && (
          <>
            {embedded ? (
              <div className="organizer-subsection__heading">
                <div>
                  <p className="organizer-subsection__kicker">VORBEREITEN</p>
                  <h3 id="embedded-preparations-title">Vorbereitungen</h3>
                </div>
                <div className="organizer-subsection__tools">
                  <span>{board.tasks.length}</span>
                  {!taskFormOpen && <button aria-label="Vorbereitung hinzufügen" className="organizer-add-button" onClick={startNewPreparation} type="button">+ Vorbereitung</button>}
                </div>
              </div>
            ) : (
              <header className="task-manager-heading">
                <p className="eyebrow eyebrow--muted">EVENTVORBEREITUNGEN</p>
                <h1>{board.event.name}<span>.</span></h1>
                <p>{taskTime(board.event.date)} · {board.event.place || "Ort folgt"}</p>
                <Link className="event-card__link" to={`/events/${eventId}`}>Event ansehen <span aria-hidden="true">→</span></Link>
              </header>
            )}

            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}

            <div className={`task-manager-layout${taskFormOpen ? " task-manager-layout--editing" : ""}`}>
              <section aria-label={embedded ? "Vorbereitungen im Event" : undefined} aria-labelledby={embedded ? undefined : "task-list-title"} className="task-manager-list">
                {!embedded && <div className="task-manager-list__heading">
                  <div className="participation-section__heading">
                    <p className="eyebrow eyebrow--muted">VORBEREITUNGEN</p>
                    <h2 id="task-list-title">Vorbereitungen<span>.</span></h2>
                  </div>
                  {!taskFormOpen && <button aria-label="Vorbereitung hinzufügen" className="organizer-add-button" onClick={startNewPreparation} type="button">+ Vorbereitung</button>}
                </div>}
                {board.tasks.length === 0 ? (
                  <p className="participation-empty">Noch keine Vorbereitungen angelegt.</p>
                ) : (
                  <div className="manager-task-list">
                    {board.tasks.map((task) => (
                      <article className={`manager-task-row${task.id === editingTaskId ? " manager-task-row--selected" : ""}`} key={task.id}>
                        <button className="manager-task-row__select" onClick={() => editPreparation(task)} type="button">
                          <strong>{task.name}</strong>
                          <small>{taskStatusLabel[task.status] || task.status} · {task.visibility} · {task.helper_count} Helfer:innen</small>
                          <span>Bearbeiten →</span>
                        </button>
                        <button className="text-button text-button--danger" onClick={() => {
                          const token = csrfToken();
                          if (token && window.confirm(`Vorbereitung „${task.name}“ löschen?`)) {
                            actionMutation.mutate({
                              run: () => deleteEventTask(eventId, task.id, token),
                              message: "Vorbereitung wurde gelöscht.",
                              after: () => { if (editingTaskId === task.id) closeTaskForm(); },
                            });
                          }
                        }} type="button">Löschen</button>
                        {board.can_assign_helpers && (
                          <AdminAssignmentManager
                            assignedUsers={task.helpers || []}
                            csrfToken={session?.csrf_token || ""}
                            eventId={eventId}
                            kind="task"
                            targetId={task.id}
                          />
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>

              {taskFormOpen && <section aria-labelledby="task-form-title" className="task-editor-panel" ref={taskEditorRef}>
                <div className="participation-section__heading">
                  <p className="eyebrow eyebrow--muted">{editingTaskId ? "BEARBEITEN" : "NEU ANLEGEN"}</p>
                  <h2 id="task-form-title">{editingTaskId ? "Vorbereitung ändern" : "Vorbereitung erstellen"}<span>.</span></h2>
                </div>
                <form className="organizer-inline-form" onSubmit={submitTask}>
                  <label className="profile-field">
                    <span>Name der Vorbereitung</span>
                    <input maxLength={50} onChange={(e) => setTaskForm((current) => ({ ...current, name: e.target.value }))} required value={taskForm.name} />
                  </label>
                  <label className="profile-field">
                    <span>Beschreibung</span>
                    <textarea maxLength={500} onChange={(e) => setTaskForm((current) => ({ ...current, description: e.target.value }))} rows={4} value={taskForm.description} />
                  </label>
                  <div className="manager-form-grid">
                    <label className="profile-field">
                      <span>Status</span>
                      <select onChange={(e) => setTaskForm((current) => ({ ...current, status: e.target.value }))} value={taskForm.status}>
                        <option value="TakeOverTask">Offen</option>
                        <option value="OnHold">Pausiert</option>
                        <option value="InProgress">In Arbeit</option>
                        <option value="Ready">Bereit</option>
                        <option value="Finished">Abgeschlossen</option>
                      </select>
                    </label>
                    <label className="profile-field">
                      <span>Priorität</span>
                      <select onChange={(e) => setTaskForm((current) => ({ ...current, priority: e.target.value }))} value={taskForm.priority}>
                        <option value="niedrig">Niedrig</option>
                        <option value="mittel">Mittel</option>
                        <option value="hoch">Hoch</option>
                      </select>
                    </label>
                    <label className="profile-field">
                      <span>Sichtbarkeit</span>
                      <select onChange={(e) => setTaskForm((current) => ({ ...current, visibility: e.target.value }))} value={taskForm.visibility}>
                        <option value="public">Öffentlich</option>
                        <option value="student">Studierende</option>
                        <option value="member">Mitglieder</option>
                        <option value="private">Privat</option>
                      </select>
                    </label>
                    <label className="profile-field">
                      <span>Deadline</span>
                      <input onChange={(e) => setTaskForm((current) => ({ ...current, deadline: e.target.value }))} type="datetime-local" value={taskForm.deadline} />
                    </label>
                    <label className="profile-field">
                      <span>Geplant ab</span>
                      <input onChange={(e) => setTaskForm((current) => ({ ...current, timeframe_start: e.target.value }))} type="datetime-local" value={taskForm.timeframe_start} />
                    </label>
                    <label className="profile-field">
                      <span>Geplant bis</span>
                      <input onChange={(e) => setTaskForm((current) => ({ ...current, timeframe_end: e.target.value }))} type="datetime-local" value={taskForm.timeframe_end} />
                    </label>
                  </div>
                  <div className="task-editor-actions">
                    <button className="participation-button" disabled={actionMutation.isPending} type="submit">
                      {editingTaskId ? "Vorbereitung speichern" : "Vorbereitung erstellen"}
                    </button>
                    <button className="text-button" onClick={closeTaskForm} type="button">Abbrechen</button>
                  </div>
                </form>
              </section>}
            </div>
          </>
        )}
      </ContentContainer>
      {!embedded && <SiteFooter />}
    </div>
  );
}
