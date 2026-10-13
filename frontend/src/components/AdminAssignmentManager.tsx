import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  changeEventAssignment,
  getAssignableEventUsers,
  type AssignmentUser,
  type EventAssignmentKind,
} from "../api/eventManager";

function displayName(user: AssignmentUser) {
  return [user.surname, user.lastname].filter(Boolean).join(" ") || user.username;
}

const assignmentLabels: Record<EventAssignmentKind, { heading: string; search: string; add: string; openSearch: string }> = {
  registration: { heading: "Teilnehmende", search: "Nutzername oder Name suchen", add: "Zur Anmeldung hinzufügen", openSearch: "Teilnehmende hinzufügen" },
  shift: { heading: "Helfer:innen", search: "Nutzername oder Name suchen", add: "Für die Schicht eintragen", openSearch: "Helfer:innen zur Schicht hinzufügen" },
  task: { heading: "Zugeordnete Helfer:innen", search: "Nutzername oder Name suchen", add: "Der Vorbereitung zuordnen", openSearch: "Helfer:innen zur Vorbereitung hinzufügen" },
};

export default function AdminAssignmentManager({
  eventId,
  kind,
  targetId,
  csrfToken,
  assignedUsers,
}: {
  eventId: number;
  kind: EventAssignmentKind;
  targetId: number;
  csrfToken: string;
  assignedUsers: AssignmentUser[];
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [error, setError] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchQuery = useQuery({
    queryKey: ["assignable-event-users", eventId, kind, targetId, search.trim()],
    queryFn: () => getAssignableEventUsers(eventId, kind, targetId, search.trim()),
    enabled: search.trim().length >= 2,
  });
  const assignmentMutation = useMutation({
    mutationFn: ({ user, action, reason }: { user: AssignmentUser; action: "add" | "remove"; reason?: string }) =>
      changeEventAssignment(eventId, kind, targetId, user.uid, action, csrfToken, reason),
    onSuccess: async () => {
      setError("");
      setSearch("");
      setSearchOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["managed-events"] }),
        queryClient.invalidateQueries({ queryKey: ["manage-event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["event-tasks", eventId] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance-event-tickets"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-finance-user"] }),
        queryClient.invalidateQueries({ queryKey: ["assignable-event-users", eventId, kind, targetId] }),
      ]);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Zuordnung konnte nicht geändert werden."),
  });
  const labels = assignmentLabels[kind];

  useEffect(() => {
    if (!searchOpen || !searchInputRef.current) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    searchInputRef.current.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    searchInputRef.current.focus();
  }, [searchOpen]);

  function removeUser(user: AssignmentUser) {
    let reason: string | undefined;
    if (kind === "registration") {
      reason = window.prompt(`Grund für die Abmeldung von ${displayName(user)}:`)?.trim();
      if (!reason) return;
    } else if (!window.confirm(`${displayName(user)} wirklich aus dieser Zuordnung entfernen?`)) {
      return;
    }
    assignmentMutation.mutate({ user, action: "remove", reason });
  }

  return (
    <div className="admin-assignment-manager">
      <div className="admin-assignment-manager__heading">
        <h4>{labels.heading}<span>{assignedUsers.length}</span></h4>
        <button
          aria-label={searchOpen ? "Suche schließen" : labels.openSearch}
          aria-expanded={searchOpen}
          className="admin-assignment-add-button"
          onClick={() => {
            setSearch("");
            setError("");
            setSearchOpen((open) => !open);
          }}
          type="button"
        >
          {searchOpen ? "Schließen" : `+ ${labels.openSearch}`}
        </button>
      </div>
      {assignedUsers.length > 0 ? (
        <ul className="admin-assignment-list">
          {assignedUsers.map((user) => (
            <li key={user.uid}>
              <span><strong>{displayName(user)}</strong><small>@{user.username} · {user.role}</small></span>
              <button
                aria-label={`${displayName(user)} aus der Zuordnung entfernen`}
                className="text-button text-button--danger"
                disabled={assignmentMutation.isPending}
                onClick={() => removeUser(user)}
                type="button"
              >Austragen</button>
            </li>
          ))}
        </ul>
      ) : <p className="participation-empty">Noch niemand eingetragen.</p>}
      {searchOpen && (
        <div className="admin-assignment-search-panel">
          <label className="profile-field admin-assignment-search">
            <span>{labels.search}</span>
            <input autoComplete="off" onChange={(event) => setSearch(event.target.value)} ref={searchInputRef} value={search} />
          </label>
          {search.trim().length === 1 && <small>Mindestens zwei Zeichen eingeben.</small>}
          {searchQuery.isFetching && <p className="participation-empty" role="status">Konten werden gesucht …</p>}
          {searchQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Konten konnten nicht gesucht werden.</p>}
          {searchQuery.data?.users.map((user) => (
            <button
              className="admin-assignment-result"
              disabled={assignmentMutation.isPending}
              key={user.uid}
              onClick={() => assignmentMutation.mutate({ user, action: "add" })}
              type="button"
            >
              <span><strong>{displayName(user)}</strong><small>@{user.username} · {user.role}</small></span>
              <span>{labels.add}</span>
            </button>
          ))}
          {searchQuery.data?.users.length === 0 && <p className="participation-empty">Keine passenden berechtigten Konten gefunden.</p>}
        </div>
      )}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
    </div>
  );
}
