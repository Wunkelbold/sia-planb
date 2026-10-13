export interface AdminUser {
  id: number;
  uid: string;
  username: string;
  role: string;
  surname: string;
  lastname: string;
  email: string;
  email_confirmed: boolean;
  hs_email: string;
  hs_email_confirmed: boolean;
  street: string;
  street_no: string;
  city: string;
  postalcode: string;
  register_date: string | null;
  last_login: string | null;
  last_updated: string | null;
}

export interface AdminUserForm {
  username: string;
  role: string;
  surname: string;
  lastname: string;
  email: string;
  hs_email: string;
  street: string;
  street_no: string;
  city: string;
  postalcode: string;
  password: string;
  password_confirm: string;
  verify_mail: boolean;
}

export interface AdminContact {
  uid: string;
  category: string;
  surname: string;
  lastname: string;
  email: string;
  message: string;
  creation: string | null;
  handled_at: string | null;
  handled_by_username: string | null;
  is_handled: boolean;
}

export interface AdminRoleRequest {
  id: number;
  uid: string;
  user_uid: string | null;
  username: string;
  surname: string;
  lastname: string;
  current_role: string;
  requested_role: string;
  request_note: string;
  status: "pending" | "approved" | "rejected" | "withdrawn";
  submitted_at: string | null;
  reviewed_at: string | null;
  review_note: string;
}

interface AdminMutationResponse<T> {
  success: boolean;
  user?: T;
  verification_warning?: boolean;
  error?: string;
  errors?: Record<string, string[]>;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Admin-Anfrage fehlgeschlagen (HTTP ${response.status}).`);
  return payload as T;
}

export function getAdminUsers(): Promise<{ users: AdminUser[]; roles: string[] }> {
  return getJson("/api/v1/manage/users");
}

export function getAdminContacts(): Promise<{ contacts: AdminContact[] }> {
  return getJson("/api/v1/manage/contacts");
}

export function getAdminRoleRequests(): Promise<{ requests: AdminRoleRequest[] }> {
  return getJson("/api/v1/manage/role-requests");
}

export async function reviewAdminRoleRequest(
  id: number,
  decision: "approve" | "reject",
  note: string,
  csrfToken: string,
): Promise<void> {
  const response = await fetch(`/api/v1/manage/role-requests/${id}/review`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ decision, note }),
  });
  const payload = await response.json() as { success?: boolean; error?: string; errors?: Record<string, string> };
  if (!response.ok || !payload.success) {
    throw new Error(payload.error || Object.values(payload.errors ?? {})[0] || `Rollenantrag konnte nicht bearbeitet werden (HTTP ${response.status}).`);
  }
}

export async function updateAdminUser(
  uid: string,
  values: AdminUserForm,
  csrfToken: string,
): Promise<AdminMutationResponse<AdminUser>> {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    body.set(key, typeof value === "boolean" ? (value ? "y" : "") : value);
  }
  body.set("csrf_token", csrfToken);
  const response = await fetch(`/api/v1/manage/users/${encodeURIComponent(uid)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken,
    },
    body,
  });
  const payload = (await response.json()) as AdminMutationResponse<AdminUser>;
  if (!response.ok || !payload.success) {
    const message = Object.values(payload.errors ?? {}).flat()[0];
    throw new Error(message || payload.error || `Nutzer konnte nicht gespeichert werden (HTTP ${response.status}).`);
  }
  return payload;
}

export async function deleteAdminUser(uid: string, csrfToken: string): Promise<void> {
  await sendDelete(`/api/v1/manage/users/${encodeURIComponent(uid)}`, csrfToken);
}

export async function deleteAdminContact(uid: string, csrfToken: string): Promise<void> {
  await sendDelete(`/api/v1/manage/contacts/${encodeURIComponent(uid)}`, csrfToken);
}

export async function setAdminContactHandled(uid: string, handled: boolean, csrfToken: string): Promise<void> {
  const response = await fetch(`/api/v1/manage/contacts/${encodeURIComponent(uid)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ handled }),
  });
  const payload = await response.json() as { success?: boolean; error?: string };
  if (!response.ok || !payload.success) {
    throw new Error(payload.error || `Kontaktanfrage konnte nicht aktualisiert werden (HTTP ${response.status}).`);
  }
}

async function sendDelete(path: string, csrfToken: string): Promise<void> {
  const response = await fetch(path, {
    method: "DELETE",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  });
  const payload = (await response.json()) as { success?: boolean; error?: string };
  if (!response.ok || !payload.success) {
    throw new Error(payload.error || `Löschen fehlgeschlagen (HTTP ${response.status}).`);
  }
}
