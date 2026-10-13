export interface ShiftCommitment {
  id: number;
  shift_id: number;
  type: string | null;
  start: string | null;
  end: string | null;
  can_leave: boolean;
  event: {
    id: number;
    name: string;
    date: string | null;
    place: string | null;
  };
}

export interface TaskCommitment {
  id: number;
  task_id: number;
  name: string;
  status: string;
  priority: string;
  deadline: string | null;
  timeframe_start: string | null;
  timeframe_end: string | null;
  can_leave: boolean;
  event: {
    id: number;
    name: string;
    date: string | null;
    place: string | null;
  };
}

export interface MyCommitments {
  shifts: ShiftCommitment[];
  tasks: TaskCommitment[];
}

export async function getMyCommitments(): Promise<MyCommitments> {
  const response = await fetch("/api/v1/me/commitments", {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Einsätze konnten nicht geladen werden (HTTP ${response.status}).`);
  return (await response.json()) as MyCommitments;
}
