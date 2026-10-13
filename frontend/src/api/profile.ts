export interface ProfileInfo {
  username: string;
  role: string;
  roles: string[];
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
  personal_calendar_url: string;
}

export interface ProfileFormValues {
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
}

export interface UserRoleRequest {
  id: number;
  uid: string;
  user_uid: string;
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

export interface MyRoleRequestsResponse {
  requestable_roles: string[];
  pending_request: UserRoleRequest | null;
}

interface ProfileUpdateResponse {
  success: boolean;
  profile: ProfileInfo;
  verification_warning: boolean;
}

interface VerificationRequestResponse {
  success: boolean;
}

export async function getMyProfile(): Promise<ProfileInfo> {
  const response = await fetch("/api/v1/me/profile", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error(`Profile API returned HTTP ${response.status}`);
  }
  return (await response.json()) as ProfileInfo;
}

export async function updateMyProfile(
  values: ProfileFormValues,
  csrfToken: string,
): Promise<ProfileUpdateResponse> {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    body.set(key, value);
  }
  body.set("csrf_token", csrfToken);

  const response = await fetch("/api/v1/me/profile", {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken,
    },
    body,
  });
  const payload = (await response.json()) as Partial<ProfileUpdateResponse> & {
    errors?: Record<string, string[]>;
  };

  if (!response.ok || !payload.success || !payload.profile) {
    const message = Object.values(payload.errors ?? {}).flat()[0];
    throw new Error(message || `Profil konnte nicht gespeichert werden (HTTP ${response.status}).`);
  }

  return payload as ProfileUpdateResponse;
}

export async function requestEmailVerification(csrfToken: string): Promise<VerificationRequestResponse> {
  const response = await fetch("/api/v1/me/verification", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  });
  const payload = (await response.json()) as Partial<VerificationRequestResponse> & { error?: string };
  if (!response.ok || !payload.success) {
    throw new Error(payload.error || `Bestätigungsmail konnte nicht angefordert werden (HTTP ${response.status}).`);
  }
  return payload as VerificationRequestResponse;
}

export async function getMyRoleRequests(): Promise<MyRoleRequestsResponse> {
  const response = await fetch("/api/v1/me/role-requests", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  const payload = await response.json() as MyRoleRequestsResponse & { error?: string };
  if (!response.ok) throw new Error(payload.error || `Rollenanträge konnten nicht geladen werden (HTTP ${response.status}).`);
  return payload;
}

export async function submitMyRoleRequest(requestedRole: string, note: string, csrfToken: string): Promise<UserRoleRequest> {
  const response = await fetch("/api/v1/me/role-requests", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ requested_role: requestedRole, note }),
  });
  const payload = await response.json() as { success?: boolean; request?: UserRoleRequest; error?: string; errors?: Record<string, string> };
  if (!response.ok || !payload.success || !payload.request) {
    throw new Error(payload.error || Object.values(payload.errors ?? {})[0] || `Rollenantrag konnte nicht gesendet werden (HTTP ${response.status}).`);
  }
  return payload.request;
}
