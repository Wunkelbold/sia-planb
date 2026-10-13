import type { AssignmentUser } from "./eventManager";

export interface EventTask {
  id: number;
  event_id: number;
  name: string;
  description: string;
  status: string;
  priority: string;
  visibility: string;
  deadline: string | null;
  timeframe_start: string | null;
  timeframe_end: string | null;
  helper_count: number;
  helpers?: AssignmentUser[];
  assigned_to_me: boolean;
  can_join: boolean;
  can_leave: boolean;
  can_manage: boolean;
}

export interface EventTaskBoard {
  event: {
    id: number;
    name: string;
    date: string | null;
    place: string | null;
  };
  tasks: EventTask[];
  can_manage: boolean;
}

export interface ManagedTaskBoard {
  event: EventTaskBoard["event"];
  tasks: EventTask[];
  can_assign_helpers?: boolean;
}

export interface ManagedTaskOverviewItem {
  id: number;
  event_id: number;
  event_name: string;
  name: string;
  priority: string;
  status: string;
  visibility: string;
  deadline: string | null;
  helper_count: number;
}

export interface ManagedTaskOverviewResponse {
  tasks: ManagedTaskOverviewItem[];
}

export interface TaskFields {
  name: string;
  description: string;
  status: string;
  priority: string;
  visibility: string;
  deadline: string;
  timeframe_start: string;
  timeframe_end: string;
}

async function taskRequest<T>(path: string, method = "GET", csrfToken?: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = (await response.json()) as T & {
    error?: string;
    errors?: Record<string, string>;
    success?: boolean;
  };

  if (!response.ok || result.success === false) {
    throw new Error(result.error || Object.values(result.errors ?? {})[0] || `Vorbereitung konnte nicht geladen werden (HTTP ${response.status}).`);
  }
  return result;
}

export function getEventTasks(eventId: number): Promise<EventTaskBoard> {
  return taskRequest<EventTaskBoard>(`/api/v1/events/${eventId}/tasks`);
}

export function getManagedEventTasks(eventId: number): Promise<ManagedTaskBoard> {
  return taskRequest<ManagedTaskBoard>(`/api/v1/manage/events/${eventId}/tasks`);
}

export function getManagedTasks(): Promise<ManagedTaskOverviewResponse> {
  return taskRequest<ManagedTaskOverviewResponse>("/api/v1/manage/tasks");
}

export async function createEventTask(eventId: number, fields: TaskFields, csrfToken: string): Promise<EventTask> {
  const response = await taskRequest<{ task: EventTask }>(`/api/v1/manage/events/${eventId}/tasks`, "POST", csrfToken, fields);
  return response.task;
}

export async function updateEventTask(
  eventId: number,
  taskId: number,
  fields: TaskFields,
  csrfToken: string,
): Promise<EventTask> {
  const response = await taskRequest<{ task: EventTask }>(
    `/api/v1/manage/events/${eventId}/tasks/${taskId}`,
    "PUT",
    csrfToken,
    fields,
  );
  return response.task;
}

export function deleteEventTask(eventId: number, taskId: number, csrfToken: string): Promise<{ success: boolean }> {
  return taskRequest(`/api/v1/manage/events/${eventId}/tasks/${taskId}`, "DELETE", csrfToken);
}

export function joinEventTask(taskId: number, csrfToken: string): Promise<{ success: boolean }> {
  return taskRequest(`/api/v1/tasks/${taskId}/join`, "POST", csrfToken);
}

export function leaveEventTask(taskId: number, csrfToken: string): Promise<{ success: boolean }> {
  return taskRequest(`/api/v1/tasks/${taskId}/leave`, "POST", csrfToken);
}
