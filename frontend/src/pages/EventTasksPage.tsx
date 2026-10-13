import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { getCurrentSession } from "../api/events";
import { getEventTasks, joinEventTask, leaveEventTask, type EventTask } from "../api/tasks";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

function formatTaskDate(value: string | null): string {
  if (!value) return "Zeit folgt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Zeit folgt";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

const taskStatusLabel: Record<string, string> = {
  TakeOverTask: "Offen",
  OnHold: "Pausiert",
  InProgress: "In Arbeit",
  Ready: "Bereit",
  Finished: "Abgeschlossen",
};

function TaskCard({
  task,
  authenticated,
  canHelp,
  busy,
  onJoin,
  onLeave,
}: {
  task: EventTask;
  authenticated: boolean;
  canHelp: boolean;
  busy: boolean;
  onJoin: () => void;
  onLeave: () => void;
}) {
  return (
    <article className="task-card">
      <div className="task-card__heading">
        <div>
          <p className="eyebrow eyebrow--muted">{task.priority || "Vorbereitung"}</p>
          <h3>{task.name}</h3>
        </div>
        <span className={`task-status task-status--${task.status.toLowerCase()}`}>
          {taskStatusLabel[task.status] || task.status}
        </span>
      </div>
      {task.description && <p className="task-card__description">{task.description}</p>}
      <div className="task-card__meta">
        {task.deadline && <span>Deadline: {formatTaskDate(task.deadline)}</span>}
        {(task.timeframe_start || task.timeframe_end) && (
          <span>
            Geplant: {formatTaskDate(task.timeframe_start)} – {formatTaskDate(task.timeframe_end)}
          </span>
        )}
        <span>{task.helper_count} {task.helper_count === 1 ? "Helfer:in" : "Helfer:innen"}</span>
      </div>
      <div className="task-card__action">
        {task.assigned_to_me ? (
          <button className="participation-button participation-button--quiet" disabled={busy} onClick={onLeave} type="button">
            Nicht mehr helfen
          </button>
        ) : task.can_join ? (
          <button className="participation-button" disabled={busy} onClick={onJoin} type="button">
            Bei dieser Vorbereitung mithelfen
          </button>
        ) : !authenticated && task.visibility === "public" ? (
          <Link className="participation-button" to="/login">Einloggen und helfen</Link>
        ) : canHelp ? (
          <span className="task-card__closed">Aktuell nicht übernehmbar</span>
        ) : (
          <span className="task-card__closed">Für deine Rolle nicht verfügbar</span>
        )}
      </div>
    </article>
  );
}

export default function EventTasksPage() {
  const { eventId: eventIdParam } = useParams();
  const eventId = Number(eventIdParam);
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const boardQuery = useQuery({
    queryKey: ["event-tasks", eventId],
    queryFn: () => getEventTasks(eventId),
    enabled: Number.isInteger(eventId) && eventId > 0,
  });
  const actionMutation = useMutation({
    mutationFn: ({ taskId, action, csrfToken }: { taskId: number; action: "join" | "leave"; csrfToken: string }) =>
      action === "join" ? joinEventTask(taskId, csrfToken) : leaveEventTask(taskId, csrfToken),
    onMutate: () => {
      setNotice("");
      setError("");
    },
    onSuccess: async (_, action) => {
      setNotice(action.action === "join" ? "Du bist für diese Vorbereitung eingetragen." : "Du bist aus dieser Vorbereitung ausgetragen.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["managed-events"] }),
      ]);
    },
    onError: (actionError) => setError(actionError instanceof Error ? actionError.message : "Die Aktion ist fehlgeschlagen."),
  });
  const session = sessionQuery.data;
  const board = boardQuery.data;

  function submitTaskAction(task: EventTask, action: "join" | "leave") {
    if (!session?.authenticated || !session.csrf_token) {
      setError("Bitte melde dich an, um bei einer Vorbereitung mitzuhelfen.");
      return;
    }
    actionMutation.mutate({ taskId: task.id, action, csrfToken: session.csrf_token });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="event-tasks-page">
        <Link className="back-link" to={`/events/${eventId}`}><span aria-hidden="true">←</span> Zurück zum Event</Link>
        {(sessionQuery.isLoading || boardQuery.isLoading) && <div className="detail-loading" role="status">Vorbereitungen werden geladen …</div>}
        {(sessionQuery.isError || boardQuery.isError || !Number.isInteger(eventId) || eventId <= 0) && (
          <div className="message-panel" role="alert">
            <div>
              <h1>Vorbereitungen konnten nicht geladen werden.</h1>
              <p>Das Event ist nicht verfügbar oder du hast keine Berechtigung, diese Vorbereitungen zu sehen.</p>
              {boardQuery.isError && <button className="text-button" onClick={() => void boardQuery.refetch()} type="button">Erneut versuchen</button>}
            </div>
          </div>
        )}

        {board && !boardQuery.isError && (
          <>
            <header className="event-tasks-heading">
              <p className="eyebrow eyebrow--muted">VORBEREITEN & MITHELFEN</p>
              <h1>Vorbereitungen<span>.</span></h1>
              <p className="event-tasks-heading__event">{board.event.name} · {formatTaskDate(board.event.date)}</p>
              {board.can_manage && <Link className="text-button" to={`/manage/events/${eventId}/tasks`}>Vorbereitungen verwalten →</Link>}
            </header>
            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
            {board.tasks.length === 0 ? (
              <div className="empty-state task-empty-state">
                <p className="eyebrow eyebrow--muted">GEMEINSAM VORBEREITEN</p>
                <h2>Für dieses Event gibt es noch keine Vorbereitungen.</h2>
                <p>Schau später noch einmal vorbei.</p>
              </div>
            ) : (
              <div className="task-list">
                {board.tasks.map((task) => (
                  <TaskCard
                    authenticated={session?.authenticated === true}
                    busy={actionMutation.isPending}
                    canHelp={task.can_join || task.can_leave}
                    key={task.id}
                    onJoin={() => submitTaskAction(task, "join")}
                    onLeave={() => submitTaskAction(task, "leave")}
                    task={task}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
