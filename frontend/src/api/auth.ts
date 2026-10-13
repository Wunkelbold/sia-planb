import type { CurrentSession } from "./events";

export interface CaptchaChallenge {
  image: string;
  hash: string;
}

export interface RegistrationSetup {
  csrf_token: string;
  roles: string[];
  captcha: CaptchaChallenge;
}

export interface RegistrationValues {
  username: string;
  password: string;
  password_confirm: string;
  role: string;
  surname: string;
  lastname: string;
  email: string;
  hs_email: string;
  street: string;
  street_no: string;
  city: string;
  postalcode: string;
  privacy_policy: boolean;
}

export interface AuthResponse {
  success: boolean;
  error?: string;
  message?: string;
  errors?: Record<string, string[]>;
  session?: CurrentSession;
  captcha?: CaptchaChallenge;
  csrf_token?: string;
  roles?: string[];
  verification_notice?: boolean;
}

async function postForm(url: string, fields: URLSearchParams, csrfToken: string): Promise<AuthResponse> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken,
    },
    body: fields,
  });

  try {
    return (await response.json()) as AuthResponse;
  } catch {
    throw new Error(`Die Anfrage ist fehlgeschlagen (HTTP ${response.status}). Bitte lade die Seite neu.`);
  }
}

export async function getRegistrationSetup(): Promise<RegistrationSetup> {
  const response = await fetch("/api/v1/auth/register", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Registrierung konnte nicht geladen werden (HTTP ${response.status}).`);
  return (await response.json()) as RegistrationSetup;
}

export function loginAccount(username: string, password: string, csrfToken: string): Promise<AuthResponse> {
  const fields = new URLSearchParams({ username, password, csrf_token: csrfToken });
  return postForm("/api/v1/auth/login", fields, csrfToken);
}

export async function requestPasswordReset(email: string, csrfToken: string): Promise<AuthResponse> {
  const fields = new URLSearchParams({ email, csrf_token: csrfToken });
  return postForm("/api/v1/auth/password-reset", fields, csrfToken);
}

export async function confirmPasswordReset(
  uid: string,
  token: string,
  password: string,
  passwordConfirm: string,
  csrfToken: string,
): Promise<AuthResponse> {
  const fields = new URLSearchParams({
    uid,
    token,
    password,
    password_confirm: passwordConfirm,
    csrf_token: csrfToken,
  });
  return postForm("/api/v1/auth/password-reset/confirm", fields, csrfToken);
}

export function registerAccount(
  values: RegistrationValues,
  captchaText: string,
  challenge: CaptchaChallenge,
  csrfToken: string,
): Promise<AuthResponse> {
  const fields = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    fields.set(key, typeof value === "boolean" ? (value ? "y" : "") : value);
  }
  fields.set("captcha-text", captchaText);
  fields.set("captcha-hash", challenge.hash);
  fields.set("csrf_token", csrfToken);
  return postForm("/api/v1/auth/register", fields, csrfToken);
}
