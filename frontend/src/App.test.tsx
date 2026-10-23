import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import App from "./App";
import type { EventDetails, MyTicketsResponse, UpcomingEvent } from "./api/events";
import type { ManagedEvent } from "./api/eventManager";
import type { ProfileInfo } from "./api/profile";
import type { EventTaskBoard, ManagedTaskOverviewItem } from "./api/tasks";
import type { AdminContact, AdminUser } from "./api/admin";
import type { MyCommitments } from "./api/commitments";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  if (originalClipboardDescriptor) {
    Object.defineProperty(navigator, "clipboard", originalClipboardDescriptor);
  } else {
    Reflect.deleteProperty(navigator, "clipboard");
  }
});

const originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, "clipboard");

function renderApp(initialEntry = "/") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockEvents(events: UpcomingEvent[]) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    if (String(input) === "/api/v1/session") {
      return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-calendar" }));
    }
    return Promise.resolve(jsonResponse({ events }));
  }));
}

function stubClipboard() {
  const writeText = vi.fn(async (_text: string) => {});
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  return writeText;
}

function jsonResponse(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

const summerParty: UpcomingEvent = {
  id: 12,
  uid: "event-uid",
  name: "SIA Sommerfest",
  place: "Plan B, Albstadt",
  date: "2027-06-12T18:30:00+02:00",
  end: "2027-06-12T23:00:00+02:00",
  description: "Ein Abend mit Musik und guten Leuten.",
  poster_url: "/static/images/eventposter/event-uid",
  has_registration: false,
  personal_shift_count: 0,
  personal_task_count: 0,
};

function eventDetails(registered = false, joinedShift = false): EventDetails {
  return {
    event: summerParty,
    registrations: [
      {
        id: 19,
        name: "Abendkasse",
        accept: "geöffnet",
        visibility: "public",
        start: null,
        end: null,
        price: 0,
        is_open: true,
        is_registered: registered,
        can_register: !registered,
        can_unregister: registered,
      },
    ],
    shifts: [
      {
        id: 31,
        type: "Aufbau",
        start: "2027-06-12T16:00:00+02:00",
        end: "2027-06-12T18:00:00+02:00",
        participants: joinedShift ? 1 : 0,
        helper_usernames: joinedShift ? ["silas"] : [],
        is_joined: joinedShift,
      },
    ],
    preparations: [
      {
        id: 52,
        name: "Eingang vorbereiten",
        description: "Einlassbereich herrichten.",
        status: "TakeOverTask",
        priority: "mittel",
        visibility: "public",
        timeframe_start: "2027-06-12T14:00:00+02:00",
        timeframe_end: "2027-06-12T15:00:00+02:00",
        helper_count: 1,
        helper_usernames: ["mithelfer"],
        assigned_to_me: false,
        can_join: false,
        can_leave: false,
        is_open: true,
      },
    ],
  };
}

function demoProfile(surname = "Demo"): ProfileInfo {
  return {
    username: "frontendtest",
    role: "Mitglied",
    roles: ["Mitglied", "Gast"],
    surname,
    lastname: "Nutzer",
    email: "frontendtest@example.invalid",
    email_confirmed: true,
    hs_email: "",
    hs_email_confirmed: false,
    street: "",
    street_no: "",
    city: "",
    postalcode: "",
    personal_calendar_url: "/calendar/demo-calendar.ics",
  };
}

function demoTaskBoard(assigned = false): EventTaskBoard {
  return {
    event: { id: 12, name: "SIA Sommerfest", date: summerParty.date, place: "Plan B, Albstadt" },
    can_manage: false,
    tasks: [
      {
        id: 58,
        event_id: 12,
        name: "Aufbau unterstützen",
        description: "Beim Aufbau der Location helfen.",
        status: assigned ? "InProgress" : "TakeOverTask",
        priority: "mittel",
        visibility: "public",
        deadline: "2027-06-12T16:00:00+02:00",
        timeframe_start: "2027-06-12T15:00:00+02:00",
        timeframe_end: "2027-06-12T18:00:00+02:00",
        helper_count: assigned ? 1 : 0,
        assigned_to_me: assigned,
        can_join: !assigned,
        can_leave: assigned,
        can_manage: false,
      },
    ],
  };
}

describe("events page", () => {
  it("copies the public calendar URL from the header without navigating", async () => {
    const writeText = stubClipboard();
    mockEvents([summerParty]);

    renderApp("/events");

    expect(await screen.findByRole("heading", { name: "SIA Sommerfest" })).toBeInTheDocument();
    expect(screen.getByText("Plan B, Albstadt")).toBeInTheDocument();
    expect(screen.getByText(/Samstag, 12\. Juni 2027/)).toBeInTheDocument();
    const calendarButton = await screen.findByRole("button", { name: /Kalender abonnieren/ });
    await waitFor(() => expect(calendarButton).toBeEnabled());
    fireEvent.click(calendarButton);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(new URL("/events.ics", window.location.origin).toString()));
    expect(screen.queryByRole("link", { name: /Kalender abonnieren/ })).not.toBeInTheDocument();
    const detailsLink = screen.getByRole("link", { name: /Eventdetails/ });
    expect(detailsLink).toHaveAttribute(
      "href",
      "/events/12",
    );
    expect(detailsLink).toHaveClass("event-card__link--prominent");
  });

  it("filters the event list by title or venue", async () => {
    mockEvents([summerParty]);

    renderApp("/events");

    await screen.findByRole("heading", { name: "SIA Sommerfest" });
    fireEvent.change(screen.getByRole("searchbox", { name: "Events suchen" }), {
      target: { value: "Albstadt" },
    });
    expect(screen.getByRole("heading", { name: "SIA Sommerfest" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Events suchen" }), {
      target: { value: "Jazz" },
    });
    expect(screen.getByText(/Keine Events für „Jazz“ gefunden/)).toBeInTheDocument();
  });

  it("renders rich event descriptions as safe links in cards and details", async () => {
    const describedEvent: UpcomingEvent = {
      ...summerParty,
      description: '<br><a href="https://www.instagram.com/junokilla/" target="_blank" rel="noopener noreferrer">JUNOKILL</a> & <a href="https://www.instagram.com/ntrinsic_band">NTRINSIC</a>',
    };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false }));
      if (url === "/api/v1/events/12") {
        return Promise.resolve(jsonResponse({ ...eventDetails(), event: describedEvent }));
      }
      return Promise.resolve(jsonResponse({ events: [describedEvent] }));
    }));

    const card = renderApp("/events");
    const junokill = await screen.findByRole("link", { name: "JUNOKILL" });
    expect(junokill).toHaveAttribute("href", "https://www.instagram.com/junokilla/");
    expect(junokill).toHaveAttribute("target", "_blank");
    expect(junokill).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "NTRINSIC" })).toHaveAttribute(
      "href",
      "https://www.instagram.com/ntrinsic_band",
    );
    card.unmount();

    renderApp("/events/12");
    expect(await screen.findByRole("link", { name: "JUNOKILL" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });

  it("drops unsafe markup from event descriptions", async () => {
    mockEvents([
      {
        ...summerParty,
        description: '<a href="javascript:alert(1)">Unsafe link</a><script>alert(2)</script><img src="x" onerror="alert(3)">',
      },
    ]);

    renderApp("/events");

    await screen.findByRole("heading", { name: "SIA Sommerfest" });
    expect(screen.queryByRole("link", { name: "Unsafe link" })).not.toBeInTheDocument();
    expect(screen.getByText("Unsafe link")).toBeInTheDocument();
    expect(screen.queryByText(/alert\(2\)/)).not.toBeInTheDocument();
    expect(document.querySelector('img[src="x"]')).not.toBeInTheDocument();
    expect(screen.queryByText("Weitere Informationen folgen in Kürze.")).not.toBeInTheDocument();
  });

  it("shows a helpful empty state when there are no upcoming events", async () => {
    const writeText = stubClipboard();
    mockEvents([]);

    renderApp("/events");

    const emptyStateHeading = await screen.findByText("Gerade sind keine Events geplant.");
    const calendarButton = within(emptyStateHeading.parentElement as HTMLElement).getByRole("button", { name: /^Kalender abonnieren/ });
    await waitFor(() => expect(calendarButton).toBeEnabled());
    fireEvent.click(calendarButton);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(new URL("/events.ics", window.location.origin).toString()));
  });

  it("offers public and personal calendar URLs to signed-in users", async () => {
    const writeText = stubClipboard();
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-calendar" }));
      }
      if (url === "/api/v1/events") return Promise.resolve(jsonResponse({ events: [summerParty] }));
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(demoProfile()));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/events");

    const calendarButton = await screen.findByRole("button", { name: /Kalender abonnieren/ });
    await waitFor(() => expect(calendarButton).toBeEnabled());
    fireEvent.click(calendarButton);
    const dialog = await screen.findByRole("dialog", { name: "Welchen Kalender möchtest du hinzufügen?" });
    expect(within(dialog).getByText("Enthält die öffentlich sichtbaren Events.")).toBeInTheDocument();
    expect(within(dialog).getByText(/nicht öffentliche Events sowie deine Schichten und Aufgaben/)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /Öffentlicher Kalender/ }));
    await waitFor(() => expect(writeText).toHaveBeenNthCalledWith(
      1,
      new URL("/events.ics", window.location.origin).toString(),
    ));

    fireEvent.click(calendarButton);
    const personalDialog = await screen.findByRole("dialog", { name: "Welchen Kalender möchtest du hinzufügen?" });
    const personalCalendarButton = within(personalDialog).getByRole("button", { name: /Persönlicher Kalender/ });
    await waitFor(() => expect(personalCalendarButton).toBeEnabled());
    fireEvent.click(personalCalendarButton);
    await waitFor(() => expect(writeText).toHaveBeenNthCalledWith(
      2,
      new URL("/calendar/demo-calendar.ics", window.location.origin).toString(),
    ));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error and retry action when the events API is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })),
    );

    renderApp("/events");

    expect(
      await screen.findByText("Events konnten gerade nicht geladen werden."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erneut versuchen/ })).toBeInTheDocument();
  });

  it("shows public registration details and directs guests to the existing login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/v1/events/12") return Promise.resolve(jsonResponse(eventDetails()));
        if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false }));
        return Promise.resolve(new Response("Not found", { status: 404 }));
      }),
    );

    renderApp("/events/12");

    expect(await screen.findByRole("heading", { name: "SIA Sommerfest" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Anmeldung." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Helferschichten." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Vorbereitungen." })).toBeInTheDocument();
    expect(screen.getByText("Eingang vorbereiten")).toBeInTheDocument();
    expect(screen.getByText(/14:00 – 15:00/)).toBeInTheDocument();
    for (const title of ["Anmeldung.", "Helferschichten.", "Vorbereitungen."]) {
      expect(screen.getByRole("heading", { name: title }).closest("section")).toHaveClass("event-participation-section");
    }
    expect(screen.getByText("Mit: @mithelfer")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Vorbereitungen ansehen und mithelfen" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Anmelden" }).map((link) => link.getAttribute("href"))).toContain("/login");
  });

  it("lets a signed-in visitor join a preparation directly from event details", async () => {
    let assigned = false;
    const details = () => {
      const result = eventDetails();
      result.preparations[0] = {
        ...result.preparations[0],
        assigned_to_me: assigned,
        can_join: !assigned,
        can_leave: assigned,
        helper_count: assigned ? 2 : 1,
        helper_usernames: assigned ? ["mithelfer", "silas"] : ["mithelfer"],
      };
      return result;
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/events/12") return Promise.resolve(jsonResponse(details()));
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "silas",
        csrf_token: "csrf-event-preparation",
      }));
      if (url === "/api/v1/tasks/52/join" && init?.method === "POST") {
        assigned = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/events/12");

    fireEvent.click(await screen.findByRole("button", { name: "Mithelfen" }));
    expect(await screen.findByRole("button", { name: "Austragen" })).toBeInTheDocument();
    expect(await screen.findByText("Mit: @mithelfer, @silas")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/tasks/52/join",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-event-preparation" }),
      }),
    );
  });

  it("registers the signed-in user and refreshes their registration status", async () => {
    let registered = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/events/12") {
        return Promise.resolve(jsonResponse(eventDetails(registered)));
      }
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "silas",
          can_help: false,
          csrf_token: "csrf-test-token",
        }));
      }
      if (url === "/api/events/event/12/register/19" && init?.method === "POST") {
        registered = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/events/12");

    fireEvent.click(await screen.findByRole("button", { name: "Anmelden" }));

    expect(await screen.findByRole("button", { name: "Abmelden" })).toBeInTheDocument();
    expect(await screen.findByText("Du bist angemeldet.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/events/event/12/register/19",
      expect.objectContaining({
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": "csrf-test-token",
        },
      }),
    );
  });

  it("lets an authorized helper join a shift", async () => {
    let joined = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/events/12") {
        return Promise.resolve(jsonResponse(eventDetails(false, joined)));
      }
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "silas",
          can_help: true,
          csrf_token: "csrf-test-token",
        }));
      }
      if (url === "/api/events/event/joinshift/31" && init?.method === "POST") {
        joined = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/events/12");

    fireEvent.click(await screen.findByRole("button", { name: "Helfen" }));

    expect(await screen.findByRole("button", { name: "Austragen" })).toBeInTheDocument();
    expect(await screen.findByText(/@silas/)).toBeInTheDocument();
    expect(await screen.findByText("Danke, du hilfst bei dieser Schicht!")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/events/event/joinshift/31",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("asks guests to sign in before loading their tickets", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: false }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/registrations");

    expect(await screen.findByRole("heading", { name: "Melde dich an, um deine Tickets zu sehen." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Einloggen" })).toHaveAttribute("href", "/login");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/me/tickets", expect.anything());
  });

  it("shows the signed-in user's tickets and check-in QR code", async () => {
    const myTickets: MyTicketsResponse = {
      checkin_qr: "data:image/png;base64,ZmFrZQ==",
      tickets: [
        {
          id: 44,
          registration_name: "Abendkasse",
          price: "5.00",
          paid: true,
          valid: true,
          timestamp: "2027-06-01T12:00:00+02:00",
          can_cancel: true,
          event: {
            id: 12,
            name: "SIA Sommerfest",
            date: summerParty.date,
            place: "Plan B, Albstadt",
          },
        },
        {
          id: 45,
          registration_name: "Abendkasse Zusatzkarte",
          price: "8.50",
          paid: false,
          payment_status: "partially_paid",
          remaining_cents: 350,
          valid: false,
          timestamp: "2027-06-01T12:05:00+02:00",
          can_cancel: false,
          event: {
            id: 12,
            name: "SIA Zusatzticket",
            date: summerParty.date,
            place: "Plan B, Albstadt",
          },
        },
      ],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "silas",
          can_help: true,
          csrf_token: "csrf-test-token",
        }));
      }
      if (url === "/api/v1/me/tickets") return Promise.resolve(jsonResponse(myTickets));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/registrations");

    expect(await screen.findByRole("heading", { name: "SIA Sommerfest" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Dein persönlicher Check-in-QR-Code" })).toHaveAttribute(
      "src",
      myTickets.checkin_qr,
    );
    expect(screen.getByText("Bezahlt")).toBeInTheDocument();
    expect(screen.getByText(/Teilweise bezahlt.*3,50.*offen/)).toBeInTheDocument();
    expect(screen.getByText("Gültig")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Anmeldung verwalten/ })).toHaveAttribute(
      "href",
      "/events/12",
    );
    expect(screen.getByRole("link", { name: "Tickets" })).toHaveAttribute(
      "href",
      "/me/registrations",
    );
  });

  it("asks guests to sign in before showing profile data", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: false }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    expect(await screen.findByRole("heading", { name: "Melde dich an, um dein Profil zu verwalten." })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/me/profile", expect.anything());
  });

  it("renders the privacy notice and imprint as React routes", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ authenticated: false }))));

    const privacyView = renderApp("/datenschutz");
    expect(screen.getByRole("heading", { name: "Datenschutzerklärung." })).toBeInTheDocument();
    expect(screen.getByText(/Wer ist verantwortlich für die Datenerfassung/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Impressum" })).toHaveAttribute("href", "/impressum");

    privacyView.unmount();
    renderApp("/impressum");
    expect(screen.getByRole("heading", { name: "Impressum." })).toBeInTheDocument();
    expect(screen.getByText(/Vereinsregister: 400419/)).toBeInTheDocument();
  });

  it("loads account details and the calendar chooser", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-test-token" }));
      }
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(demoProfile()));
      if (url === "/api/v1/me/role-requests") return Promise.resolve(jsonResponse({ requestable_roles: ["Mitglied"], pending_request: null }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    expect(await screen.findByDisplayValue("frontendtest")).toBeInTheDocument();
    expect(screen.getByLabelText("Vorname")).toHaveValue("Demo");
    expect(screen.getByRole("heading", { name: "Dein persönlicher Kalender" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Kalender abonnieren/ })).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Profil" })).toHaveAttribute("href", "/me/profile");
  });

  it("updates profile data using the session CSRF token", async () => {
    let currentProfile = demoProfile();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-test-token" }));
      }
      if (url === "/api/v1/me/profile" && init?.method === "PUT") {
        const form = new URLSearchParams(String(init.body));
        currentProfile = demoProfile(form.get("surname") || "");
        return Promise.resolve(jsonResponse({ success: true, profile: currentProfile, verification_warning: false }));
      }
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(currentProfile));
      if (url === "/api/v1/me/role-requests") return Promise.resolve(jsonResponse({ requestable_roles: ["Mitglied"], pending_request: null }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    fireEvent.change(await screen.findByLabelText("Vorname"), { target: { value: "Alex" } });
    fireEvent.click(screen.getByRole("button", { name: "Änderungen speichern" }));

    expect(await screen.findByText("Deine Änderungen wurden gespeichert.")).toBeInTheDocument();
    expect(screen.getByLabelText("Vorname")).toHaveValue("Alex");
    const updateCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === "/api/v1/me/profile" && init?.method === "PUT",
    );
    expect(updateCall?.[1]).toEqual(expect.objectContaining({
      method: "PUT",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-test-token" }),
    }));
    expect(new URLSearchParams(String(updateCall?.[1]?.body)).get("surname")).toBe("Alex");
  });

  it("submits a reviewed Member role application without changing the current role", async () => {
    const profile = { ...demoProfile(), role: "Sia-Alumni", roles: ["Gast", "Student", "Sia-Alumni"] };
    let pendingRequest: Record<string, unknown> | null = null;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-role-request" }));
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(profile));
      if (url === "/api/v1/me/role-requests" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        pendingRequest = {
          id: 21,
          uid: "role-request-uid",
          user_uid: "frontendtest-uid",
          username: "frontendtest",
          surname: "Demo",
          lastname: "Nutzer",
          current_role: "Sia-Alumni",
          requested_role: body.requested_role,
          request_note: body.note,
          status: "pending",
          submitted_at: "2027-01-01T12:00:00+01:00",
          reviewed_at: null,
          review_note: "",
        };
        return Promise.resolve(jsonResponse({ success: true, request: pendingRequest }, 201));
      }
      if (url === "/api/v1/me/role-requests") return Promise.resolve(jsonResponse({
        requestable_roles: ["Mitglied"],
        pending_request: pendingRequest,
      }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    fireEvent.change(await screen.findByLabelText("Gewünschte Rolle"), { target: { value: "Mitglied" } });
    fireEvent.change(screen.getByLabelText("Begründung"), { target: { value: "Wurde durch die Verwaltung als Mitglied bestätigt." } });
    fireEvent.click(screen.getByRole("button", { name: "Rollenänderung beantragen" }));

    expect(await screen.findByText(/Dein Antrag von Sia-Alumni zu Mitglied wird geprüft/)).toBeInTheDocument();
    expect(screen.getByLabelText("Rolle")).toHaveValue("Sia-Alumni");
    const requestCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/me/role-requests" && init?.method === "POST");
    expect(JSON.parse(String(requestCall?.[1]?.body))).toEqual({ requested_role: "Mitglied", note: "Wurde durch die Verwaltung als Mitglied bestätigt." });
    expect(requestCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-role-request" }));
  });

  it("lets a Moderator downgrade directly and only offers Member as a role application", async () => {
    let currentProfile: ProfileInfo = {
      ...demoProfile(),
      role: "Moderator",
      roles: ["Gast", "Student", "Sia-Alumni", "Moderator"],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-moderator" }));
      if (url === "/api/v1/me/profile" && init?.method === "PUT") {
        const form = new URLSearchParams(String(init.body));
        const role = form.get("role") || currentProfile.role;
        currentProfile = { ...currentProfile, role, roles: role === "Moderator" ? ["Gast", "Student", "Sia-Alumni", "Moderator"] : ["Gast", "Student", "Sia-Alumni"] };
        return Promise.resolve(jsonResponse({ success: true, profile: currentProfile, verification_warning: false }));
      }
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(currentProfile));
      if (url === "/api/v1/me/role-requests") return Promise.resolve(jsonResponse({ requestable_roles: ["Mitglied"], pending_request: null }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    expect(await screen.findByDisplayValue("frontendtest")).toBeInTheDocument();
    expect(screen.getByLabelText("Rolle")).toHaveValue("Moderator");
    expect(Array.from((screen.getByLabelText("Gewünschte Rolle") as HTMLSelectElement).options).map((option) => option.value)).toEqual(["Mitglied"]);
    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "Gast" } });
    fireEvent.click(screen.getByRole("button", { name: "Änderungen speichern" }));

    expect(await screen.findByText("Deine Änderungen wurden gespeichert.")).toBeInTheDocument();
    expect(screen.getByLabelText("Rolle")).toHaveValue("Gast");
    const updateCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/me/profile" && init?.method === "PUT");
    expect(new URLSearchParams(String(updateCall?.[1]?.body)).get("role")).toBe("Gast");
  });

  it("requests a verification email for unconfirmed profile addresses", async () => {
    const profile = { ...demoProfile(), email_confirmed: false };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "frontendtest", csrf_token: "csrf-verify" }));
      }
      if (url === "/api/v1/me/profile") return Promise.resolve(jsonResponse(profile));
      if (url === "/api/v1/me/verification" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ success: true }, 202));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/profile");

    fireEvent.click(await screen.findByRole("button", { name: "Bestätigungsmail erneut anfordern" }));

    expect(await screen.findByText(/Bestätigungsmail angefordert/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/me/verification", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-verify" }),
    }));
  });

  it("shows verification link results on the React profile page", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-verify" }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/me/profile?verification=verified");

    expect(await screen.findByText("Deine E-Mail-Adresse wurde bestätigt.")).toHaveAttribute("role", "status");
  });

  it("shows a useful message when login credentials are rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/v1/session") {
          return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-login" }));
        }
        if (url === "/api/v1/auth/login") {
          return Promise.resolve(jsonResponse({ success: false, error: "Benutzername oder Passwort ist falsch." }, 401));
        }
        return Promise.resolve(new Response("Not found", { status: 404 }));
      }),
    );

    renderApp("/login");

    expect(await screen.findByRole("link", { name: "Passwort vergessen?" })).toHaveAttribute("href", "/forgot-password");
    fireEvent.change(await screen.findByLabelText("Benutzername"), { target: { value: "nobody" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Einloggen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Benutzername oder Passwort ist falsch.");
  });

  it("requests password recovery with the session CSRF token and generic feedback", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-reset" }));
      if (url === "/api/v1/auth/password-reset" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({
          success: true,
          message: "Wenn ein Konto mit dieser bestätigten E-Mail-Adresse existiert, erhältst du einen Link zum Zurücksetzen.",
        }, 202));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/forgot-password");

    fireEvent.change(await screen.findByLabelText("E-Mail-Adresse"), { target: { value: "member@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Link anfordern" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Wenn ein Konto mit dieser bestätigten E-Mail-Adresse existiert");
    const requestCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/v1/auth/password-reset");
    expect(requestCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-reset" }),
    }));
    expect(new URLSearchParams(String(requestCall?.[1]?.body)).get("email")).toBe("member@example.com");
  });

  it("sets a new password using the signed reset-link details", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-reset-confirm" }));
      if (url === "/api/v1/auth/password-reset/confirm" && init?.method === "POST") return Promise.resolve(jsonResponse({ success: true }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/reset-password?uid=user-uid&token=signed-reset-token");

    fireEvent.change(await screen.findByLabelText("Neues Passwort"), { target: { value: "a-new-secure-password" } });
    fireEvent.change(screen.getByLabelText("Passwort bestätigen"), { target: { value: "a-new-secure-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Passwort speichern" }));

    expect(await screen.findByText("Dein Passwort wurde geändert. Du kannst dich jetzt wieder anmelden.")).toBeInTheDocument();
    const resetCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/v1/auth/password-reset/confirm");
    expect(resetCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-reset-confirm" }),
    }));
    const resetBody = new URLSearchParams(String(resetCall?.[1]?.body));
    expect(resetBody.get("uid")).toBe("user-uid");
    expect(resetBody.get("token")).toBe("signed-reset-token");
  });

  it("logs in through the Flask session API and opens the ticket area", async () => {
    let authenticated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(authenticated
          ? { authenticated: true, username: "frontendtest", can_help: true, csrf_token: "csrf-next" }
          : { authenticated: false, csrf_token: "csrf-login" }));
      }
      if (url === "/api/v1/auth/login" && init?.method === "POST") {
        authenticated = true;
        return Promise.resolve(jsonResponse({
          success: true,
          session: { authenticated: true, username: "frontendtest", can_help: true, csrf_token: "csrf-next" },
        }));
      }
      if (url === "/api/v1/me/tickets") {
        return Promise.resolve(jsonResponse({ checkin_qr: "data:image/png;base64,AA==", tickets: [] }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/login");

    fireEvent.change(await screen.findByLabelText("Benutzername"), { target: { value: "frontendtest" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "sample-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Einloggen" }));

    expect(await screen.findByText("Du hast noch keine Tickets.")).toBeInTheDocument();
    const loginCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/v1/auth/login");
    expect(loginCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-login" }),
    }));
    expect(new URLSearchParams(String(loginCall?.[1]?.body)).get("username")).toBe("frontendtest");
  });

  it("registers a new account with the server CAPTCHA and policy consent", async () => {
    let authenticated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(authenticated
          ? { authenticated: true, username: "newmember", can_help: false, csrf_token: "csrf-after-register" }
          : { authenticated: false, csrf_token: "csrf-register" }));
      }
      if (url === "/api/v1/auth/register" && !init?.method) {
        return Promise.resolve(jsonResponse({
          csrf_token: "csrf-register",
          roles: ["Gast", "Student"],
          captcha: { image: "data:image/jpeg;base64,AA==", hash: "signed-captcha-token" },
        }));
      }
      if (url === "/api/v1/auth/register" && init?.method === "POST") {
        authenticated = true;
        return Promise.resolve(jsonResponse({
          success: true,
          session: { authenticated: true, username: "newmember", can_help: false, csrf_token: "csrf-after-register" },
          verification_notice: false,
        }, 201));
      }
      if (url === "/api/v1/me/tickets") {
        return Promise.resolve(jsonResponse({ checkin_qr: "data:image/png;base64,AA==", tickets: [] }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/register");

    expect(await screen.findByRole("img", { name: "Zeichen aus dem CAPTCHA" })).toHaveAttribute(
      "src",
      "data:image/jpeg;base64,AA==",
    );
    fireEvent.change(screen.getByLabelText("Benutzername"), { target: { value: "newmember" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "sample-password" } });
    fireEvent.change(screen.getByLabelText("Passwort bestätigen"), { target: { value: "sample-password" } });
    fireEvent.change(screen.getByLabelText("Sicherheitsabfrage"), { target: { value: "ABC123" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));

    expect(await screen.findByText("Du hast noch keine Tickets.")).toBeInTheDocument();
    const registerCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === "/api/v1/auth/register" && init?.method === "POST",
    );
    expect(registerCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-register" }),
    }));
    const registrationBody = new URLSearchParams(String(registerCall?.[1]?.body));
    expect(registrationBody.get("captcha-text")).toBe("ABC123");
    expect(registrationBody.get("captcha-hash")).toBe("signed-captcha-token");
    expect(registrationBody.get("privacy_policy")).toBe("y");
  });

  it("keeps event management behind organizer permissions", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "guest",
          can_help: false,
          can_manage_events: false,
          csrf_token: "csrf-guest",
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");

    expect(await screen.findByRole("heading", { name: "Dir fehlt die Berechtigung für die Eventverwaltung." })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Eventmanager" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/events", expect.anything());
  });

  it("allows an organizer to create an event and refreshes the event list", async () => {
    let events: ManagedEvent[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "organizer",
          can_help: true,
          can_manage_events: true,
          can_create_events: true,
          can_edit_events: true,
          can_delete_events: true,
          can_manage_shifts: true,
          can_manage_registration_options: true,
          csrf_token: "csrf-organizer",
        }));
      }
      if (url === "/api/v1/manage/events" && init?.method === "POST") {
        const requestBody = JSON.parse(String(init.body)) as { name: string; place: string; date: string; visibility: string; description: string; end: string };
        const event: ManagedEvent = {
          ...requestBody,
          id: 91,
          uid: "new-event",
          poster_url: "/static/images/eventposter/new-event",
          task_count: 0,
          shifts: [],
          registration_options: [],
        };
        events = [event];
        return Promise.resolve(jsonResponse({ success: true, event }, 201));
      }
      if (url === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");

    expect(await screen.findByRole("heading", { name: "Eventmanager." })).toBeInTheDocument();
    fireEvent.click(await screen.findByText("Neues Event erstellen"));
    expect(screen.getByText(/Formatierung: <br> für Zeilenumbrüche und/)).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Eventname"), { target: { value: "Neues Demoevent" } });
    fireEvent.change(screen.getByLabelText("Ort"), { target: { value: "Plan B" } });
    fireEvent.change(screen.getByLabelText("Beginn"), { target: { value: "2027-07-01T18:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Event erstellen" }));

    expect(await screen.findByText("Event wurde erstellt.")).toBeInTheDocument();
    expect(screen.getAllByText("Neues Demoevent").length).toBeGreaterThan(0);
    const createCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === "/api/v1/manage/events" && init?.method === "POST",
    );
    expect(createCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-organizer" }),
    }));
  });

  it("uploads a poster image after creating an event", async () => {
    let events: ManagedEvent[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "organizer",
          can_manage_events: true,
          can_create_events: true,
          can_edit_events: true,
          csrf_token: "csrf-poster",
        }));
      }
      if (url === "/api/v1/manage/events" && init?.method === "POST") {
        const values = JSON.parse(String(init.body)) as Partial<ManagedEvent>;
        const event: ManagedEvent = {
          ...values,
          id: 91,
          uid: "new-event",
          poster_url: "/static/images/eventposter/new-event",
          task_count: 0,
          shifts: [],
          registration_options: [],
        } as ManagedEvent;
        events = [event];
        return Promise.resolve(jsonResponse({ success: true, event }, 201));
      }
      if (url === "/api/v1/manage/events/91/poster" && init?.method === "POST") {
        const upload = init.body as FormData;
        expect(upload.get("file")).toBeInstanceOf(File);
        events = [{
          ...events[0],
          poster_url: "/static/images/eventposter/new-event?v=123",
        }];
        return Promise.resolve(jsonResponse({ success: true, event: events[0] }));
      }
      if (url === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");

    fireEvent.click(await screen.findByText("Neues Event erstellen"));
    fireEvent.change(await screen.findByLabelText("Eventname"), { target: { value: "Poster-Event" } });
    fireEvent.change(screen.getByLabelText("Beginn"), { target: { value: "2027-08-01T18:00" } });
    fireEvent.change(screen.getByLabelText(/Eventbild/), {
      target: { files: [new File(["image"], "poster.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Event erstellen" }));

    expect(await screen.findByText("Event wurde erstellt.")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/events/91/poster",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("replaces an existing event poster when editing", async () => {
    let event: ManagedEvent = {
      id: 91,
      uid: "edit-event",
      name: "Poster bearbeiten",
      visibility: "public",
      place: "Plan B",
      date: "2027-08-01T18:00",
      end: null,
      description: "",
      poster_url: "/static/images/eventposter/edit-event?v=111",
      task_count: 0,
      shifts: [],
      registration_options: [],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "organizer",
          can_manage_events: true,
          can_edit_events: true,
          csrf_token: "csrf-edit-poster",
        }));
      }
      if (url === "/api/v1/manage/events/91" && init?.method === "PUT") {
        event = { ...event, ...(JSON.parse(String(init.body)) as Partial<ManagedEvent>) };
        return Promise.resolve(jsonResponse({ success: true, event }));
      }
      if (url === "/api/v1/manage/events/91/poster" && init?.method === "POST") {
        const upload = init.body as FormData;
        expect(upload.get("file")).toBeInstanceOf(File);
        event = { ...event, poster_url: "/static/images/eventposter/edit-event?v=222" };
        return Promise.resolve(jsonResponse({ success: true, event }));
      }
      if (url === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events: [event] }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");

    fireEvent.click(await screen.findByRole("button", { name: /Poster bearbeiten/ }));
    expect(screen.getByAltText("Vorschau des Eventbilds")).toHaveAttribute(
      "src",
      "/static/images/eventposter/edit-event?v=111",
    );
    fireEvent.change(screen.getByLabelText(/Eventbild/), {
      target: { files: [new File(["image"], "new-poster.jpg", { type: "image/jpeg" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Event speichern" }));

    expect(await screen.findByText("Eventänderungen wurden gespeichert.")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/events/91/poster",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("sorts managed events by start date and can hide past events after the grace period", async () => {
    const now = Date.now();
    const dateAt = (offsetMs: number) => new Date(now + offsetMs).toISOString();
    const baseEvent: ManagedEvent = {
      id: 1,
      uid: "past-event",
      name: "Vergangenes Event",
      visibility: "public",
      place: "Plan B",
      date: dateAt(-13 * 60 * 60 * 1000),
      end: null,
      description: "",
      poster_url: "/static/images/eventposter/past-event",
      task_count: 0,
      shifts: [],
      registration_options: [],
    };
    const events: ManagedEvent[] = [
      baseEvent,
      { ...baseEvent, id: 2, uid: "grace-event", name: "Event in der Gnadenfrist", date: dateAt(-2 * 60 * 60 * 1000) },
      { ...baseEvent, id: 3, uid: "future-event", name: "Zukünftiges Event", date: dateAt(48 * 60 * 60 * 1000) },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "organizer",
          can_manage_events: true,
          csrf_token: "csrf-filter",
        }));
      }
      if (url === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const managedRowNames = () => screen
      .getAllByRole("button")
      .filter((button) => button.className.includes("managed-event-row__select"))
      .map((button) => button.querySelector(".managed-event-row__name")?.textContent);

    renderApp("/manage/events");

    await screen.findByText("Zukünftiges Event");
    expect(screen.getByRole("option", { name: "Späteste zuerst" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Früheste zuerst" })).toBeInTheDocument();
    expect(managedRowNames()).toEqual(["Zukünftiges Event", "Event in der Gnadenfrist", "Vergangenes Event"]);

    fireEvent.click(screen.getByLabelText("Vergangene ausblenden"));
    expect(managedRowNames()).toEqual(["Zukünftiges Event", "Event in der Gnadenfrist"]);

    fireEvent.change(screen.getByLabelText("Sortierung"), { target: { value: "asc" } });
    expect(managedRowNames()).toEqual(["Event in der Gnadenfrist", "Zukünftiges Event"]);
  });

  it("opens shift and registration forms on demand and closes them after saving", async () => {
    let managedEvent: ManagedEvent = {
      id: 91,
      uid: "form-event",
      name: "Form workflow event",
      visibility: "public",
      place: "Plan B",
      date: summerParty.date,
      end: null,
      description: "",
      poster_url: "/poster",
      task_count: 0,
      shifts: [],
      registration_options: [],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "organizer",
        can_manage_events: true,
        can_manage_shifts: true,
        can_manage_registration_options: true,
        csrf_token: "csrf-inline-forms",
      }));
      if (path === "/api/v1/manage/events/91/shifts" && init?.method === "POST") {
        const values = JSON.parse(String(init.body)) as { type: string; start: string; end: string };
        managedEvent = {
          ...managedEvent,
          shifts: [{ id: 17, type: values.type, start: values.start || null, end: values.end || null, participants: 0 }],
        };
        return Promise.resolve(jsonResponse({ success: true, event: managedEvent }));
      }
      if (path === "/api/v1/manage/events/91/shifts/17" && init?.method === "PUT") {
        const values = JSON.parse(String(init.body)) as { type: string; start: string; end: string };
        managedEvent = {
          ...managedEvent,
          shifts: [{ id: 17, type: values.type, start: values.start || null, end: values.end || null, participants: 0 }],
        };
        return Promise.resolve(jsonResponse({ success: true, event: managedEvent }));
      }
      if (path === "/api/v1/manage/events/91/registrations" && init?.method === "POST") {
        const values = JSON.parse(String(init.body)) as { name: string; visibility: string; accept: string; deny: string; start: string; end: string; price: string };
        managedEvent = {
          ...managedEvent,
          registration_options: [{ id: 23, ...values, start: values.start || null, end: values.end || null, price: values.price || 0 }],
        };
        return Promise.resolve(jsonResponse({ success: true, event: managedEvent }));
      }
      if (path === "/api/v1/manage/events/91/registrations/23" && init?.method === "PUT") {
        const values = JSON.parse(String(init.body)) as { name: string; visibility: string; accept: string; deny: string; start: string; end: string; price: string };
        managedEvent = {
          ...managedEvent,
          registration_options: [{ id: 23, ...values, start: values.start || null, end: values.end || null, price: values.price || 0 }],
        };
        return Promise.resolve(jsonResponse({ success: true, event: managedEvent }));
      }
      if (path === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events: [managedEvent] }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");
    fireEvent.click(await screen.findByRole("button", { name: /Form workflow event/ }));
    expect(screen.queryByLabelText("Bezeichnung")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Neue Helferschicht hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Bezeichnung"), { target: { value: "Aufbau" } });
    fireEvent.click(screen.getByRole("button", { name: "Schicht hinzufügen" }));
    expect(await screen.findByText("Helferschicht wurde erstellt.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Bezeichnung")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Helferschicht Aufbau bearbeiten" }));
    expect(await screen.findByLabelText("Bezeichnung")).toHaveValue("Aufbau");
    fireEvent.change(screen.getByLabelText("Bezeichnung"), { target: { value: "Aufbau und Deko" } });
    fireEvent.click(screen.getByRole("button", { name: "Schicht speichern" }));
    expect(await screen.findByText("Helferschicht wurde geändert.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Bezeichnung")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Neue Anmeldung hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Abendkasse" } });
    fireEvent.click(screen.getByRole("button", { name: "Anmeldung hinzufügen" }));
    expect(await screen.findByText("Anmeldemöglichkeit wurde erstellt.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Name")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Anmeldung Abendkasse bearbeiten" }));
    expect(await screen.findByLabelText("Name")).toHaveValue("Abendkasse");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Abendkasse Plus" } });
    fireEvent.click(screen.getByRole("button", { name: "Anmeldung speichern" }));
    expect(await screen.findByText("Anmeldemöglichkeit wurde geändert.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Name")).not.toBeInTheDocument());
  });

  it("moves the event end with the start and sends the move flag", async () => {
    let managedEvent: ManagedEvent = {
      id: 91,
      uid: "move-event",
      name: "Move workflow event",
      visibility: "public",
      place: "Plan B",
      date: "2027-06-12T18:00",
      end: "2027-06-12T23:00",
      description: "",
      poster_url: "/poster",
      task_count: 0,
      shifts: [],
      registration_options: [],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "organizer",
        can_manage_events: true,
        can_edit_events: true,
        csrf_token: "csrf-move",
      }));
      if (path === "/api/v1/manage/events/91" && init?.method === "PUT") {
        const values = JSON.parse(String(init.body)) as Partial<ManagedEvent>;
        managedEvent = { ...managedEvent, ...values };
        return Promise.resolve(jsonResponse({ success: true, event: managedEvent }));
      }
      if (path === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events: [managedEvent] }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");
    fireEvent.click(await screen.findByRole("button", { name: /Move workflow event/ }));

    expect(document.querySelector(".managed-event-list")).toContainElement(
      screen.getByRole("button", { name: "Event speichern" }),
    );
    fireEvent.change(screen.getByLabelText("Beginn"), { target: { value: "2027-06-14T18:00" } });
    expect(screen.getByLabelText("Ende")).toHaveValue("2027-06-14T23:00");
    fireEvent.click(screen.getByRole("button", { name: "Event speichern" }));

    expect(await screen.findByText("Eventänderungen wurden gespeichert.")).toBeInTheDocument();
    const updateCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === "/api/v1/manage/events/91" && init?.method === "PUT",
    );
    const body = JSON.parse(String(updateCall?.[1]?.body));
    expect(body.date).toBe("2027-06-14T18:00");
    expect(body.end).toBe("2027-06-14T23:00");
    expect(body.move_shifts).toBe(true);
  });

  it("lets event managers assign only users returned as eligible to registrations and shifts", async () => {
    const attendee = { uid: "member-uid", username: "memberone", surname: "Mia", lastname: "Member", role: "Mitglied" };
    let registrationUsers: typeof attendee[] = [];
    let shiftUsers: typeof attendee[] = [];
    const managedEvent = (): ManagedEvent => ({
      id: 91,
      uid: "assignment-event",
      name: "Assignment event",
      visibility: "member",
      place: "Plan B",
      date: summerParty.date,
      end: null,
      description: "",
      poster_url: "/poster",
      task_count: 0,
      shifts: [{ id: 17, type: "Bar", start: null, end: null, participants: shiftUsers.length, assigned_users: shiftUsers }],
      registration_options: [{ id: 23, name: "Dinner ticket", visibility: "member", accept: "geöffnet", deny: "erlaubt", start: null, end: null, price: "10.00", participants: registrationUsers }],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "organizer",
        can_manage_events: true,
        can_manage_shifts: true,
        can_manage_registration_options: true,
        csrf_token: "csrf-assignment",
      }));
      if (url.pathname === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events: [managedEvent()] }));
      if (url.pathname.endsWith("/users") && url.searchParams.get("q") === "mi") {
        return Promise.resolve(jsonResponse({ users: [attendee] }));
      }
      if (url.pathname === "/api/v1/manage/events/91/assignments/registration/23" && init?.method === "POST") {
        registrationUsers = [attendee];
        return Promise.resolve(jsonResponse({ success: true }));
      }
      if (url.pathname === "/api/v1/manage/events/91/assignments/shift/17" && init?.method === "POST") {
        shiftUsers = [attendee];
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events");
    fireEvent.click(await screen.findByRole("button", { name: /Assignment event/ }));
    expect(screen.queryByLabelText("Bezeichnung")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Neue Helferschicht hinzufügen" }));
    expect(await screen.findByLabelText("Bezeichnung")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    await waitFor(() => expect(screen.queryByLabelText("Bezeichnung")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Neue Anmeldung hinzufügen" }));
    expect(await screen.findByLabelText("Name")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    await waitFor(() => expect(screen.queryByLabelText("Name")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Teilnehmende hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Nutzername oder Name suchen"), { target: { value: "mi" } });
    const addRegistrationButton = await screen.findByRole("button", { name: /Zur Anmeldung hinzufügen/ });
    expect(addRegistrationButton).toBeEnabled();
    fireEvent.click(addRegistrationButton);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/manage/events/91/assignments/registration/23", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("@memberone · Mitglied")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Helfer:innen zur Schicht hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Nutzername oder Name suchen"), { target: { value: "mi" } });
    fireEvent.click(await screen.findByRole("button", { name: /Für die Schicht eintragen/ }));
    expect(await screen.findAllByText("@memberone · Mitglied")).toHaveLength(2);

    const addCalls = fetchMock.mock.calls.filter(([url, init]) => String(url).includes("/assignments/") && init?.method === "POST");
    expect(addCalls).toHaveLength(2);
    expect(addCalls.map(([, init]) => JSON.parse(String(init?.body)))).toEqual([
      { user_uid: "member-uid" },
      { user_uid: "member-uid" },
    ]);
  });

  it("lets an attendee join and leave an event task", async () => {
    let assigned = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "student",
          can_help: false,
          csrf_token: "csrf-task-user",
        }));
      }
      if (url === "/api/v1/events/12/tasks") return Promise.resolve(jsonResponse(demoTaskBoard(assigned)));
      if (url === "/api/v1/tasks/58/join" && init?.method === "POST") {
        assigned = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      if (url === "/api/v1/tasks/58/leave" && init?.method === "POST") {
        assigned = false;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/events/12/tasks");

    fireEvent.click(await screen.findByRole("button", { name: "Bei dieser Vorbereitung mithelfen" }));
    expect(await screen.findByRole("button", { name: "Nicht mehr helfen" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nicht mehr helfen" }));
    expect(await screen.findByRole("button", { name: "Bei dieser Vorbereitung mithelfen" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/tasks/58/join",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-task-user" }),
      }),
    );
  });

  it("renders member-scoped tasks returned for a member role", async () => {
    const memberTask: EventTaskBoard = {
      event: { id: 12, name: "Mitgliedertreffen", date: summerParty.date, place: "Plan B" },
      can_manage: false,
      tasks: [{
        id: 77,
        event_id: 12,
        name: "Mitgliederraum vorbereiten",
        description: "",
        status: "TakeOverTask",
        priority: "mittel",
        visibility: "member",
        deadline: null,
        timeframe_start: null,
        timeframe_end: null,
        helper_count: 0,
        assigned_to_me: false,
        can_join: true,
        can_leave: false,
        can_manage: false,
      }],
    };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "mitgliederkonto", csrf_token: "csrf-member-task" }));
      if (String(input) === "/api/v1/events/12/tasks") return Promise.resolve(jsonResponse(memberTask));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/events/12/tasks");

    expect(await screen.findByRole("heading", { name: "Mitgliederraum vorbereiten" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bei dieser Vorbereitung mithelfen" })).toBeInTheDocument();
  });

  it("lets an authorized organizer create an event task", async () => {
    let tasks: EventTaskBoard["tasks"] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "organizer",
          can_manage_events: true,
          can_manage_tasks: true,
          csrf_token: "csrf-task-admin",
        }));
      }
      if (url === "/api/v1/manage/events/12/tasks" && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { name: string; description: string; status: string; priority: string; visibility: string; deadline: string; timeframe_start: string; timeframe_end: string };
        const task: EventTaskBoard["tasks"][number] = {
          id: 59,
          event_id: 12,
          ...body,
          helper_count: 0,
          assigned_to_me: false,
          can_join: false,
          can_leave: false,
          can_manage: true,
        };
        tasks = [task];
        return Promise.resolve(jsonResponse({ success: true, task }, 201));
      }
      if (url === "/api/v1/manage/events/12/tasks/59" && init?.method === "PUT") {
        const fields = JSON.parse(String(init.body)) as { name: string; description: string; status: string; priority: string; visibility: string; deadline: string; timeframe_start: string; timeframe_end: string };
        tasks = tasks.map((task) => task.id === 59 ? { ...task, ...fields } : task);
        return Promise.resolve(jsonResponse({ success: true, task: tasks.find((task) => task.id === 59) }));
      }
      if (url === "/api/v1/manage/events/12/tasks") {
        return Promise.resolve(jsonResponse({
          event: { id: 12, name: "SIA Sommerfest", date: summerParty.date, place: "Plan B, Albstadt" },
          tasks,
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events/12/tasks");

    expect(screen.queryByLabelText("Name der Vorbereitung")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Vorbereitung hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Name der Vorbereitung"), { target: { value: "Aufbau unterstützen" } });
    fireEvent.click(screen.getByRole("button", { name: "Vorbereitung erstellen" }));
    expect(await screen.findByText("Vorbereitung wurde erstellt.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Name der Vorbereitung")).not.toBeInTheDocument();
    expect(screen.getByText("Aufbau unterstützen")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Aufbau unterstützen/ }));
    expect(await screen.findByLabelText("Name der Vorbereitung")).toHaveValue("Aufbau unterstützen");
    fireEvent.change(screen.getByLabelText("Name der Vorbereitung"), { target: { value: "Aufbau vorbereiten" } });
    fireEvent.click(screen.getByRole("button", { name: "Vorbereitung speichern" }));
    expect(await screen.findByText("Vorbereitung wurde geändert.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Name der Vorbereitung")).not.toBeInTheDocument());
    expect(screen.getByText("Aufbau vorbereiten")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/events/12/tasks",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-task-admin" }),
      }),
    );
  });

  it("lets a task manager assign an eligible member to a task", async () => {
    const attendee = { uid: "member-uid", username: "memberone", surname: "Mia", lastname: "Member", role: "Mitglied" };
    let helpers: typeof attendee[] = [];
    const task = () => ({
      id: 44,
      event_id: 12,
      name: "Bar vorbereiten",
      description: "",
      status: "TakeOverTask",
      priority: "mittel",
      visibility: "member",
      deadline: null,
      timeframe_start: null,
      timeframe_end: null,
      helper_count: helpers.length,
      helpers,
      assigned_to_me: false,
      can_join: false,
      can_leave: false,
      can_manage: true,
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://localhost");
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "organizer",
        can_manage_tasks: true,
        csrf_token: "csrf-task-assignment",
      }));
      if (url.pathname === "/api/v1/manage/events/12/tasks") return Promise.resolve(jsonResponse({
        event: { id: 12, name: "SIA Sommerfest", date: summerParty.date, place: "Plan B" },
        tasks: [task()],
        can_assign_helpers: true,
      }));
      if (url.pathname === "/api/v1/manage/events/12/assignments/task/44/users") return Promise.resolve(jsonResponse({ users: [attendee] }));
      if (url.pathname === "/api/v1/manage/events/12/assignments/task/44" && init?.method === "POST") {
        helpers = [attendee];
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/manage/events/12/tasks");
    fireEvent.click(await screen.findByRole("button", { name: "Helfer:innen zur Vorbereitung hinzufügen" }));
    fireEvent.change(await screen.findByLabelText("Nutzername oder Name suchen"), { target: { value: "mi" } });
    const addTaskButton = await screen.findByRole("button", { name: /Der Vorbereitung zuordnen/ });
    expect(addTaskButton).toBeEnabled();
    fireEvent.click(addTaskButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/manage/events/12/assignments/task/44", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("@memberone · Mitglied")).toBeInTheDocument();
    const assignmentCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/events/12/assignments/task/44" && init?.method === "POST");
    expect(JSON.parse(String(assignmentCall?.[1]?.body))).toEqual({ user_uid: "member-uid" });
    expect(assignmentCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-task-assignment" }));
  });

  it("shows the legacy-style home page with links into the existing sections", async () => {
    mockEvents([summerParty]);

    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Das Plan B" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verein" })).toHaveAttribute("href", "/verein");
    expect(screen.getByRole("link", { name: "Location" })).toHaveAttribute("href", "/location");
    expect(screen.getByRole("link", { name: "Kontakt" })).toHaveAttribute("href", "/contact");
    expect(await screen.findByRole("heading", { name: "SIA Sommerfest" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Alle kommenden Events" })).toHaveAttribute("href", "/events");
  });

  it("recreates the club information and history sections", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ authenticated: false }))));

    renderApp("/verein");

    expect(await screen.findByRole("heading", { name: /Von Studierenden/ })).toBeInTheDocument();
    expect(screen.getByText(/studentischer Verein/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ein Stück Geschichte." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mitmachen" })).toHaveAttribute("href", "/register");
  });

  it("shows the location gallery, 3D viewer control, and rental contact path", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ authenticated: false }))));

    renderApp("/location");

    expect(await screen.findByRole("heading", { name: /Der Treffpunkt der SIA/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3D-Ansicht öffnen" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Location anfragen/ })).toHaveAttribute(
      "href",
      "/contact?category=mieten",
    );
    expect(screen.getByRole("img", { name: "Barbereich im Plan B" })).toBeInTheDocument();
  });

  it("renders the public drink menu with hidden prices and the QR code", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false }));
      if (url === "/api/v1/drink-menu") {
        return Promise.resolve(jsonResponse({
          sections: [
            {
              uid: "section-longdrink",
              title: "Mix your own Longdrink",
              subtitle: "5 cl Alkohol deiner Wahl + Alkoholfreies Mischgetränk",
              price_cents: 500,
              show_price: true,
              sort_order: 1,
              is_active: true,
              items: [
                { uid: "item-tequila", name: "Tequila", group_label: "Alkohol · 5 cl", description: "", volume_label: "", price_cents: null, show_price: false, image_url: "", sort_order: 1, is_active: true },
                { uid: "item-cola", name: "Cola", group_label: "Mischgetränk", description: "", volume_label: "", price_cents: null, show_price: false, image_url: "", sort_order: 2, is_active: true },
              ],
            },
            {
              uid: "section-bier",
              title: "Bier",
              subtitle: "",
              price_cents: null,
              show_price: false,
              sort_order: 2,
              is_active: true,
              items: [
                { uid: "item-helles", name: "Hirsch Helles", group_label: "", description: "", volume_label: "0,5 l", price_cents: 350, show_price: true, image_url: "/static/images/drinks/helles.png", sort_order: 1, is_active: true },
                { uid: "item-zwuckl", name: "Hirsch Zwuckl", group_label: "", description: "", volume_label: "0,33 l", price_cents: 300, show_price: false, image_url: "", sort_order: 2, is_active: true },
              ],
            },
          ],
          updated_at: "2026-10-13T22:00",
          qr_data_url: "data:image/png;base64,AA==",
          menu_url: "https://beta.example.test/getraenkekarte",
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/getraenkekarte");

    expect(await screen.findByRole("heading", { name: "Getränkekarte." })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Mix your own Longdrink" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Getränke" })).toHaveAttribute("href", "/getraenkekarte");
    expect(screen.getByText("Alkohol · 5 cl")).toBeInTheDocument();
    expect(screen.getByText("Hirsch Helles")).toBeInTheDocument();
    expect(screen.getByText("0,5 l")).toBeInTheDocument();
    expect(screen.getByText(/5,00/)).toBeInTheDocument();
    expect(screen.getByText(/3,50/)).toBeInTheDocument();
    expect(screen.queryByText(/3,00/)).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "QR-Code zur Getränkekarte" })).toHaveAttribute("src", "data:image/png;base64,AA==");
    expect(screen.getByText(/2 € Becher/)).toBeInTheDocument();
  });

  it("manages the drink menu inside the Admin tool", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "menudemo",
          can_admin_panel: true,
          can_manage_drink_menu: true,
          csrf_token: "csrf-menu",
        }));
      }
      if (url === "/api/v1/manage/drink-menu") {
        return Promise.resolve(jsonResponse({
          sections: [{
            uid: "section-bier",
            title: "Bier",
            subtitle: "",
            price_cents: null,
            show_price: false,
            sort_order: 1,
            is_active: true,
            items: [{
              uid: "item-helles",
              name: "Hirsch Helles",
              group_label: "",
              description: "",
              volume_label: "0,5 l",
              price_cents: 350,
              show_price: true,
              image_url: "",
              sort_order: 1,
              is_active: true,
            }],
          }],
          menu_url: "https://beta.example.test/getraenkekarte",
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");

    fireEvent.click(await screen.findByRole("tab", { name: "Getränkekarte" }));

    expect(await screen.findByRole("heading", { name: "Öffentliche Karte." })).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Bier")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Hirsch Helles")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox", { name: "Preis anzeigen" }).some((toggle) => (toggle as HTMLInputElement).checked)).toBe(true);
  });

  it("submits anonymous feedback with CAPTCHA and privacy consent", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: false, csrf_token: "csrf-public" }));
      if (url === "/api/v1/contact" && !init?.method) {
        return Promise.resolve(jsonResponse({
          csrf_token: "csrf-contact",
          categories: [
            { value: "kontakt", label: "Kontakt" },
            { value: "mieten", label: "Location mieten" },
            { value: "feedback", label: "Kritik oder Lob" },
            { value: "events", label: "Wünsche für ein Event" },
          ],
          captcha: { image: "data:image/jpeg;base64,AA==", hash: "contact-captcha-token" },
          prefill: { surname: "", lastname: "", email: "" },
        }));
      }
      if (url === "/api/v1/contact" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ success: true, message: "Danke für deine Nachricht!" }, 201));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/contact?category=feedback");

    await screen.findByRole("option", { name: "Kritik oder Lob" });
    expect(screen.getByLabelText("Art der Anfrage")).toHaveValue("feedback");
    fireEvent.change(screen.getByLabelText("Nachricht"), {
      target: { value: "Das ist eine ausreichend lange Feedback-Nachricht." },
    });
    fireEvent.change(screen.getByLabelText("Sicherheitsabfrage"), { target: { value: "ABC123" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Anfrage senden" }));

    expect(await screen.findByText("Danke für deine Nachricht!")).toBeInTheDocument();
    const contactCall = fetchMock.mock.calls.find(([url, init]) =>
      String(url) === "/api/v1/contact" && init?.method === "POST",
    );
    expect(contactCall?.[1]).toEqual(expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-contact" }),
    }));
    const body = new URLSearchParams(String(contactCall?.[1]?.body));
    expect(body.get("category")).toBe("feedback");
    expect(body.get("captcha-hash")).toBe("contact-captcha-token");
    expect(body.get("privacy_policy")).toBe("y");
  });

  it("keeps the ticket scanner restricted to authorized users", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "guest", can_scan_tickets: false }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/scanner");

    expect(await screen.findByRole("heading", { name: "Dir fehlt die Berechtigung für den Scanner." })).toBeInTheDocument();
  });

  it("loads scanned tickets and updates validation/payment status", async () => {
    let valid = false;
    let paid = false;
    let lookupRequest: unknown;
    const ticket = () => [{
      id: 71,
      userUID: "demo-user-uid",
      users: "Demo Mitglied",
      rm_name: "Abendkasse",
      price: "8.50",
      paid,
      payment_status: paid ? "paid" : "partially_paid",
      remaining_cents: paid ? 0 : 250,
      valid,
    }];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "eventmanagerdemo",
          can_scan_tickets: true,
          can_validate_tickets: true,
          can_punch_tickets: true,
          can_manage_ticket_payment: true,
          csrf_token: "csrf-scanner",
        }));
      }
      if (url === "/api/user/get/scanner" && init?.method === "POST") {
        lookupRequest = JSON.parse(String(init.body));
        return Promise.resolve(jsonResponse(ticket()));
      }
      if (url === "/api/events/event/registration/validate/71" && init?.method === "POST") {
        valid = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      if (url === "/api/events/event/registration/paid/71" && init?.method === "POST") {
        paid = true;
        return Promise.resolve(jsonResponse({ success: true }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/scanner");

    fireEvent.change(await screen.findByLabelText("Benutzernamen manuell eingeben"), {
      target: { value: "DemoMember" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Nutzer laden" }));

    expect(await screen.findByText("Demo Mitglied")).toBeInTheDocument();
    expect(await screen.findByText(/Teilweise bezahlt.*offen/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Als gültig markieren" }));
    expect(await screen.findByText("Gültig")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Als bezahlt markieren" }));
    expect(await screen.findByText("Bezahlt")).toBeInTheDocument();
    expect(lookupRequest).toEqual({ username: "demomember" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/events/event/registration/validate/71",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-scanner" }),
      }),
    );
  });

  it("shows a readable scanner error when the server responds with HTML", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse({
          authenticated: true,
          username: "eventmanagerdemo",
          can_scan_tickets: true,
          can_validate_tickets: true,
          can_punch_tickets: true,
          can_manage_ticket_payment: true,
          csrf_token: "csrf-scanner-html",
        }));
      }
      if (url === "/api/user/get/scanner") {
        return Promise.resolve(new Response("<!doctype html><title>Sign in</title>", { headers: { "Content-Type": "text/html" } }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/scanner");

    fireEvent.change(await screen.findByLabelText("Benutzernamen manuell eingeben"), { target: { value: "demomember" } });
    fireEvent.click(screen.getByRole("button", { name: "Nutzer laden" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Der Scanner-Server hat keine gültige JSON-Antwort geliefert.");
  });

  it("shows a card for each personal shift and task commitment", async () => {
    const commitments: MyCommitments = {
      shifts: [{
        id: 21,
        shift_id: 4,
        type: "Aufbau",
        start: "2027-06-12T16:00:00+02:00",
        end: "2027-06-12T18:00:00+02:00",
        can_leave: true,
        event: { id: 12, name: "SIA Sommerfest", date: summerParty.date, place: "Plan B, Albstadt" },
      }],
      tasks: [{
        id: 31,
        task_id: 8,
        name: "Bar vorbereiten",
        status: "InProgress",
        priority: "mittel",
        deadline: "2027-06-12T17:00:00+02:00",
        timeframe_start: "2027-06-12T14:00:00+02:00",
        timeframe_end: "2027-06-12T15:00:00+02:00",
        can_leave: true,
        event: { id: 12, name: "SIA Sommerfest", date: summerParty.date, place: "Plan B, Albstadt" },
      }],
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "silas", csrf_token: "csrf-commitments" }));
      if (url === "/api/v1/me/commitments") return Promise.resolve(jsonResponse(commitments));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/commitments");

    expect(await screen.findByRole("heading", { name: "Aufbau" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bar vorbereiten" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Meine Vorbereitungen." })).toBeInTheDocument();
    expect(screen.getByText(/14:00 – 15:00/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Meine Tickets ansehen/ })).toHaveAttribute("href", "/me/registrations");
  });

  it("keeps the Admin user and contact tabs behind admin permission", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ authenticated: true, username: "member", can_admin_panel: false }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "Dir fehlt die Berechtigung für das Admintool." })).toBeInTheDocument();
  });

  it("opens event and task management workflows inside the Admin tabs", async () => {
    const managedEvent: ManagedEvent = {
      id: 12,
      uid: "event-uid",
      name: "SIA Sommerfest",
      visibility: "public",
      place: "Plan B, Albstadt",
      date: summerParty.date,
      end: summerParty.end,
      description: "Ein Abend mit Musik und guten Leuten.",
      poster_url: summerParty.poster_url,
      task_count: 1,
      shifts: [],
      registration_options: [],
    };
    const overviewTasks: ManagedTaskOverviewItem[] = [
      {
        id: 58,
        event_id: 12,
        event_name: "SIA Sommerfest",
        name: "Getränke vorbereiten",
        priority: "hoch",
        status: "TakeOverTask",
        visibility: "public",
        deadline: "2027-06-12T18:00:00+02:00",
        helper_count: 0,
      },
      {
        id: 59,
        event_id: 14,
        event_name: "Kinoabend",
        name: "Aufbau unterstützen",
        priority: "niedrig",
        status: "InProgress",
        visibility: "member",
        deadline: "2027-06-12T16:00:00+02:00",
        helper_count: 2,
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        can_admin_panel: true,
        can_manage_events: true,
        can_create_events: true,
        can_manage_tasks: true,
        csrf_token: "csrf-admin-workflows",
      }));
      if (url === "/api/v1/manage/events") return Promise.resolve(jsonResponse({ events: [managedEvent] }));
      if (url === "/api/v1/manage/events/12/tasks") return Promise.resolve(jsonResponse({
        event: { id: 12, name: managedEvent.name, date: managedEvent.date, place: managedEvent.place },
        tasks: [{
          id: 88,
          event_id: 12,
          name: "Aufbau unterstützen",
          description: "",
          status: "TakeOverTask",
          priority: "mittel",
          visibility: "public",
          deadline: null,
          timeframe_start: null,
          timeframe_end: null,
          helper_count: 0,
          assigned_to_me: false,
          can_join: false,
          can_leave: false,
          can_manage: true,
        }],
        can_assign_helpers: true,
      }));
      if (url === "/api/v1/manage/tasks") return Promise.resolve(jsonResponse({ tasks: overviewTasks }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");

    fireEvent.click(await screen.findByRole("tab", { name: "Events" }));
    expect(await screen.findByText("Neues Event erstellen")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /SIA Sommerfest/ }));
    expect(await screen.findByRole("heading", { name: "Vorbereitungen" })).toBeInTheDocument();
    expect(await screen.findByText("Aufbau unterstützen")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vorbereitung hinzufügen" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Vorbereitungen" }));
    expect(await screen.findByRole("heading", { name: "Vorbereitungsübersicht." })).toBeInTheDocument();
    expect(await screen.findByText("Aufbau unterstützen")).toBeInTheDocument();
    let taskRows = screen.getAllByRole("row");
    expect(taskRows[1]).toHaveTextContent("Aufbau unterstützen");
    expect(taskRows[2]).toHaveTextContent("Getränke vorbereiten");
    fireEvent.click(screen.getByRole("button", { name: "Priorität" }));
    taskRows = screen.getAllByRole("row");
    expect(taskRows[1]).toHaveTextContent("Getränke vorbereiten");
    expect(taskRows[2]).toHaveTextContent("Aufbau unterstützen");
    expect(screen.getAllByRole("link", { name: "Öffnen" }).map((link) => link.getAttribute("href"))).toContain("/manage/events/12/tasks");
  });

  it("shows a scrollable admin user list with most recently active users first", async () => {
    const user = (username: string, last_login: string | null): AdminUser => ({
      id: username === "active-member" ? 71 : 72,
      uid: `${username}-uid`,
      username,
      role: "Mitglied",
      surname: username,
      lastname: "Demo",
      email: `${username}@example.invalid`,
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      street: "",
      street_no: "",
      city: "",
      postalcode: "",
      register_date: "2026-01-01",
      last_login,
      last_updated: "2026-06-01",
    });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        can_admin_panel: true,
        can_manage_users: true,
      }));
      if (url === "/api/v1/manage/users") return Promise.resolve(jsonResponse({
        roles: ["Mitglied"],
        users: [user("quiet-member", "2026-05-01 12:00:00"), user("active-member", "2026-06-01 12:00:00")],
      }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/admin");

    expect(await screen.findByRole("table", { name: "Benutzerliste" })).toBeInTheDocument();
    let rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("active-member");
    expect(rows[2]).toHaveTextContent("quiet-member");
    fireEvent.click(screen.getByRole("button", { name: "Zuletzt aktiv" }));
    rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("quiet-member");
    expect(rows[2]).toHaveTextContent("active-member");
  });

  it("lets admins review role applications independently of Finance membership applications", async () => {
    let requestPending = true;
    const roleRequest = {
      id: 31,
      uid: "role-request-uid",
      user_uid: "alumni-uid",
      username: "oldalumni",
      surname: "Alex",
      lastname: "Alumni",
      current_role: "Sia-Alumni",
      requested_role: "Mitglied",
      request_note: "Ich bin wieder regelmäßig am Campus.",
      status: "pending",
      submitted_at: "2027-01-02T12:00:00+01:00",
      reviewed_at: null,
      review_note: "",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        can_admin_panel: true,
        can_update_users: true,
        csrf_token: "csrf-role-review",
      }));
      if (url === "/api/v1/manage/role-requests/31/review" && init?.method === "POST") {
        requestPending = false;
        return Promise.resolve(jsonResponse({ success: true, request: { ...roleRequest, status: "approved" } }));
      }
      if (url === "/api/v1/manage/role-requests") return Promise.resolve(jsonResponse({ requests: requestPending ? [roleRequest] : [] }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Rollenanträge" }));
    expect(await screen.findByText("Ich bin wieder regelmäßig am Campus.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rolle genehmigen" }));

    expect(await screen.findByText("Keine offenen Rollenänderungsanträge.")).toBeInTheDocument();
    const reviewCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/role-requests/31/review" && init?.method === "POST");
    expect(JSON.parse(String(reviewCall?.[1]?.body))).toEqual({ decision: "approve", note: "" });
    expect(reviewCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-role-review" }));
  });

  it("lets a signed-in member add their own drink to the tally", async () => {
    let balance = 620;
    const charges: Array<Record<string, unknown>> = [{
      uid: "waived-dues-uid",
      kind: "membership",
      name: "Mitgliedsbeitrag 2027 (student)",
      fee_category: "student",
      cycle_year: 2027,
      quantity: 1,
      unit_price_cents: 0,
      amount_cents: 0,
      due_date: "2027-03-01",
      status: "waived",
      created_at: "2026-10-11T10:00:00+02:00",
      status_at: "2026-10-11T10:00:00+02:00",
      status_note: "Beitragsfreies erstes Mitgliedsjahr.",
    }];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "frontendtest",
        csrf_token: "csrf-finance-member",
      }));
      if (url === "/api/v1/me/finance/purchases" && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { item_id: number; quantity: number };
        const charge = {
          uid: "drink-charge-uid",
          kind: "drink",
          name: "Glasflaschen",
          fee_category: null,
          cycle_year: null,
          quantity: body.quantity,
          unit_price_cents: 250,
          amount_cents: 250 * body.quantity,
          due_date: null,
          status: "open",
          created_at: "2026-10-11T10:00:00+02:00",
          status_at: null,
          status_note: "",
        };
        charges.push(charge);
        balance += 250 * body.quantity;
        return Promise.resolve(jsonResponse({ success: true, charge, balance_cents: balance }, 201));
      }
      if (url === "/api/v1/me/student-verification" && init?.method === "POST") return Promise.resolve(jsonResponse({ success: true, cycle_year: 2027 }, 202));
      if (url === "/api/v1/me/finances") return Promise.resolve(jsonResponse({
        membership: {
          uid: "membership-uid",
          user_uid: "member-uid",
          username: "frontendtest",
          surname: "Demo",
          lastname: "Member",
          email: "frontendtest@example.invalid",
          email_confirmed: true,
          hs_email: "student@hs-albsig.de",
          hs_email_confirmed: true,
          status: "active",
          fee_category: "student",
          member_since: "2025-03-01",
          ended_at: null,
          special_rate_cents: null,
          special_rate_valid_until: null,
          balance_cents: balance,
        },
        pending_request: null,
        cycle_year: 2027,
        can_use_tally: true,
        products: [{ id: 1, uid: "product-uid", name: "Glasflaschen", price_cents: 250, is_active: true }],
        charges,
        payments: [],
        balance_cents: balance,
        payment_instructions: "IBAN wird vor Ort ausgehängt.",
        student_verification: { required: true, verified: false, email: "student@hs-albsig.de", verified_at: null },
      }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/finances");

    expect(await screen.findByText("Beitragsfrei", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Mitgliedsbeitrag 2027")).toBeInTheDocument();
    expect(screen.queryByText("Mitgliedsbeitrag 2027 (student)")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Bestätigungsmail senden" }));
    expect(await screen.findByText("Bestätigungsmail für den aktuellen Beitragszyklus wurde angefordert.")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Menge"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /Glasflaschen/ }));
    expect(await screen.findByText("Dein Eintrag wurde zum Tally hinzugefügt.")).toBeInTheDocument();
    const purchaseCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/me/finance/purchases" && init?.method === "POST");
    expect(purchaseCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-finance-member" }));
    expect(JSON.parse(String(purchaseCall?.[1]?.body))).toEqual({ item_id: 1, quantity: 2 });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/me/student-verification", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRFToken": "csrf-finance-member" }),
    }));
  });

  it("lets the Member role use Tally without a Finance membership", async () => {
    let bought = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "member-without-finance", csrf_token: "csrf-role-tally" }));
      if (url === "/api/v1/me/finance/purchases" && init?.method === "POST") {
        bought = true;
        return Promise.resolve(jsonResponse({ success: true, charge: { uid: "member-tally-charge" }, balance_cents: 350 }, 201));
      }
      if (url === "/api/v1/me/finances") return Promise.resolve(jsonResponse({
        membership: null,
        can_use_tally: true,
        pending_request: null,
        cycle_year: 2027,
        products: [{ id: 3, uid: "water-uid", name: "Wasser", price_cents: 350, is_active: true }],
        charges: [],
        payments: [],
        balance_cents: bought ? 350 : 0,
        payment_instructions: "",
      }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/me/finances");
    expect(await screen.findByRole("heading", { name: "Getränk eintragen." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deine Beitragsmitgliedschaft ist noch nicht eingerichtet." })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Wasser/ }));

    expect(await screen.findByText("Dein Eintrag wurde zum Tally hinzugefügt.")).toBeInTheDocument();
    const purchaseCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/me/finance/purchases" && init?.method === "POST");
    expect(JSON.parse(String(purchaseCall?.[1]?.body))).toEqual({ item_id: 3, quantity: 1 });
  });

  it("does not show Tally products for Sia-Alumni or guests", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "alumni", csrf_token: "csrf-no-tally" }));
      if (url === "/api/v1/me/finances") return Promise.resolve(jsonResponse({
        membership: null,
        can_use_tally: false,
        pending_request: null,
        cycle_year: 2027,
        products: [],
        charges: [],
        payments: [],
        balance_cents: 0,
        payment_instructions: "",
      }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    }));

    renderApp("/me/finances");

    expect(await screen.findByRole("heading", { name: "Deine Beitragsmitgliedschaft ist noch nicht eingerichtet." })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Getränk eintragen." })).not.toBeInTheDocument();
    expect(screen.queryByText("Glasflaschen")).not.toBeInTheDocument();
  });

  it("exposes the Finance tab only to finance admins and creates member records", async () => {
    const financeOverview = {
      memberships: [],
      available_users: [{ uid: "user-uid", username: "newmember", surname: "New", lastname: "Member", role: "Mitglied" }],
      requests: [],
      products: [],
      fee_rates: [
        { category: "full", annual_amount_cents: 5000 },
        { category: "reduced", annual_amount_cents: 2500 },
        { category: "student", annual_amount_cents: 2000 },
        { category: "training", annual_amount_cents: 2000 },
        { category: "exempt", annual_amount_cents: 0 },
      ],
      payment_instructions: "IBAN folgt.",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        can_admin_panel: true,
        can_manage_finances: true,
        csrf_token: "csrf-finance-admin",
      }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse(financeOverview));
      if (url === "/api/v1/manage/finance/memberships" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ success: true, membership: { uid: "membership-new" } }, 201));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");

    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    expect(await screen.findByRole("heading", { name: "Finanzen." })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Beitragsmitgliedschaft anlegen" }));
    expect(await screen.findByText("Beitragsmitgliedschaft wurde angelegt.")).toBeInTheDocument();
    const createCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/finance/memberships" && init?.method === "POST");
    expect(createCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-finance-admin" }));
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual(expect.objectContaining({ user_uid: "user-uid", fee_category: "student" }));
  });

  it("manually marks user-linked event tickets paid without creating a Finance membership", async () => {
    let paid = false;
    const ticket = () => ({
      registration_id: 505,
      event_id: 12,
      event_name: "Sommerfest",
      event_visibility: "public",
      event_date: "2027-06-12T18:00:00+02:00",
      registration_name: "Abendkasse",
      registration_visibility: "public",
      user_uid: "attendee-uid",
      username: "memberone",
      surname: "Mia",
      lastname: "Member",
      role: "Sia-Alumni",
      price_cents: null,
      price_known: false,
      paid,
      ledger_linked: false,
      valid: false,
      status: paid ? "paid" : "open",
      timestamp: "2027-06-01T12:00:00+02:00",
      created_by_username: "eventmanagerdemo",
      cancelled_at: null,
      cancel_reason: "",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        can_admin_panel: true,
        can_manage_finances: true,
        csrf_token: "csrf-event-ticket-finance",
      }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [], available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "",
      }));
      if (url === "/api/v1/manage/finance/event-tickets/status" && init?.method === "PUT") {
        paid = JSON.parse(String(init.body)).paid;
        return Promise.resolve(jsonResponse({ success: true, updated_count: 1 }));
      }
      if (url.startsWith("/api/v1/manage/finance/event-tickets")) {
        return Promise.resolve(jsonResponse({ tickets: [ticket()], open_amount_cents: 0, open_unlinked_count: paid ? 0 : 1 }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Eventtickets" }));
    expect(await screen.findByText("Altbestand · Preis nicht gespeichert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Mia Member Sommerfest auswählen" }));
    fireEvent.click(screen.getByRole("button", { name: "Ausgewählte als bezahlt markieren (1)" }));

    expect(await screen.findByText(/1 Ticket\(s\) wurden als bezahlt markiert/)).toBeInTheDocument();
    const statusCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/finance/event-tickets/status" && init?.method === "PUT");
    expect(JSON.parse(String(statusCall?.[1]?.body))).toEqual({
      registration_ids: [505],
      paid: true,
      note: "Manuell im Eventticket-Finanzbereich als bezahlt markiert",
    });
    expect(statusCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-event-ticket-finance" }));
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/finance/memberships", expect.anything());
  });

  it("proposes matching event charges after recording a payment and waits for admin confirmation", async () => {
    const user = {
      uid: "alumni-user-uid",
      username: "ticketguest",
      surname: "Toni",
      lastname: "Gast",
      role: "Sia-Alumni",
      email: "ticketguest@example.invalid",
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      membership_uid: null,
      membership_status: null,
      fee_category: null,
      balance_cents: 850,
      can_use_tally: false,
    };
    const charge = {
      uid: "event-charge-uid",
      kind: "event_ticket",
      name: "Sommerfest — Abendkasse",
      registration_id: 505,
      registration_name: "Abendkasse",
      event_name: "Sommerfest",
      event_date: "2027-06-12T18:00:00+02:00",
      fee_category: null,
      cycle_year: null,
      quantity: 1,
      unit_price_cents: 850,
      amount_cents: 850,
      due_date: null,
      status: "open",
      created_at: "2027-06-01T12:00:00+02:00",
      status_at: null,
      status_note: "",
    };
    let paid = false;
    let balance = 850;
    let payments: Array<Record<string, unknown>> = [];
    let paymentCount = 0;
    const account = () => ({
      user: { ...user, balance_cents: balance },
      membership: null,
      membership_history: [],
      charges: [{ ...charge, status: paid ? "paid" : "open" }],
      payments,
      balance_cents: balance,
      payment_instructions: "IBAN folgt.",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-user-ledger" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [],
        finance_users: [{ ...user, balance_cents: balance }],
        available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "IBAN folgt.",
      }));
      if (url === "/api/v1/manage/finance/users/alumni-user-uid/payments" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        paymentCount += 1;
        payments = [{ uid: `payment-uid-${paymentCount}`, amount_cents: body.amount_cents, method: body.method, reference: body.reference, note: body.note, received_at: body.received_at, voided_at: null, void_reason: "" }];
        balance -= body.amount_cents;
        return Promise.resolve(jsonResponse({
          success: true,
          payment: payments[0],
          balance_cents: balance,
          match_suggestion: { payment_amount_cents: 850, total_cents: 850, remainder_cents: 0, all_open_charges: true, charges: [charge] },
        }, 201));
      }
      if (url.endsWith(`/payments/payment-uid-${paymentCount}/confirm-charges`) && init?.method === "POST") {
        paid = true;
        return Promise.resolve(jsonResponse({ success: true, confirmed_count: 1, total_cents: 850, balance_cents: balance }));
      }
      if (url === "/api/v1/manage/finance/charges/event-charge-uid/status" && init?.method === "PUT") {
        paid = JSON.parse(String(init.body)).status === "paid";
        return Promise.resolve(jsonResponse({ success: true, charge: { ...charge, status: paid ? "paid" : "open" }, balance_cents: balance }));
      }
      if (url === "/api/v1/manage/finance/users/alumni-user-uid") return Promise.resolve(jsonResponse(account()));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Salden & Zahlungen" }));
    expect(await screen.findByText("Sommerfest — Abendkasse")).toBeInTheDocument();
    expect(screen.getByText("Nicht eingerichtet")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Betrag (€)"), { target: { value: "8.50" } });
    fireEvent.click(screen.getByRole("button", { name: "Zahlung verbuchen" }));
    expect(await screen.findByText("Zahlung wurde verbucht.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Als bezahlt markieren: Sommerfest — Abendkasse" })).toBeInTheDocument();
    expect(screen.getByText("Alle offenen Buchungen passen genau zum verfügbaren Guthaben.")).toBeInTheDocument();
    expect(paid).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Vorschlag verwerfen" }));
    expect(await screen.findByText("Vorschlag verworfen. Die offenen Buchungen bleiben unverändert.")).toBeInTheDocument();
    expect(paid).toBe(false);
    expect(screen.getByRole("button", { name: "Als bezahlt markieren: Sommerfest — Abendkasse" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Betrag (€)"), { target: { value: "8.50" } });
    fireEvent.click(screen.getByRole("button", { name: "Zahlung verbuchen" }));
    expect(await screen.findByText("Alle offenen Buchungen passen genau zum verfügbaren Guthaben.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag übernehmen" }));
    expect(await screen.findByText(/1 Buchung\(en\) über/)).toBeInTheDocument();
    expect(paid).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/finance/users/alumni-user-uid/payments/payment-uid-2/confirm-charges",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ charge_uids: ["event-charge-uid"] }) }),
    );
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/finance/memberships", expect.anything());
  });

  it("shows an event charge for a non-Finance-member and keeps charge status separate from recorded payment", async () => {
    let paid = false;
    let balance = 850;
    let payments: Array<Record<string, unknown>> = [];
    const user = {
      uid: "alumni-user-uid",
      username: "ticketguest",
      surname: "Toni",
      lastname: "Gast",
      role: "Sia-Alumni",
      email: "ticketguest@example.invalid",
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      membership_uid: null,
      membership_status: null,
      fee_category: null,
      balance_cents: balance,
      can_use_tally: false,
    };
    const charge = () => ({
      uid: "event-charge-uid",
      kind: "event_ticket",
      name: "Sommerfest — Abendkasse",
      registration_id: 505,
      registration_name: "Abendkasse",
      event_name: "Sommerfest",
      event_date: "2027-06-12T18:00:00+02:00",
      fee_category: null,
      cycle_year: null,
      quantity: 1,
      unit_price_cents: 850,
      amount_cents: 850,
      due_date: null,
      status: paid ? "paid" : "open",
      created_at: "2027-06-01T12:00:00+02:00",
      status_at: null,
      status_note: "",
    });
    const account = () => ({
      user: { ...user, balance_cents: balance },
      membership: null,
      membership_history: [],
      charges: [charge()],
      payments,
      balance_cents: balance,
      payment_instructions: "IBAN folgt.",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-user-ledger" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [],
        finance_users: [{ ...user, balance_cents: balance }],
        available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "IBAN folgt.",
      }));
      if (url === "/api/v1/manage/finance/users/alumni-user-uid/payments" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        payments = [{ uid: "payment-uid", amount_cents: body.amount_cents, method: body.method, reference: body.reference, note: body.note, received_at: body.received_at, voided_at: null, void_reason: "" }];
        balance -= body.amount_cents;
        return Promise.resolve(jsonResponse({
          success: true,
          payment: payments[0],
          balance_cents: balance,
          match_suggestion: { payment_amount_cents: 850, total_cents: 0, remainder_cents: 850, all_open_charges: false, charges: [] },
        }, 201));
      }
      if (url === "/api/v1/manage/finance/charges/event-charge-uid/status" && init?.method === "PUT") {
        paid = JSON.parse(String(init.body)).status === "paid";
        return Promise.resolve(jsonResponse({ success: true, charge: charge(), balance_cents: balance }));
      }
      if (url === "/api/v1/manage/finance/users/alumni-user-uid") return Promise.resolve(jsonResponse(account()));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Salden & Zahlungen" }));
    expect(await screen.findByText("Sommerfest — Abendkasse")).toBeInTheDocument();
    expect(screen.getByText("Nicht eingerichtet")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Betrag (€)"), { target: { value: "8.50" } });
    fireEvent.click(screen.getByRole("button", { name: "Zahlung verbuchen" }));

    expect(await screen.findByText("Zahlung wurde verbucht.")).toBeInTheDocument();
    expect(await screen.findByText(/Keine vollständige Buchung passt in das verfügbare Guthaben/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Als bezahlt markieren: Sommerfest — Abendkasse" })).toBeInTheDocument();
    expect(paid).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/manage/finance/users/alumni-user-uid/payments", expect.objectContaining({ method: "POST" }));

    fireEvent.click(screen.getByRole("button", { name: "Als bezahlt markieren: Sommerfest — Abendkasse" }));
    expect(await screen.findByText("Als bezahlt markiert")).toBeInTheDocument();
    expect(paid).toBe(true);
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/finance/memberships", expect.anything());
  });

  it("warns that a recorded payment cannot be restored before voiding it", async () => {
    const user = {
      uid: "void-user-uid",
      username: "voidmember",
      surname: "Demo",
      lastname: "Zahlung",
      role: "Mitglied",
      email: "voidmember@demo.invalid",
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      membership_uid: null,
      membership_status: null,
      fee_category: null,
      balance_cents: 1200,
      can_use_tally: true,
    };
    let voided = false;
    let voidBody: unknown;
    const payment = () => ({
      uid: "payment-to-void",
      amount_cents: 1200,
      method: "bank_transfer" as const,
      reference: "DEMO-DOUBLE-ENTRY",
      note: "",
      received_at: "2027-01-10T10:00:00+01:00",
      voided_at: voided ? "2027-01-11T10:00:00+01:00" : null,
      void_reason: voided ? "Doppelt verbucht" : "",
      allocated_cents: 0,
      unallocated_cents: voided ? 0 : 1200,
      allocations: [],
    });
    const account = () => ({
      user: { ...user, balance_cents: voided ? 0 : 1200 },
      membership: null,
      membership_history: [],
      charges: [],
      payments: [payment()],
      charge_adjustments: [],
      balance_cents: voided ? 0 : 1200,
      unallocated_credit_cents: voided ? 0 : 1200,
      allocation_suggestion: { payment_amount_cents: 0, available_amount_cents: 0, total_cents: 0, remainder_cents: 0, all_open_charges: false, charges: [] },
      payment_instructions: "",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-void-payment" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [],
        finance_users: [user],
        available_users: [],
        requests: [],
        products: [],
        fee_rates: [],
        payment_instructions: "",
      }));
      if (url === "/api/v1/manage/finance/payments/payment-to-void/void" && init?.method === "POST") {
        voidBody = JSON.parse(String(init.body));
        voided = true;
        return Promise.resolve(jsonResponse({ success: true, payment: payment(), balance_cents: 0 }));
      }
      if (url === "/api/v1/manage/finance/users/void-user-uid") return Promise.resolve(jsonResponse(account()));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    const confirmMock = vi.fn().mockReturnValue(false);
    const promptMock = vi.fn().mockReturnValue("Doppelt verbucht");
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", confirmMock);
    vi.stubGlobal("prompt", promptMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Salden & Zahlungen" }));
    const voidButton = await screen.findByRole("button", { name: "Zahlung stornieren" });

    fireEvent.click(voidButton);
    expect(confirmMock).toHaveBeenCalledWith(expect.stringContaining("nicht rückgängig gemacht werden"));
    expect(promptMock).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/finance/payments/payment-to-void/void", expect.anything());

    confirmMock.mockReturnValue(true);
    fireEvent.click(voidButton);
    expect(await screen.findByText("Zahlung wurde storniert und aus dem Saldo entfernt.")).toBeInTheDocument();
    expect(promptMock).toHaveBeenCalledTimes(1);
    expect(voidBody).toEqual({ reason: "Doppelt verbucht" });
  });

  it("archives a billing run with a reason and allows a replacement run", async () => {
    let runStatus: "issued" | "voided" = "issued";
    let createdReplacement = false;
    const activeRun = {
      id: 7,
      cycle_year: 2027,
      period: "march" as const,
      run_number: 1,
      status: "issued" as const,
      due_date: "2027-03-01",
      created_at: "2026-12-31T10:00:00+01:00",
      created_by_username: "eventmanagerdemo",
      voided_at: null,
      voided_by_username: null,
      void_reason: "",
      charge_count: 1,
      open_charge_count: 1,
      issued_amount_cents: 2000,
      open_amount_cents: 2000,
      cancelled_amount_cents: 0,
      affected_members: [{ membership_uid: "membership-uid", username: "Mia Member", run_amount_cents: 2000, current_balance_cents: 2000, balance_after_void_cents: 0 }],
    };
    const voidedRun = { ...activeRun, status: "voided" as const, voided_at: "2026-12-31T11:00:00+01:00", voided_by_username: "eventmanagerdemo", void_reason: "Testlauf versehentlich gestartet", open_charge_count: 0, open_amount_cents: 0, cancelled_amount_cents: 2000, affected_members: [] };
    const preview = () => ({
      cycle_year: 2027,
      period: "march" as const,
      due_date: "2027-03-01",
      run_created: runStatus === "issued",
      active_run: runStatus === "issued" ? activeRun : null,
      runs: [runStatus === "issued" ? activeRun : voidedRun],
      members: [{
        membership: { uid: "membership-uid", user_uid: "member-uid", username: "Mia Member", surname: "Mia", lastname: "Member", email: "", email_confirmed: false, hs_email: "", hs_email_confirmed: false, status: "active", fee_category: "full", member_since: "2024-03-01", ended_at: null, special_rate_cents: null, special_rate_valid_until: null, balance_cents: 2000 },
        cycle_year: 2027,
        due_date: "2027-03-01",
        amount_cents: 2000,
        effective_category: "full",
        reason: "Regulärer Jahresbeitrag",
        needs_admin_review: false,
        already_billed: runStatus === "issued",
        existing_status: runStatus === "issued" ? "open" : null,
        existing_amount_cents: runStatus === "issued" ? 2000 : null,
        existing_due_date: runStatus === "issued" ? "2027-03-01" : null,
        existing_period: runStatus === "issued" ? "march" : null,
        not_eligible: false,
      }, {
        membership: { uid: "summer-membership-uid", user_uid: "summer-user-uid", username: "summerspring", surname: "Summer", lastname: "Joiner", email: "", email_confirmed: false, hs_email: "", hs_email_confirmed: true, status: "active", fee_category: "student", member_since: "2027-05-15", ended_at: null, special_rate_cents: null, special_rate_valid_until: null, balance_cents: 0 },
        cycle_year: 2027,
        due_date: "2027-03-01",
        amount_cents: 0,
        effective_category: "student",
        reason: "Erster Studierendenbeitrag fällt nach dem Sommersemester in den Septemberlauf",
        needs_admin_review: false,
        already_billed: false,
        existing_status: null,
        not_eligible: true,
      }],
      total_to_issue_cents: runStatus === "issued" ? 0 : 2000,
      charge_count: runStatus === "issued" ? 0 : 1,
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-run-void" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({ memberships: [], available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "" }));
      if (url.startsWith("/api/v1/manage/finance/billing-preview/")) return Promise.resolve(jsonResponse(preview()));
      if (url === "/api/v1/manage/finance/billing-runs/7/void" && init?.method === "POST") {
        runStatus = "voided";
        return Promise.resolve(jsonResponse({ success: true, run: voidedRun, voided_charge_count: 1, affected_members: [activeRun.affected_members[0]] }));
      }
      if (url === "/api/v1/manage/finance/billing-runs" && init?.method === "POST") {
        createdReplacement = true;
        runStatus = "issued";
        return Promise.resolve(jsonResponse({ success: true, cycle_year: 2027, period: "march", run_number: 2, due_date: "2027-03-01", created_count: 1, total_cents: 2000 }, 201));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Jahresbeiträge" }));
    expect(await screen.findByText("Nicht in diesem Lauf")).toBeInTheDocument();
    expect(screen.getByText("Bereits im März-Lauf erstellt")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Beitragslauf stornieren" }));
    fireEvent.change(screen.getByLabelText("Grund für die Stornierung"), { target: { value: "Testlauf versehentlich gestartet" } });
    fireEvent.click(screen.getByRole("button", { name: "Lauf stornieren" }));

    expect(await screen.findByText(/Beitragslauf #1 storniert/)).toBeInTheDocument();
    expect(await screen.findByText(/Testlauf versehentlich gestartet/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Beitragslauf #2 erstellen" }));
    expect(await screen.findByText(/März-Beitragslauf 2027: 1 Buchungen/)).toBeInTheDocument();
    expect(createdReplacement).toBe(true);
    const voidCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/finance/billing-runs/7/void" && init?.method === "POST");
    expect(JSON.parse(String(voidCall?.[1]?.body))).toEqual({ reason: "Testlauf versehentlich gestartet" });
  });

  it("lets an admin directly change a member fee category with an audit note", async () => {
    const membership = {
      uid: "membership-uid",
      user_uid: "user-uid",
      username: "member-one",
      surname: "Mia",
      lastname: "Member",
      email: "member@example.invalid",
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      status: "active",
      fee_category: "student",
      member_since: "2025-03-01",
      ended_at: null,
      special_rate_cents: null,
      special_rate_valid_until: null,
      balance_cents: 0,
    };
    let changedMembership = membership;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-fee-edit" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [changedMembership], available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "",
      }));
      if (url === "/api/v1/manage/finance/memberships/membership-uid" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        changedMembership = { ...changedMembership, fee_category: body.fee_category };
        return Promise.resolve(jsonResponse({
          success: true,
          membership: changedMembership,
          fee_adjustments: [{ cycle_year: 2026, from_amount_cents: 2000, to_amount_cents: 3500, from_fee_category: "student", to_fee_category: "full", due_date: "2026-03-01" }],
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");

    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("button", { name: "Beitragsklasse" }));
    fireEvent.change(screen.getByLabelText("Beitragsklasse"), { target: { value: "full" } });
    fireEvent.change(screen.getByLabelText("Änderungsnotiz"), { target: { value: "Alumni-Nachweis geprüft" } });
    fireEvent.click(screen.getByRole("button", { name: "Beitragsklasse speichern" }));

    expect(await screen.findByText(/Beitragskategorie wurde geändert/)).toBeInTheDocument();
    expect(screen.getByText(/Jahresbeiträge angepasst/)).toHaveTextContent("Student:in → Vollbetrag");
    expect(screen.getByText(/Jahresbeiträge angepasst/)).toHaveTextContent("20,00");
    expect(screen.getByText(/Jahresbeiträge angepasst/)).toHaveTextContent("35,00");
    const updateCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/finance/memberships/membership-uid" && init?.method === "PUT");
    expect(updateCall?.[1]?.headers).toEqual(expect.objectContaining({ "X-CSRFToken": "csrf-fee-edit" }));
    expect(JSON.parse(String(updateCall?.[1]?.body))).toEqual(expect.objectContaining({ fee_category: "full", note: "Alumni-Nachweis geprüft" }));
  });

  it("allocates available payment credit to selected open Tally charges", async () => {
    const membership = {
      uid: "membership-uid",
      user_uid: "user-uid",
      username: "tallymember",
      role: "Vereinsmitglied",
      surname: "Tally",
      lastname: "Member",
      email: "tally@example.invalid",
      email_confirmed: true,
      hs_email: "tally@uni.invalid",
      hs_email_confirmed: true,
      status: "active",
      fee_category: "student",
      member_since: "2025-03-01",
      ended_at: null,
      special_rate_cents: null,
      special_rate_valid_until: null,
      balance_cents: 2000,
    };
    let charges = [
      { uid: "drink-one", kind: "drink", name: "Glasflaschen", fee_category: null, cycle_year: null, quantity: 1, unit_price_cents: 250, amount_cents: 250, allocated_cents: 0, remaining_cents: 250, due_date: null, status: "open", created_at: "2026-01-01T12:00:00+01:00", status_at: null, status_note: "" },
      { uid: "drink-two", kind: "drink", name: "Longdrinks", fee_category: null, cycle_year: null, quantity: 1, unit_price_cents: 500, amount_cents: 500, allocated_cents: 0, remaining_cents: 500, due_date: null, status: "open", created_at: "2026-01-02T12:00:00+01:00", status_at: null, status_note: "" },
      { uid: "dues-one", kind: "membership", name: "Mitgliedsbeitrag 2026", fee_category: "student", cycle_year: 2026, quantity: 1, unit_price_cents: 2000, amount_cents: 2000, allocated_cents: 0, remaining_cents: 2000, due_date: "2026-03-01", status: "open", created_at: "2026-03-01T12:00:00+01:00", status_at: null, status_note: "" },
    ];
    let unallocatedCreditCents = 750;
    let payments = [{ uid: "payment-one", amount_cents: 750, method: "cash", reference: "", note: "", received_at: "2026-03-01T12:00:00+01:00", voided_at: null, void_reason: "", allocated_cents: 0, unallocated_cents: 750, allocations: [] }];
    const allocationSuggestion = () => {
      const chargesToAllocate = charges.filter((charge) => charge.kind === "drink" && charge.remaining_cents > 0);
      return {
        payment_amount_cents: 0,
        available_amount_cents: unallocatedCreditCents,
        total_cents: chargesToAllocate.reduce((total, charge) => total + charge.remaining_cents, 0),
        remainder_cents: Math.max(0, unallocatedCreditCents - chargesToAllocate.reduce((total, charge) => total + charge.remaining_cents, 0)),
        all_open_charges: chargesToAllocate.length === charges.filter((charge) => charge.kind === "drink").length,
        charges: chargesToAllocate,
      };
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-bulk-tally" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({
        memberships: [membership], available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "Zahlungsdaten",
      }));
      if (url === "/api/v1/manage/finance/users/user-uid/allocations/confirm" && init?.method === "POST") {
        const ids = (JSON.parse(String(init.body)) as { charge_uids: string[] }).charge_uids;
        charges = charges.map((charge) => ids.includes(charge.uid)
          ? { ...charge, status: "paid", allocated_cents: charge.amount_cents, remaining_cents: 0 }
          : charge);
        unallocatedCreditCents = 0;
        payments = payments.map((payment) => ({ ...payment, allocated_cents: 750, unallocated_cents: 0 }));
        return Promise.resolve(jsonResponse({ success: true, confirmed_count: ids.length, total_cents: 750, balance_cents: 2000, unallocated_credit_cents: 0 }));
      }
      if (url === "/api/v1/manage/finance/users/user-uid") {
        return Promise.resolve(jsonResponse({
          user: { uid: "user-uid", username: "tallymember", surname: "Tally", lastname: "Member", role: "Vereinsmitglied", email: "tally@example.invalid", email_confirmed: true, hs_email: "tally@uni.invalid", hs_email_confirmed: true, membership_uid: "membership-uid", membership_status: "active", fee_category: "student", balance_cents: 2000, can_use_tally: true },
          membership, membership_history: [], charges, payments, balance_cents: 2000, unallocated_credit_cents: unallocatedCreditCents, allocation_suggestion: allocationSuggestion(), payment_instructions: "Zahlungsdaten",
        }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");

    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Salden & Zahlungen" }));

    expect(screen.getByRole("option", { name: /Tally Member \(@tallymember · Vereinsmitglied\)/ })).toBeInTheDocument();
    expect(await screen.findByText("Tally Member (@tallymember)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Informationen zu Tally Member" }));
    const memberInfo = screen.getByRole("dialog");
    expect(memberInfo).toHaveTextContent("Vereinsmitglied");
    expect(memberInfo).toHaveTextContent("tally@example.invalid");
    expect(memberInfo).toHaveTextContent("tally@uni.invalid");
    fireEvent.click(screen.getByRole("button", { name: "Schließen" }));

    expect(screen.queryByRole("button", { name: "Als bezahlt markieren: Glasflaschen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Alle offenen Tally-Einträge als bezahlt markieren/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Vorschlag aus vorhandenem Guthaben öffnen/ }));
    expect(await screen.findByRole("button", { name: "Vorschlag übernehmen" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Vorschlag übernehmen" }));
    expect(await screen.findByText(/2 Buchung\(en\) über/)).toBeInTheDocument();
    const allocationCall = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/v1/manage/finance/users/user-uid/allocations/confirm" && init?.method === "POST");
    expect(JSON.parse(String(allocationCall?.[1]?.body))).toEqual({ charge_uids: ["drink-one", "drink-two"] });
    expect(allocationCall?.[1]).toEqual(expect.objectContaining({ headers: expect.objectContaining({ "X-CSRFToken": "csrf-bulk-tally" }) }));
    expect(charges.find((charge) => charge.kind === "membership")?.status).toBe("open");
    expect(charges.find((charge) => charge.uid === "drink-one")?.status).toBe("paid");
    expect(charges.find((charge) => charge.uid === "drink-two")?.status).toBe("paid");
  });

  it("loads, edits, and deletes admin records in the tabbed dashboard", async () => {
    let user: AdminUser = {
      id: 55,
      uid: "member-uid",
      username: "member-one",
      role: "Mitglied",
      surname: "Mia",
      lastname: "Member",
      email: "member@example.com",
      email_confirmed: true,
      hs_email: "",
      hs_email_confirmed: false,
      street: "",
      street_no: "",
      city: "",
      postalcode: "",
      register_date: "2026-01-01",
      last_login: "2026-06-01",
      last_updated: "2026-06-01",
    };
    let contacts: AdminContact[] = [{
      uid: "contact-uid",
      category: "feedback",
      surname: "Sam",
      lastname: "Test",
      email: "sam@example.com",
      message: "Danke für die schönen Events im Plan B.",
      creation: "2026-06-10 14:00",
      handled_at: null,
      handled_by_username: null,
      is_handled: false,
    }];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({
        authenticated: true,
        username: "eventmanagerdemo",
        needs_email_confirmation: true,
        can_admin_panel: true,
        can_manage_users: true,
        can_update_users: true,
        can_delete_users: true,
        can_manage_contacts: true,
        can_delete_contacts: true,
        csrf_token: "csrf-admin-panel",
      }));
      if (url === "/api/v1/manage/users/member-uid" && init?.method === "PUT") {
        const body = new URLSearchParams(String(init.body));
        user = { ...user, surname: body.get("surname") || "" };
        return Promise.resolve(jsonResponse({ success: true, user, verification_warning: false }));
      }
      if (url === "/api/v1/manage/users") return Promise.resolve(jsonResponse({ users: [user], roles: ["Mitglied", "Gast"] }));
      if (url === "/api/v1/manage/contacts/contact-uid" && init?.method === "PUT") {
        const handled = (JSON.parse(String(init.body)) as { handled: boolean }).handled;
        contacts = contacts.map((contact) => ({
          ...contact,
          is_handled: handled,
          handled_at: handled ? "2026-06-11 10:00" : null,
          handled_by_username: handled ? "eventmanagerdemo" : null,
        }));
        return Promise.resolve(jsonResponse({ success: true, contact: contacts[0] }));
      }
      if (url === "/api/v1/manage/contacts/contact-uid" && init?.method === "DELETE") {
        contacts = [];
        return Promise.resolve(jsonResponse({ success: true }));
      }
      if (url === "/api/v1/manage/contacts") return Promise.resolve(jsonResponse({ contacts }));
      if (url === "/api/v1/manage/role-requests") return Promise.resolve(jsonResponse({ requests: [] }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn(() => true));

    renderApp("/admin");

    expect(await screen.findByRole("heading", { name: "Benutzerverwaltung." })).toBeInTheDocument();
    expect(document.querySelector(".todo-indicator")).toHaveAttribute("title", "E-Mail-Bestätigung ausstehend");
    expect(await screen.findByText("member-one")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bearbeiten" }));
    fireEvent.change(screen.getByLabelText("Vorname"), { target: { value: "Mira" } });
    fireEvent.click(screen.getByRole("button", { name: "Nutzerdaten speichern" }));
    expect(await screen.findByText("Nutzerdaten gespeichert.")).toBeInTheDocument();
    expect(screen.getByText("Mira Member")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Kontaktanfragen" }));
    expect(await screen.findByText("Danke für die schönen Events im Plan B.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Kontaktanfragen" }).querySelector(".admin-tab-indicator")).toHaveTextContent("1");
    fireEvent.click(screen.getByRole("button", { name: "Als erledigt markieren" }));
    expect(await screen.findByText("Anfrage als erledigt markiert.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Kontaktanfragen" }).querySelector(".admin-tab-indicator")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Erledigt" }));
    expect(await screen.findByText("Erledigt von eventmanagerdemo")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Wieder öffnen" }));
    expect(await screen.findByText("Es gibt keine erledigten Kontaktanfragen.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Alle" }));
    fireEvent.click(screen.getByRole("button", { name: "Löschen" }));
    expect(await screen.findByText("Es gibt keine Kontaktanfragen.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/contacts/contact-uid",
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-admin-panel" }),
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/contacts/contact-uid",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "X-CSRFToken": "csrf-admin-panel" }),
      }),
    );
  });

  it("saves the shared student email draft, tests it, reviews recipients, and requires final confirmation", async () => {
    let draft = {
      kind: "student_verification",
      subject_template: "Studentenstatus für {{cycle_year}} bestätigen",
      body_template: "Hallo {{name}}\n{{verification_link}}",
      minimum_balance_cents: 0,
      cycle_year: 2027,
      selected_recipient_keys: null as string[] | null,
      version: 1,
      updated_by_username: "eventmanagerdemo",
      updated_at: "2026-10-01T12:00:00+02:00",
    };
    const candidate = (key: string, username: string, displayName: string) => ({
      key,
      user_uid: `user-${username}`,
      membership_uid: key.replace("membership:", ""),
      username,
      display_name: displayName,
      email: `${username}@uni.example.invalid`,
      email_source: "hs_email",
      balance_cents: null,
      can_select: true,
      default_selected: true,
      selected: draft.selected_recipient_keys === null || draft.selected_recipient_keys.includes(key),
      reasons: [],
    });
    const candidates = () => [
      candidate("membership:membership-one", "memberone", "Mia Member"),
      candidate("membership:membership-two", "membertwo", "Max Member"),
    ];
    const preview = () => {
      const recipientCandidates = candidates();
      return {
        kind: "student_verification",
        cycle_year: 2027,
        draft_version: draft.version,
        selected_recipient_keys: draft.selected_recipient_keys,
        selection_is_saved: draft.selected_recipient_keys !== null,
        scope_user_uid: null,
        summary: { selected: recipientCandidates.filter((item) => item.selected).length, active_students: 2, already_verified: 0, cooldown: 0, missing_hs_email: 0 },
        candidates: recipientCandidates,
        draft,
        mail_test_email: "admin-test@example.invalid",
      };
    };
    const campaigns: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-mail-draft" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse({ memberships: [], finance_users: [], available_users: [], requests: [], products: [], fee_rates: [], payment_instructions: "", mail_test_email: "admin-test@example.invalid" }));
      if (url.startsWith("/api/v1/manage/finance/billing-preview/")) return Promise.resolve(jsonResponse({
        cycle_year: 2027, period: "march", due_date: "2027-03-01", run_created: false, active_run: null, runs: [], members: [], total_to_issue_cents: 0, charge_count: 0,
      }));
      if (url === "/api/v1/manage/finance/mail-drafts/student_verification" && init?.method === "GET") {
        return Promise.resolve(jsonResponse({ draft, mail_test_email: "admin-test@example.invalid" }));
      }
      if (url === "/api/v1/manage/finance/mail-drafts/student_verification" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as typeof draft;
        draft = { ...draft, ...body, version: draft.version + 1, updated_at: "2026-10-13T12:00:00+02:00" };
        return Promise.resolve(jsonResponse({ success: true, draft }));
      }
      if (url === "/api/v1/manage/finance/mail-drafts/student_verification/preview" && init?.method === "POST") {
        return Promise.resolve(jsonResponse(preview()));
      }
      if (url === "/api/v1/manage/finance/mail-drafts/student_verification/test" && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ success: true, campaign_uid: "test-campaign-uid", recipient_email: "admin-test@example.invalid" }, 202));
      }
      if (url === "/api/v1/manage/finance/mail-drafts/student_verification/send" && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { selected_recipient_keys: string[] };
        campaigns.push({
          uid: "campaign-uid",
          kind: "student_verification",
          source: "admin",
          test_only: false,
          cycle_year: 2027,
          minimum_balance_cents: null,
          subject_template: draft.subject_template,
          body_template: draft.body_template,
          created_by_username: "eventmanagerdemo",
          created_at: "2026-10-13T12:00:00+02:00",
          completed_at: null,
          status: "sending",
          counts: { selected: body.selected_recipient_keys.length, queued: body.selected_recipient_keys.length },
          recipient_status_counts: { queued: body.selected_recipient_keys.length },
          recipient_count: body.selected_recipient_keys.length,
          request_body: body,
        });
        return Promise.resolve(jsonResponse({ success: true, campaign_uid: "campaign-uid", selected: body.selected_recipient_keys.length, counts: { selected: body.selected_recipient_keys.length } }, 202));
      }
      if (url === "/api/v1/manage/finance/mail-campaigns?kind=student_verification") return Promise.resolve(jsonResponse({ campaigns }));
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Jahresbeiträge" }));
    fireEvent.click(await screen.findByRole("button", { name: "Studentenbestätigungen vorbereiten" }));
    expect(await screen.findByText("admin-test@example.invalid")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Betreff"), { target: { value: "Neue Bestätigung für {{cycle_year}}" } });
    fireEvent.click(screen.getByRole("button", { name: "Testmail senden" }));
    expect(await screen.findByText(/Testmail wurde an admin-test@example.invalid zur Übermittlung eingereiht/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/finance/mail-drafts/student_verification/test",
      expect.objectContaining({ method: "POST", headers: expect.objectContaining({ "X-CSRFToken": "csrf-mail-draft" }) }),
    );

    fireEvent.click(await screen.findByRole("button", { name: "Empfänger:innen laden" }));
    expect(await screen.findByText("Mia Member")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manage/finance/mail-drafts/student_verification/preview",
      expect.objectContaining({ method: "POST", headers: expect.objectContaining({ "X-CSRFToken": "csrf-mail-draft" }) }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Mia Member auswählen" }));
    fireEvent.click(screen.getByRole("button", { name: "Entwurf speichern" }));
    expect(await screen.findByText("Gemeinsamer Entwurf gespeichert.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Versand prüfen · 1" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("1 E-Mail(s) versenden?");
    expect(fetchMock).not.toHaveBeenCalledWith("/api/v1/manage/finance/mail-drafts/student_verification/send", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Jetzt an 1 senden" }));

    expect(await screen.findByText(/Studentenbestätigung: 1 Mail\(s\) wurden zur Übermittlung eingereiht/)).toBeInTheDocument();
    expect(campaigns).toHaveLength(1);
    expect((campaigns[0].request_body as { selected_recipient_keys: string[] }).selected_recipient_keys).toEqual(["membership:membership-two"]);
  });

  it("saves the configured finance test email address", async () => {
    let savedSettings: Record<string, unknown> | null = null;
    const financeOverview = {
      memberships: [],
      finance_users: [],
      available_users: [],
      requests: [],
      products: [],
      fee_rates: [],
      payment_instructions: "IBAN folgt.",
      mail_test_email: "",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-mail-settings" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse(financeOverview));
      if (url === "/api/v1/manage/finance/settings" && init?.method === "PUT") {
        savedSettings = JSON.parse(String(init.body));
        return Promise.resolve(jsonResponse({ success: true, ...savedSettings }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Salden & Zahlungen" }));
    fireEvent.change(screen.getByLabelText("Konfigurierte Test-E-Mail-Adresse"), { target: { value: "finance-test@example.invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "Zahlungs- und Testinformationen speichern" }));

    expect(await screen.findByText("Zahlungsinformationen und Testadresse gespeichert.")).toBeInTheDocument();
    expect(savedSettings).toEqual({ payment_instructions: "IBAN folgt.", mail_test_email: "finance-test@example.invalid" });
  });

  it("shows the contribution-order categories and saves annual rates", async () => {
    let fullRatePayload: Record<string, unknown> | null = null;
    const overview = {
      memberships: [],
      finance_users: [],
      available_users: [],
      requests: [],
      products: [],
      fee_rates: [
        { category: "full", annual_amount_cents: 5000 },
        { category: "reduced", annual_amount_cents: 2500 },
        { category: "student", annual_amount_cents: 2000 },
        { category: "training", annual_amount_cents: 2000 },
        { category: "exempt", annual_amount_cents: 0 },
      ],
      payment_instructions: "",
      mail_test_email: "",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/session") return Promise.resolve(jsonResponse({ authenticated: true, username: "eventmanagerdemo", can_admin_panel: true, can_manage_finances: true, csrf_token: "csrf-fee-rules" }));
      if (url === "/api/v1/manage/finance") return Promise.resolve(jsonResponse(overview));
      if (url.startsWith("/api/v1/manage/finance/billing-preview/")) return Promise.resolve(jsonResponse({
        cycle_year: 2027, period: "march", due_date: "2027-03-01", run_created: false, active_run: null, runs: [], members: [], total_to_issue_cents: 0, charge_count: 0,
      }));
      if (url === "/api/v1/manage/finance/rates/full" && init?.method === "PUT") {
        fullRatePayload = JSON.parse(String(init.body));
        return Promise.resolve(jsonResponse({ success: true, rate: { category: "full", annual_amount_cents: 5500 } }));
      }
      return Promise.resolve(new Response("Not found", { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/admin");
    fireEvent.click(await screen.findByRole("tab", { name: "Finanzen" }));
    fireEvent.click(await screen.findByRole("tab", { name: "Jahresbeiträge" }));
    expect(screen.getByText("Vollbetrag")).toBeInTheDocument();
    expect(screen.getByText("Ermäßigt")).toBeInTheDocument();
    expect(screen.getByText("In Ausbildung")).toBeInTheDocument();
    expect(screen.getByText("Befreit")).toBeInTheDocument();
    expect(screen.queryByText(/Jahreszyklus freistellen/)).not.toBeInTheDocument();
    const rateRows = document.querySelectorAll(".finance-rate-row");
    fireEvent.change(rateRows[0].querySelector("input[type='number']") as HTMLInputElement, { target: { value: "55.00" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);

    await waitFor(() => expect(fullRatePayload).not.toBeNull());
    expect(fullRatePayload).toEqual({ annual_amount_cents: 5500 });
  });
});
