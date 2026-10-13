import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { getCurrentSession, postEventAction } from "../api/events";
import { getMyCommitments, type MyCommitments } from "../api/commitments";
import { leaveEventTask } from "../api/tasks";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

function commitmentDate(value: string | null) {
  if (!value) return "Zeit folgt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Zeit folgt";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    weekday: "short",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function commitmentClock(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function MyCommitmentsPage() {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const commitmentsQuery = useQuery({
    queryKey: ["my-commitments"],
    queryFn: getMyCommitments,
    enabled: sessionQuery.data?.authenticated === true,
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [notice, setNotice] = useState("");
  const actionMutation = useMutation({
    mutationFn: async ({ kind, id, csrfToken }: { kind: "shift" | "task"; id: number; csrfToken: string }) => {
      if (kind === "shift") await postEventAction(`/api/events/event/leaveshift/${id}`, csrfToken);
      else await leaveEventTask(id, csrfToken);
    },
    onMutate: () => {
      setErrorMessage("");
      setNotice("");
    },
    onSuccess: async (_, action) => {
      setNotice(action.kind === "shift" ? "Du hilfst bei dieser Schicht nicht mehr." : "Du bist aus der Vorbereitung ausgetragen.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["my-commitments"] }),
        queryClient.invalidateQueries({ queryKey: ["upcoming-events"] }),
      ]);
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "Änderung konnte nicht gespeichert werden."),
  });
  const session = sessionQuery.data;
  const data: MyCommitments | undefined = commitmentsQuery.data;
  const totalCommitments = (data?.shifts.length ?? 0) + (data?.tasks.length ?? 0);

  function leave(kind: "shift" | "task", id: number) {
    const token = session?.csrf_token;
    if (!token) {
      setErrorMessage("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu.");
      return;
    }
    actionMutation.mutate({ kind, id, csrfToken: token });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="commitments-page">
        <header className="commitments-heading">
          <p className="eyebrow eyebrow--muted">DEIN EINSATZ</p>
          <h1>Meine Beteiligung<span>.</span></h1>
          <p>Hier siehst du, bei welchen Vorbereitungen und Helferschichten du mit anpackst.</p>
          <Link className="event-card__link" to="/me/registrations">Meine Tickets ansehen <span aria-hidden="true">→</span></Link>
        </header>

        {(sessionQuery.isLoading || (session?.authenticated && commitmentsQuery.isLoading)) && (
          <div className="detail-loading" role="status">Deine Einsätze werden geladen …</div>
        )}
        {sessionQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Deine Sitzung konnte nicht geprüft werden.</p>}
        {session && !session.authenticated && (
          <div className="message-panel" role="status">
            <div><h2>Melde dich an, um deine Einsätze zu sehen.</h2><Link className="participation-button" to="/login">Einloggen</Link></div>
          </div>
        )}
        {session?.authenticated && commitmentsQuery.isError && (
          <div className="message-panel" role="alert">
            <div><h2>Deine Einsätze konnten nicht geladen werden.</h2><button className="text-button" onClick={() => void commitmentsQuery.refetch()} type="button">Erneut versuchen</button></div>
          </div>
        )}

        {session?.authenticated && data && (
          <>
            {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}
            {notice && <p className="action-feedback" role="status">{notice}</p>}
            {totalCommitments === 0 ? (
              <div className="empty-state">
                <p className="eyebrow eyebrow--muted">GEMEINSAM ANPACKEN</p>
                <h2>Du bist aktuell für nichts eingetragen.</h2>
                <p>Schau bei den kommenden Events vorbei und finde eine Vorbereitung oder Schicht, die zu dir passt.</p>
                <Link to="/events">Kommende Events ansehen <span aria-hidden="true">→</span></Link>
              </div>
            ) : (
              <div className="commitments-sections">
                <section aria-labelledby="commitment-shifts-title" className="commitment-section">
                  <div className="participation-section__heading">
                    <p className="eyebrow eyebrow--muted">VOR ORT HELFEN</p>
                    <h2 id="commitment-shifts-title">Meine Helferschichten<span>.</span></h2>
                  </div>
                  {data.shifts.length === 0 ? (
                    <p className="participation-empty">Du hast dich noch für keine Helferschicht eingetragen.</p>
                  ) : (
                    <div className="commitment-grid">
                      {data.shifts.map((shift) => (
                        <article className="commitment-card commitment-card--shift" key={shift.id}>
                          <p className="commitment-card__kind">HELFER-SCHICHT</p>
                          <h3>{shift.type || "Helferschicht"}</h3>
                          <p className="commitment-card__event">{shift.event.name}</p>
                          <p className="commitment-card__time">{commitmentDate(shift.start)}{shift.end ? ` – ${new Intl.DateTimeFormat("de-DE", { timeZone: "Europe/Berlin", hour: "2-digit", minute: "2-digit" }).format(new Date(shift.end))}` : ""}</p>
                          <Link className="event-card__link" to={`/events/${shift.event.id}`}>Event ansehen <span aria-hidden="true">→</span></Link>
                          {shift.can_leave && <button className="text-button" disabled={actionMutation.isPending} onClick={() => leave("shift", shift.shift_id)} type="button">Austragen</button>}
                        </article>
                      ))}
                    </div>
                  )}
                </section>

                <section aria-labelledby="commitment-tasks-title" className="commitment-section">
                  <div className="participation-section__heading">
                    <p className="eyebrow eyebrow--muted">VORBEREITUNGEN ÜBERNEHMEN</p>
                    <h2 id="commitment-tasks-title">Meine Vorbereitungen<span>.</span></h2>
                  </div>
                  {data.tasks.length === 0 ? (
                    <p className="participation-empty">Du hast noch keine Eventvorbereitung übernommen.</p>
                  ) : (
                    <div className="commitment-grid">
                      {data.tasks.map((task) => (
                        <article className="commitment-card commitment-card--task" key={task.id}>
                          <p className="commitment-card__kind">{task.priority || "VORBEREITUNG"}</p>
                          <h3>{task.name}</h3>
                          <p className="commitment-card__event">{task.event.name}</p>
                          <p className="commitment-card__time">
                            {task.timeframe_start
                              ? `Zeit: ${commitmentDate(task.timeframe_start)}${task.timeframe_end ? ` – ${commitmentClock(task.timeframe_end)}` : ""}`
                              : task.deadline ? `Deadline ${commitmentDate(task.deadline)}` : task.status}
                          </p>
                          <Link className="event-card__link" to={`/events/${task.event.id}`}>Event &amp; Vorbereitungen <span aria-hidden="true">→</span></Link>
                          {task.can_leave && <button className="text-button" disabled={actionMutation.isPending} onClick={() => leave("task", task.task_id)} type="button">Austragen</button>}
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}
          </>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
