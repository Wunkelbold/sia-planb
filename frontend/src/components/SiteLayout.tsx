import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { getCurrentSession } from "../api/events";
import { CalendarSubscribeButton } from "./CalendarSubscribeButton";

export function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const sessionQuery = useQuery({
    queryKey: ["current-session"],
    queryFn: getCurrentSession,
  });

  return (
    <header className="site-header">
      <Link aria-label="SIA – Gemeinsam mehr erleben" className="brand" to="/">
        <span aria-hidden="true" className="brand__wordmark">SIA</span>
        <span className="brand__slogan">Gemeinsam mehr erleben.</span>
      </Link>
      <button
        aria-controls="primary-navigation"
        aria-expanded={menuOpen}
        aria-label={menuOpen ? "Menü schließen" : "Menü öffnen"}
        className="mobile-nav-toggle"
        onClick={() => setMenuOpen((open) => !open)}
        type="button"
      >
        <span />
        <span />
        <span />
      </button>
      <nav aria-label="Hauptnavigation" className={`header-nav${menuOpen ? " header-nav--open" : ""}`} id="primary-navigation">
        <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/events">Events</Link>
        <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/verein">Verein</Link>
        <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/location">Location</Link>
        <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/getraenkekarte">Getränke</Link>
        <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/contact">Kontakt</Link>
        {sessionQuery.data?.authenticated && sessionQuery.data.can_scan_tickets && (
          <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/scanner">Scanner</Link>
        )}
        {sessionQuery.data?.authenticated && sessionQuery.data.can_admin_panel && (
          <Link className="header-nav__link" onClick={() => setMenuOpen(false)} to="/admin">Admintool</Link>
        )}
        <details className="account-dropdown">
          <summary>Konto</summary>
          <div className="account-dropdown__menu">
            {sessionQuery.data?.authenticated ? (
              <>
                <Link onClick={() => setMenuOpen(false)} to="/me/profile">Profil{sessionQuery.data.needs_email_confirmation && <span aria-hidden="true" className="todo-indicator" title="E-Mail-Bestätigung ausstehend">!</span>}</Link>
                <Link onClick={() => setMenuOpen(false)} to="/me/registrations">Tickets</Link>
                <Link onClick={() => setMenuOpen(false)} to="/me/commitments">Meine Einsätze</Link>
                <Link onClick={() => setMenuOpen(false)} to="/me/finances">{sessionQuery.data.can_use_tally ? "Finanzen & Tally" : "Finanzen"}</Link>
                <a href="/logout">Abmelden</a>
              </>
            ) : sessionQuery.data && !sessionQuery.data.authenticated ? (
              <>
                <Link onClick={() => setMenuOpen(false)} to="/login">Anmelden</Link>
                <Link onClick={() => setMenuOpen(false)} to="/register">Registrieren</Link>
              </>
            ) : <span className="account-dropdown__loading">Konto wird geladen …</span>}
          </div>
        </details>
        <CalendarSubscribeButton className="calendar-link">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <rect height="17" rx="2" width="18" x="3" y="5" />
            <path d="M16 3v4M8 3v4M3 10h18" />
          </svg>
          <span>Kalender abonnieren</span>
        </CalendarSubscribeButton>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <Link aria-label="SIA – Gemeinsam mehr erleben" className="brand brand--footer" to="/">
        <span aria-hidden="true" className="brand__wordmark">SIA</span>
        <span className="brand__slogan">Gemeinsam mehr erleben.</span>
      </Link>
      <p>Studenteninitiative Albstadt e.V.</p>
      <nav aria-label="Rechtliche Informationen" className="site-footer__links">
        <Link to="/datenschutz">Datenschutz</Link>
        <Link to="/impressum">Impressum</Link>
        <a href="https://sia-planb.de" rel="noreferrer" target="_blank">sia-planb.de <span aria-hidden="true">↗</span></a>
      </nav>
    </footer>
  );
}
