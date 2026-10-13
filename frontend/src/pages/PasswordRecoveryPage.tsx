import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { confirmPasswordReset, requestPasswordReset } from "../api/auth";
import { getCurrentSession } from "../api/events";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";

export function ForgotPasswordPage() {
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const [email, setEmail] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const requestMutation = useMutation({
    mutationFn: ({ address, csrfToken }: { address: string; csrfToken: string }) => requestPasswordReset(address, csrfToken),
    onSuccess: (result) => {
      if (!result.success) {
        setError(result.error || Object.values(result.errors ?? {}).flat()[0] || "Die Anfrage konnte nicht verarbeitet werden.");
        return;
      }
      setFeedback(result.message || "Wenn ein Konto mit dieser bestätigten E-Mail-Adresse existiert, erhältst du einen Link zum Zurücksetzen.");
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Die Anfrage konnte nicht gesendet werden."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback("");
    setError("");
    const csrfToken = sessionQuery.data?.csrf_token;
    if (!csrfToken) {
      setError("Deine Sitzung konnte nicht geprüft werden. Bitte lade die Seite neu.");
      return;
    }
    requestMutation.mutate({ address: email, csrfToken });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="auth-page">
        <section aria-labelledby="forgot-password-title" className="auth-card">
          <p className="eyebrow eyebrow--muted">ZUGANG WIEDERHERSTELLEN</p>
          <h1 id="forgot-password-title">Passwort vergessen<span>.</span></h1>
          <p className="auth-card__intro">Gib die bestätigte E-Mail-Adresse deines Kontos ein. Wenn sie zu einem Konto gehört, senden wir dir einen Link.</p>
          {feedback && <p className="action-feedback" role="status">{feedback}</p>}
          {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
          {sessionQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Sicherheitsprüfung konnte nicht geladen werden.</p>}
          <form className="auth-form" onSubmit={submit}>
            <label className="profile-field">
              <span>E-Mail-Adresse</span>
              <input autoComplete="email" maxLength={254} onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
            </label>
            <button className="participation-button auth-form__submit" disabled={requestMutation.isPending || sessionQuery.isLoading} type="submit">
              {requestMutation.isPending ? "Wird angefordert …" : "Link anfordern"}
            </button>
          </form>
          <p className="auth-card__switch"><Link to="/login">Zurück zum Einloggen</Link></p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";
  const sessionQuery = useQuery({ queryKey: ["current-session"], queryFn: getCurrentSession });
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);
  const resetMutation = useMutation({
    mutationFn: ({ csrfToken }: { csrfToken: string }) => confirmPasswordReset(uid, token, password, passwordConfirm, csrfToken),
    onSuccess: (result) => {
      if (!result.success) {
        setError(result.error || Object.values(result.errors ?? {}).flat()[0] || "Das Passwort konnte nicht geändert werden.");
        return;
      }
      setCompleted(true);
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Das Passwort konnte nicht geändert werden."),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!uid || !token) {
      setError("Der Link ist unvollständig. Fordere einen neuen Link an.");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Die Passwörter stimmen nicht überein.");
      return;
    }
    const csrfToken = sessionQuery.data?.csrf_token;
    if (!csrfToken) {
      setError("Deine Sitzung konnte nicht geprüft werden. Bitte lade die Seite neu.");
      return;
    }
    resetMutation.mutate({ csrfToken });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="auth-page">
        <section aria-labelledby="reset-password-title" className="auth-card">
          <p className="eyebrow eyebrow--muted">SICHERER ZUGANG</p>
          <h1 id="reset-password-title">Neues Passwort<span>.</span></h1>
          {completed ? (
            <div role="status">
              <p>Dein Passwort wurde geändert. Du kannst dich jetzt wieder anmelden.</p>
              <Link className="participation-button" to="/login">Zum Einloggen</Link>
            </div>
          ) : (
            <>
              <p className="auth-card__intro">Der Link ist eine Stunde gültig. Dein neues Passwort muss 8 bis 30 Zeichen lang sein.</p>
              {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
              {sessionQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Sicherheitsprüfung konnte nicht geladen werden.</p>}
              <form className="auth-form" onSubmit={submit}>
                <label className="profile-field">
                  <span>Neues Passwort</span>
                  <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
                </label>
                <label className="profile-field">
                  <span>Passwort bestätigen</span>
                  <input autoComplete="new-password" maxLength={30} minLength={8} onChange={(event) => setPasswordConfirm(event.target.value)} required type="password" value={passwordConfirm} />
                </label>
                <button className="participation-button auth-form__submit" disabled={resetMutation.isPending || sessionQuery.isLoading} type="submit">
                  {resetMutation.isPending ? "Wird gespeichert …" : "Passwort speichern"}
                </button>
              </form>
            </>
          )}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
