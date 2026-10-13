export interface ManagedShift {
  id: number;
  type: string;
  start: string | null;
  end: string | null;
  participants: number;
  assigned_users?: AssignmentUser[];
}

export interface AssignmentUser {
  uid: string;
  username: string;
  surname: string;
  lastname: string;
  role: string;
}

export type EventAssignmentKind = "registration" | "shift" | "task";

export interface ManagedRegistrationOption {
  id: number;
  name: string;
  visibility: string;
  accept: string;
  deny: string;
  start: string | null;
  end: string | null;
  price: number | string | null;
  participants?: AssignmentUser[];
}

export interface ManagedEvent {
  id: number;
  uid: string;
  name: string;
  visibility: string;
  place: string;
  date: string | null;
  end: string | null;
  description: string;
  poster_url: string;
  task_count: number;
  shifts: ManagedShift[];
  registration_options: ManagedRegistrationOption[];
}

export interface ManagedEventFields {
  name: string;
  visibility: string;
  place: string;
  date: string;
  end: string;
  description: string;
  move_shifts?: boolean;
}

export interface ManagedShiftFields {
  type: string;
  start: string;
  end: string;
}

export interface ManagedRegistrationFields {
  name: string;
  visibility: string;
  accept: string;
  deny: string;
  start: string;
  end: string;
  price: string;
}

export interface ManagedEventsResponse {
  events: ManagedEvent[];
}

async function sendJson<T>(path: string, method: string, csrfToken?: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;

  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = (await response.json()) as T & {
    error?: string;
    errors?: Record<string, string>;
    success?: boolean;
  };

  if (!response.ok || payload.success === false) {
    const message = payload.error || Object.values(payload.errors ?? {})[0];
    throw new Error(message || `Eventmanager-Anfrage fehlgeschlagen (HTTP ${response.status}).`);
  }
  return payload;
}

export function getManagedEvents(): Promise<ManagedEventsResponse> {
  return sendJson<ManagedEventsResponse>("/api/v1/manage/events", "GET");
}

export async function createManagedEvent(fields: ManagedEventFields, csrfToken: string): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>("/api/v1/manage/events", "POST", csrfToken, fields);
  return response.event;
}

export async function updateManagedEvent(
  eventId: number,
  fields: ManagedEventFields,
  csrfToken: string,
): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>(`/api/v1/manage/events/${eventId}`, "PUT", csrfToken, fields);
  return response.event;
}

export function deleteManagedEvent(eventId: number, csrfToken: string): Promise<{ success: boolean }> {
  return sendJson(`/api/v1/manage/events/${eventId}`, "DELETE", csrfToken);
}

export async function createManagedShift(
  eventId: number,
  fields: ManagedShiftFields,
  csrfToken: string,
): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>(
    `/api/v1/manage/events/${eventId}/shifts`,
    "POST",
    csrfToken,
    fields,
  );
  return response.event;
}

export async function updateManagedShift(
  eventId: number,
  shiftId: number,
  fields: ManagedShiftFields,
  csrfToken: string,
): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>(
    `/api/v1/manage/events/${eventId}/shifts/${shiftId}`,
    "PUT",
    csrfToken,
    fields,
  );
  return response.event;
}

export function deleteManagedShift(
  eventId: number,
  shiftId: number,
  csrfToken: string,
): Promise<{ event: ManagedEvent }> {
  return sendJson(`/api/v1/manage/events/${eventId}/shifts/${shiftId}`, "DELETE", csrfToken);
}

export async function createManagedRegistration(
  eventId: number,
  fields: ManagedRegistrationFields,
  csrfToken: string,
): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>(
    `/api/v1/manage/events/${eventId}/registrations`,
    "POST",
    csrfToken,
    fields,
  );
  return response.event;
}

export async function updateManagedRegistration(
  eventId: number,
  registrationId: number,
  fields: ManagedRegistrationFields,
  csrfToken: string,
): Promise<ManagedEvent> {
  const response = await sendJson<{ event: ManagedEvent }>(
    `/api/v1/manage/events/${eventId}/registrations/${registrationId}`,
    "PUT",
    csrfToken,
    fields,
  );
  return response.event;
}

export function deleteManagedRegistration(
  eventId: number,
  registrationId: number,
  csrfToken: string,
): Promise<{ event: ManagedEvent }> {
  return sendJson(
    `/api/v1/manage/events/${eventId}/registrations/${registrationId}`,
    "DELETE",
    csrfToken,
  );
}

export function getAssignableEventUsers(
  eventId: number,
  kind: EventAssignmentKind,
  targetId: number,
  query: string,
): Promise<{ users: AssignmentUser[] }> {
  const params = new URLSearchParams({ q: query });
  return sendJson(`/api/v1/manage/events/${eventId}/assignments/${kind}/${targetId}/users?${params}`, "GET");
}

export function changeEventAssignment(
  eventId: number,
  kind: EventAssignmentKind,
  targetId: number,
  userUid: string,
  action: "add" | "remove",
  csrfToken: string,
  reason?: string,
): Promise<{ success: boolean }> {
  return sendJson(
    `/api/v1/manage/events/${eventId}/assignments/${kind}/${targetId}`,
    action === "add" ? "POST" : "DELETE",
    csrfToken,
    { user_uid: userUid, reason },
  );
}
