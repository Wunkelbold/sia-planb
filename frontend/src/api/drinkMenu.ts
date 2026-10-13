export interface DrinkMenuItem {
  uid: string;
  name: string;
  group_label: string;
  description: string;
  volume_label: string;
  price_cents: number | null;
  show_price: boolean;
  image_url: string;
  sort_order: number;
  is_active: boolean;
}

export interface DrinkMenuSection {
  uid: string;
  title: string;
  subtitle: string;
  price_cents: number | null;
  show_price: boolean;
  sort_order: number;
  is_active: boolean;
  items: DrinkMenuItem[];
}

export interface PublicDrinkMenu {
  sections: DrinkMenuSection[];
  updated_at: string | null;
  qr_data_url: string;
  menu_url: string;
}

export interface AdminDrinkMenu {
  sections: DrinkMenuSection[];
  menu_url: string;
}

export interface DrinkMenuSectionValues {
  title: string;
  subtitle: string;
  price_cents: number | null;
  show_price: boolean;
  sort_order: number;
  is_active?: boolean;
}

export interface DrinkMenuItemValues {
  section_uid: string;
  name: string;
  group_label: string;
  description: string;
  volume_label: string;
  price_cents: number | null;
  show_price: boolean;
  sort_order: number;
  is_active?: boolean;
}

async function menuRequest<T>(path: string, method = "GET", csrfToken?: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let payload: T & { error?: string; errors?: Record<string, string | string[]>; success?: boolean };
  try {
    payload = JSON.parse(await response.text()) as T & { error?: string; errors?: Record<string, string | string[]>; success?: boolean };
  } catch {
    throw new Error(`Getränkekarten-Anfrage fehlgeschlagen (HTTP ${response.status}). Bitte lade die Seite neu.`);
  }
  if (!response.ok || payload.success === false) {
    const detail = Object.values(payload.errors ?? {}).flat()[0];
    throw new Error(payload.error || detail || `Getränkekarten-Anfrage fehlgeschlagen (HTTP ${response.status}).`);
  }
  return payload;
}

export function getPublicDrinkMenu() {
  return menuRequest<PublicDrinkMenu>("/api/v1/drink-menu");
}

export function getAdminDrinkMenu() {
  return menuRequest<AdminDrinkMenu>("/api/v1/manage/drink-menu");
}

export function createDrinkMenuSection(values: DrinkMenuSectionValues, csrfToken: string) {
  return menuRequest<{ success: boolean; section: DrinkMenuSection }>(
    "/api/v1/manage/drink-menu/sections", "POST", csrfToken, values,
  );
}

export function updateDrinkMenuSection(uid: string, values: DrinkMenuSectionValues, csrfToken: string) {
  return menuRequest<{ success: boolean; section: DrinkMenuSection }>(
    `/api/v1/manage/drink-menu/sections/${uid}`, "PUT", csrfToken, values,
  );
}

export function deactivateDrinkMenuSection(uid: string, csrfToken: string) {
  return menuRequest<{ success: boolean }>(`/api/v1/manage/drink-menu/sections/${uid}`, "DELETE", csrfToken);
}

export function createDrinkMenuItem(values: DrinkMenuItemValues, csrfToken: string) {
  return menuRequest<{ success: boolean; item: DrinkMenuItem }>(
    "/api/v1/manage/drink-menu/items", "POST", csrfToken, values,
  );
}

export function updateDrinkMenuItem(uid: string, values: DrinkMenuItemValues, csrfToken: string) {
  return menuRequest<{ success: boolean; item: DrinkMenuItem }>(
    `/api/v1/manage/drink-menu/items/${uid}`, "PUT", csrfToken, values,
  );
}

export function deactivateDrinkMenuItem(uid: string, csrfToken: string) {
  return menuRequest<{ success: boolean }>(`/api/v1/manage/drink-menu/items/${uid}`, "DELETE", csrfToken);
}

export async function uploadDrinkMenuItemImage(uid: string, file: File, csrfToken: string) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`/api/v1/manage/drink-menu/items/${uid}/image`, {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
    body: formData,
  });
  let payload: { success?: boolean; item?: DrinkMenuItem; error?: string; errors?: Record<string, string | string[]> };
  try {
    payload = JSON.parse(await response.text());
  } catch {
    throw new Error(`Bild-Upload fehlgeschlagen (HTTP ${response.status}).`);
  }
  if (!response.ok || payload.success === false) {
    const detail = Object.values(payload.errors ?? {}).flat()[0];
    throw new Error(payload.error || detail || `Bild-Upload fehlgeschlagen (HTTP ${response.status}).`);
  }
  return payload as { success: boolean; item: DrinkMenuItem };
}

export function removeDrinkMenuItemImage(uid: string, csrfToken: string) {
  return menuRequest<{ success: boolean; item: DrinkMenuItem }>(
    `/api/v1/manage/drink-menu/items/${uid}/image`, "DELETE", csrfToken,
  );
}
