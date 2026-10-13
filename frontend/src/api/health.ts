export interface ApiHealth {
  status: "ok";
}

export async function getApiHealth(): Promise<ApiHealth> {
  const response = await fetch("/api/v1/health", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });

  if (!response.ok) {
    throw new Error(`Flask API returned HTTP ${response.status}`);
  }

  return (await response.json()) as ApiHealth;
}
