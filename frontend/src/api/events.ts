export interface UpcomingEvent {
  id: number;
  uid: string;
  name: string;
  place: string | null;
  date: string | null;
  end: string | null;
  description: string | null;
  poster_url: string;
  has_registration: boolean;
  personal_shift_count: number;
  personal_task_count: number;
}

export interface EventRegistrationOption {
  id: number;
  name: string;
  accept: string;
  visibility: string;
  start: string | null;
  end: string | null;
  price: number | string | null;
  is_open: boolean;
  is_registered: boolean;
  can_register: boolean;
  can_unregister: boolean;
}

export interface EventShift {
  id: number;
  type: string | null;
  start: string | null;
  end: string | null;
  participants: number;
  helper_usernames: string[];
  is_joined: boolean;
}

export interface EventPreparation {
  id: number;
  name: string;
  description: string;
  status: string;
  priority: string;
  visibility: string;
  timeframe_start: string | null;
  timeframe_end: string | null;
  helper_count: number;
  helper_usernames: string[];
  assigned_to_me: boolean;
  can_join: boolean;
  can_leave: boolean;
  is_open: boolean;
}

export interface EventDetails {
  event: UpcomingEvent;
  registrations: EventRegistrationOption[];
  shifts: EventShift[];
  preparations: EventPreparation[];
}

export interface CurrentSession {
  authenticated: boolean;
  username?: string;
  needs_email_confirmation?: boolean;
  can_help?: boolean;
  can_admin_panel?: boolean;
  can_manage_events?: boolean;
  can_manage_tasks?: boolean;
  can_create_events?: boolean;
  can_edit_events?: boolean;
  can_delete_events?: boolean;
  can_manage_shifts?: boolean;
  can_manage_registration_options?: boolean;
  can_scan_tickets?: boolean;
  can_manage_users?: boolean;
  can_update_users?: boolean;
  can_delete_users?: boolean;
  can_manage_contacts?: boolean;
  can_delete_contacts?: boolean;
  can_manage_finances?: boolean;
  can_manage_drink_menu?: boolean;
  can_use_tally?: boolean;
  can_validate_tickets?: boolean;
  can_punch_tickets?: boolean;
  can_manage_ticket_payment?: boolean;
  csrf_token?: string;
}

export interface MyTicket {
  id: number;
  registration_name: string | null;
  price: number | string | null;
  paid: boolean;
  payment_status?: "open" | "partially_paid" | "paid" | "cancelled" | "waived";
  remaining_cents?: number | null;
  valid: boolean;
  timestamp: string | null;
  can_cancel: boolean;
  event: {
    id: number;
    name: string;
    date: string | null;
    place: string | null;
  };
}

export interface MyTicketsResponse {
  checkin_qr: string;
  tickets: MyTicket[];
}

interface EventsResponse {
  events: UpcomingEvent[];
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });

  if (!response.ok) {
    throw new Error(`Flask API returned HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getUpcomingEvents(): Promise<UpcomingEvent[]> {
  const payload = (await getJson<Partial<EventsResponse>>("/api/v1/events"));
  if (!Array.isArray(payload.events)) {
    throw new Error("Events API returned an invalid response");
  }

  return payload.events;
}

export function getEventDetails(eventId: number): Promise<EventDetails> {
  return getJson<EventDetails>(`/api/v1/events/${eventId}`);
}

export function getCurrentSession(): Promise<CurrentSession> {
  return getJson<CurrentSession>("/api/v1/session");
}

export function getMyTickets(): Promise<MyTicketsResponse> {
  return getJson<MyTicketsResponse>("/api/v1/me/tickets");
}

export async function postEventAction(path: string, csrfToken: string): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  });

  const payload = (await response.json()) as {
    success?: boolean;
    error?: unknown;
  };

  if (!response.ok || !payload.success) {
    throw new Error(getApiErrorMessage(payload.error) || "Die Aktion konnte nicht ausgeführt werden.");
  }
}

function getApiErrorMessage(error: unknown): string | undefined {
  if (typeof error === "string") return error;
  if (!error || typeof error !== "object") return undefined;

  for (const value of Object.values(error)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }

  return undefined;
}
