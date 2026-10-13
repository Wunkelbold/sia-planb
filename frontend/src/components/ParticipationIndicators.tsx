import { Link } from "react-router";

import type { UpcomingEvent } from "../api/events";

export function ParticipationIndicators({ event }: { event: UpcomingEvent }) {
  if (!event.has_registration && event.personal_shift_count === 0 && event.personal_task_count === 0) {
    return null;
  }

  return (
    <div aria-label={`Deine Beteiligung am Event ${event.name}`} className="event-participation-indicators">
      {event.has_registration && (
        <Link className="participation-pill participation-pill--registered" to={`/events/${event.id}`}>
          Angemeldet
        </Link>
      )}
      {event.personal_shift_count > 0 && (
        <Link className="participation-pill participation-pill--shift" to={`/events/${event.id}`}>
          Hilfst mit · {event.personal_shift_count}
        </Link>
      )}
      {event.personal_task_count > 0 && (
        <Link className="participation-pill participation-pill--task" to={`/events/${event.id}`}>
          Vorbereitung übernommen · {event.personal_task_count}
        </Link>
      )}
    </div>
  );
}
