import type { CaptchaChallenge } from "./auth";

export interface ContactSetup {
  csrf_token: string;
  categories: Array<{ value: string; label: string }>;
  captcha: CaptchaChallenge;
  prefill: {
    surname: string;
    lastname: string;
    email: string;
  };
}

export interface ContactFormValues {
  category: string;
  surname: string;
  lastname: string;
  email: string;
  message: string;
  privacy_policy: boolean;
}

export interface ContactResponse {
  success: boolean;
  message?: string;
  errors?: Record<string, string[]>;
  captcha?: CaptchaChallenge;
  csrf_token?: string;
}

export async function getContactSetup(): Promise<ContactSetup> {
  const response = await fetch("/api/v1/contact", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Kontaktformular konnte nicht geladen werden (HTTP ${response.status}).`);
  return (await response.json()) as ContactSetup;
}

export async function submitContact(
  values: ContactFormValues,
  captchaText: string,
  captcha: CaptchaChallenge,
  csrfToken: string,
): Promise<ContactResponse> {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    body.set(key, typeof value === "boolean" ? (value ? "y" : "") : value);
  }
  body.set("captcha-text", captchaText);
  body.set("captcha-hash", captcha.hash);
  body.set("csrf_token", csrfToken);

  const response = await fetch("/api/v1/contact", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      "X-CSRFToken": csrfToken,
    },
    body,
  });
  try {
    return (await response.json()) as ContactResponse;
  } catch {
    throw new Error(`Kontaktanfrage fehlgeschlagen (HTTP ${response.status}). Bitte versuche es erneut.`);
  }
}
