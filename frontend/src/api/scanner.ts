export interface ScannedTicket {
  id: number;
  userUID: string;
  users: string;
  rm_name: string;
  price: number | string | null;
  paid: boolean;
  payment_status?: "open" | "partially_paid" | "paid" | "cancelled" | "waived";
  remaining_cents?: number | null;
  valid: boolean;
}

export type ScannedUserLookup = { username: string } | { uid: string };

async function readScannerPayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    if (response.status === 401) throw new Error("Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.");
    if (response.status === 403) throw new Error("Dir fehlt die Berechtigung für den Scanner.");
    throw new Error("Der Scanner-Server hat keine gültige JSON-Antwort geliefert. Bitte lade die Seite neu.");
  }
}

export async function getTicketsForScannedUser(lookup: ScannedUserLookup, csrfToken: string): Promise<ScannedTicket[]> {
  const response = await fetch("/api/user/get/scanner", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(lookup),
  });
  const payload = await readScannerPayload(response) as ScannedTicket[] | { error?: string };
  if (!response.ok || !Array.isArray(payload)) {
    throw new Error((!Array.isArray(payload) && payload.error) || "Tickets für diesen Benutzer konnten nicht geladen werden.");
  }
  return payload;
}

export async function updateScannedTicket(
  ticketId: number,
  action: "validate" | "punch" | "paid" | "unpaid",
  csrfToken: string,
): Promise<void> {
  const response = await fetch(`/api/events/event/registration/${action}/${ticketId}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  });
  const payload = await readScannerPayload(response) as {
    success?: boolean;
    error?: Record<string, string[]> | string;
    message?: Record<string, string[]>;
  };
  if (!response.ok || !payload.success) {
    const message = typeof payload.error === "string"
      ? payload.error
      : Object.values(payload.message ?? payload.error ?? {}).flat()[0];
    throw new Error(message || "Ticket-Aktion fehlgeschlagen.");
  }
}
