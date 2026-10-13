import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { getUpcomingEvents } from "../api/events";
import { getPublicDrinkMenu, type DrinkMenuItem } from "../api/drinkMenu";
import {
  getContactSetup,
  submitContact,
  type ContactFormValues,
} from "../api/contact";
import { SiteFooter, SiteHeader } from "../components/SiteLayout";
import { ParticipationIndicators } from "../components/ParticipationIndicators";

const homeSlides = [
  { kind: "video", src: "/static/images/slider/kamerafahrt.mp4", title: "Das Plan B", text: "Dein Treffpunkt mitten in Albstadt." },
  { kind: "image", src: "/static/images/slider/slider1.avif", title: "Das Plan B", text: "Poststraße 6 · 72458 Albstadt" },
  { kind: "image", src: "/static/images/slider/slider4.avif", title: "Spaß haben", text: "Das Studium besteht nicht nur aus Lernen." },
  { kind: "image", src: "/static/images/slider/slider3.avif", title: "Durch dick und dünn", text: "Gemeinsam lernen, feiern und anpacken." },
];

function formatHomeDate(value: string | null) {
  if (!value) return "Termin folgt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Termin folgt";
  return new Intl.DateTimeFormat("de-DE", {
    timeZone: "Europe/Berlin",
    weekday: "short",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function HomePage() {
  const [activeSlide, setActiveSlide] = useState(0);
  const eventsQuery = useQuery({ queryKey: ["upcoming-events"], queryFn: getUpcomingEvents });
  const slide = homeSlides[activeSlide];

  function changeSlide(direction: number) {
    setActiveSlide((current) => (current + direction + homeSlides.length) % homeSlides.length);
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main>
        <section aria-label="Plan B Einblicke" className="home-carousel">
          {slide.kind === "video" ? (
            <video autoPlay className="home-carousel__media" loop muted playsInline poster="/static/images/slider/slider1.avif">
              <source src={slide.src} type="video/mp4" />
            </video>
          ) : (
            <img alt="Einblick in das Plan B und das Vereinsleben" className="home-carousel__media" src={slide.src} />
          )}
          <div className="home-carousel__shade" />
          <div className="home-carousel__caption" aria-live="polite">
            <p className="eyebrow"><span className="eyebrow__dot" /> STUDENTENINITIATIVE ALBSTADT E.V.</p>
            <h1>{slide.title}</h1>
            <p>{slide.text}</p>
            <Link className="hero__action" to="/events">Alle kommenden Events <span aria-hidden="true">→</span></Link>
          </div>
          <button aria-label="Vorheriger Einblick" className="home-carousel__control home-carousel__control--previous" onClick={() => changeSlide(-1)} type="button">‹</button>
          <button aria-label="Nächster Einblick" className="home-carousel__control home-carousel__control--next" onClick={() => changeSlide(1)} type="button">›</button>
          <div aria-label="Einblick auswählen" className="home-carousel__indicators">
            {homeSlides.map((item, index) => (
              <button
                aria-label={`Einblick ${index + 1}: ${item.title}`}
                aria-pressed={activeSlide === index}
                className={activeSlide === index ? "home-carousel__indicator home-carousel__indicator--active" : "home-carousel__indicator"}
                key={item.src}
                onClick={() => setActiveSlide(index)}
                type="button"
              />
            ))}
          </div>
        </section>

        <section className="home-intro">
          <div>
            <p className="eyebrow eyebrow--muted">VON STUDIERENDEN FÜR STUDIERENDE</p>
            <h2>Ein Ort für gute Begegnungen<span>.</span></h2>
            <p>
              Die Studenteninitiative Albstadt e.V. bringt Menschen zusammen. Im Plan B treffen sich
              Studierende, Alumni und Freund:innen zu Events, Kultur und gemeinsamen Projekten.
            </p>
          </div>
          <div className="home-intro__links">
            <Link to="/verein">Den Verein kennenlernen <span aria-hidden="true">→</span></Link>
            <Link to="/location">Unsere Location entdecken <span aria-hidden="true">→</span></Link>
            <Link to="/contact?category=mieten">Location anfragen <span aria-hidden="true">→</span></Link>
          </div>
        </section>

        <section aria-labelledby="home-events-heading" className="home-events">
          <div className="section-heading">
            <div>
              <p className="eyebrow eyebrow--muted">WAS STEHT AN?</p>
              <h2 id="home-events-heading">Kommende Events<span>.</span></h2>
            </div>
            <Link className="home-events__all" to="/events">Alle Events <span aria-hidden="true">→</span></Link>
          </div>
          {eventsQuery.isLoading && <p className="detail-loading" role="status">Events werden geladen …</p>}
          {eventsQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Events konnten gerade nicht geladen werden.</p>}
          {!eventsQuery.isLoading && !eventsQuery.isError && eventsQuery.data?.length === 0 && (
            <div className="participation-empty">Aktuell sind keine kommenden Events eingetragen.</div>
          )}
          {!!eventsQuery.data?.length && (
            <div className="home-event-grid">
              {eventsQuery.data.slice(0, 3).map((event) => (
                <article className="home-event-card" key={event.id}>
                  <img alt={`Plakat für ${event.name}`} loading="lazy" src={event.poster_url} />
                  <div>
                    <p className="event-card__date">{formatHomeDate(event.date)}</p>
                    <h3>{event.name}</h3>
                    <p>{event.place || "Ort folgt"}</p>
                    <ParticipationIndicators event={event} />
                    <Link to={`/events/${event.id}`}>Details <span aria-hidden="true">→</span></Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

const testimonials = [
  {
    name: "Tobias · SIA-Alumni, 2019",
    quote: "Die SIA bietet fantastische Gelegenheiten, wertvolle Kontakte zwischen Studierenden und Professoren zu knüpfen. Die SIA bedeutet mir nach wie vor sehr viel und hat mein Studium sehr bereichert.",
  },
  {
    name: "Leon · aktives Mitglied, 2022",
    quote: "In der Klausurenphase haben wir uns intern zum Lernen getroffen. Nachdem man sich kannte, wurde alles entspannter. Ich bin froh, beigetreten zu sein.",
  },
  {
    name: "Simon · SIA-Alumni, 2022",
    quote: "Von Anfang an hatte ich eine Anlaufstelle mit super netten Leuten. Aus der anfangs fremden Umgebung wurde schnell ein Zuhause.",
  },
  {
    name: "Andra · aktives Mitglied",
    quote: "Die SIA ist ein Ort, an dem man Menschen kennenlernt und lebenslange Freundschaften aufbaut. Sie ist für mich ein echtes Highlight in Albstadt.",
  },
  {
    name: "Marc · SIA-Alumni, 2018",
    quote: "Die SIA war während meines Studiums wie eine zweite Familie. Ich habe viel fürs Studium und fürs Leben gelernt und schaue als Alumni noch immer gerne im Plan B vorbei.",
  },
];

const history = [
  {
    year: "1990",
    title: "Die Gründung",
    text: "Am 28. Mai 1990 wurde die Studenteninitiative Albstadt e.V. gegründet. Ihr Ziel: Studierende in fachlichen, kulturellen und sozialen Angelegenheiten zu unterstützen.",
  },
  {
    year: "2000",
    title: "Ein erster Treffpunkt",
    text: "In der Villa Weiß entstand eine SIA-Bar. Aus regelmäßigen Treffen entwickelte sich schnell ein beliebter Treffpunkt für Studierende aller Fachrichtungen.",
  },
  {
    year: "2002",
    title: "Die Ladezone",
    text: "Ein neues Vereinslokal bot Platz für Bar, Sofas und viele gemeinsame Abende. Freiwillige Helfer:innen machten den regelmäßigen Betrieb möglich.",
  },
  {
    year: "2009",
    title: "Abschied von der Ladezone",
    text: "Das Mietverhältnis endete im März 2009, damit die Hochschule die Räume umbauen konnte. Schon seit 2008 war ein regelmäßiger Betrieb nicht mehr möglich.",
  },
  {
    year: "Heute",
    title: "Das Plan B",
    text: "Die SIA gestaltet das Campusleben ehrenamtlich weiter – mit dem Plan B als Ort für Events, Kultur und Gemeinschaft.",
  },
];

export function VereinPage() {
  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="info-page">
        <header className="info-page__hero">
          <p className="eyebrow eyebrow--muted">STUDENTENINITIATIVE ALBSTADT E.V.</p>
          <h1>Von Studierenden.<br /><span>Für Studierende.</span></h1>
          <p>Ein Verein, ein Treffpunkt und jede Menge Möglichkeiten, das Campusleben gemeinsam zu gestalten.</p>
        </header>

        <section className="info-copy-card">
          <h2>Willkommen bei der SIA<span>.</span></h2>
          <p>
            Wir sind ein studentischer Verein, der das Campusleben mit Leidenschaft bereichert. Unser Herzstück ist die Bar
            <strong> Plan B</strong> – ein Treffpunkt für Partys, kulturelle Events und vieles mehr. Die Mitarbeit ist ehrenamtlich;
            jede helfende Hand macht unser Projekt einzigartig.
          </p>
          <p>
            Bei uns bist du willkommen, egal ob du Ideen einbringen, mit anpacken oder einfach Teil der Gemeinschaft sein möchtest.
            Aktive und passive Mitglieder gestalten den Verein offen und transparent. Kosten oder Verpflichtungen gibt es nicht.
          </p>
          <div className="info-copy-card__actions">
            <Link className="participation-button" to="/register">Mitmachen</Link>
            <a className="participation-button participation-button--quiet" href="https://www.instagram.com/sia_albstadt/" rel="noreferrer" target="_blank">Instagram <span aria-hidden="true">↗</span></a>
          </div>
        </section>

        <section aria-labelledby="testimonials-heading" className="info-section">
          <div className="participation-section__heading">
            <p className="eyebrow eyebrow--muted">STIMMEN AUS DEM VEREIN</p>
            <h2 id="testimonials-heading">Was sagen die Mitglieder<span>?</span></h2>
          </div>
          <div className="testimonial-grid">
            {testimonials.map((testimonial) => (
              <blockquote className="testimonial-card" key={testimonial.name}>
                <p>“{testimonial.quote}”</p>
                <footer>{testimonial.name}</footer>
              </blockquote>
            ))}
          </div>
        </section>

        <section aria-labelledby="history-heading" className="info-section">
          <div className="participation-section__heading">
            <p className="eyebrow eyebrow--muted">SEIT 1990</p>
            <h2 id="history-heading">Ein Stück Geschichte<span>.</span></h2>
          </div>
          <ol className="history-list">
            {history.map((item) => (
              <li className="history-card" key={item.year}>
                <span className="history-card__year">{item.year}</span>
                <div><h3>{item.title}</h3><p>{item.text}</p></div>
              </li>
            ))}
          </ol>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

const locationImages = [
  { src: "/static/images/location/lernraum.avif", alt: "Lernbereich im Plan B" },
  { src: "/static/images/location/eingang.avif", alt: "Eingang zum Plan B" },
  { src: "/static/images/location/bild31.avif", alt: "Einblick in die Vereinsräume" },
  { src: "/static/images/location/kinoabend.avif", alt: "Kinoabend im Plan B" },
  { src: "/static/images/location/barbereich.avif", alt: "Barbereich im Plan B" },
  { src: "/static/images/location/liveband.avif", alt: "Live-Musik im Plan B" },
  { src: "/static/images/location/blacklight.avif", alt: "Party mit Schwarzlicht" },
  { src: "/static/images/location/terasse.avif", alt: "Terrasse des Plan B" },
  { src: "/static/images/location/stpatrick.avif", alt: "St. Patrick’s Day im Plan B" },
];

function PlanBViewer() {
  const viewer = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !viewer.current) return;
    let disposed = false;
    let timeout: number | undefined;
    const scripts = [
      "/static/js/aframe.min.js",
      "/static/js/aframe-teleport-controls.min.js",
      "/static/js/drone-controls-mode2.js",
      "/static/js/mc-controls.js",
    ];

    const loadScript = (src: string) => new Promise<void>((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>(`script[data-planb-viewer="${src}"]`);
      if (existing?.dataset.loaded === "true") return resolve();
      const script = existing || document.createElement("script");
      const onLoad = () => {
        script.dataset.loaded = "true";
        resolve();
      };
      const onError = () => reject(new Error("Die 3D-Ansicht konnte nicht geladen werden."));
      script.addEventListener("load", onLoad, { once: true });
      script.addEventListener("error", onError, { once: true });
      if (!existing) {
        script.src = src;
        script.dataset.planbViewer = src;
        document.body.appendChild(script);
      }
    });

    async function mountViewer() {
      try {
        setLoading(true);
        setError("");
        for (const src of scripts) await loadScript(src);
        if (disposed || !viewer.current) return;
        viewer.current.innerHTML = `
          <a-scene embedded renderer="antialias: true; colorManagement: true" vr-mode-ui="enabled: true" background="color: #222426">
            <a-assets timeout="15000">
              <a-asset-item id="planb-model" src="/static/assets/Plan_B_3D_Scan.glb"></a-asset-item>
            </a-assets>
            <a-entity light="type: ambient; color: #FFF"></a-entity>
            <a-entity id="cameraRig" position="0 0 0">
              <a-entity id="head" camera position="0 1.7 0" mc-controls look-controls></a-entity>
              <a-entity id="leftHand" hand-tracking-controls="hand: left"></a-entity>
              <a-entity id="rightHand" hand-tracking-controls="hand: right"></a-entity>
            </a-entity>
            <a-entity id="planb-model-entity" gltf-model="#planb-model" position="0.8 0 1.1" scale="1 1 1"></a-entity>
          </a-scene>`;
        const model = viewer.current.querySelector("#planb-model-entity");
        model?.addEventListener("model-loaded", () => setLoading(false), { once: true });
        model?.addEventListener("model-error", () => {
          setLoading(false);
          setError("Das 3D-Modell konnte nicht geladen werden.");
        }, { once: true });
        timeout = window.setTimeout(() => {
          if (!disposed) setLoading(false);
        }, 15000);
      } catch (viewerError) {
        if (!disposed) {
          setLoading(false);
          setError(viewerError instanceof Error ? viewerError.message : "3D-Ansicht nicht verfügbar.");
        }
      }
    }

    void mountViewer();
    return () => {
      disposed = true;
      if (timeout) window.clearTimeout(timeout);
      if (viewer.current) viewer.current.innerHTML = "";
    };
  }, [open]);

  return (
    <section className="location-viewer-card">
      <div className="location-viewer-card__heading">
        <div>
          <p className="eyebrow eyebrow--muted">VIRTUELLER RUNDGANG</p>
          <h2>Schau dich im Plan B um<span>.</span></h2>
          <p>Nutze Maus oder Touch zum Umschauen. Auf unterstützten Geräten kannst du in den VR-Modus wechseln.</p>
        </div>
        <button className="participation-button" onClick={() => setOpen((current) => !current)} type="button">
          {open ? "3D-Ansicht schließen" : "3D-Ansicht öffnen"}
        </button>
      </div>
      {open && (
        <>
          {loading && <p className="viewer-loading" role="status">Lade den 3D-Rundgang …</p>}
          {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
          <div aria-label="Interaktiver 3D-Rundgang durch das Plan B" className="location-viewer" ref={viewer} />
        </>
      )}
    </section>
  );
}

export function LocationPage() {
  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="info-page location-page">
        <header className="info-page__hero">
          <p className="eyebrow eyebrow--muted">POSTSTRASSE 6 · 72458 ALBSTADT</p>
          <h1>Plan B<span>.</span><br />Der Treffpunkt der SIA.</h1>
          <p>Bar, Vereinsraum und Bühne für Partys, Kultur, gemeinsames Lernen und vieles mehr.</p>
          <Link className="hero__action" to="/contact?category=mieten">Location anfragen <span aria-hidden="true">→</span></Link>
        </header>

        <PlanBViewer />

        <section aria-labelledby="location-gallery-heading" className="info-section">
          <div className="participation-section__heading">
            <p className="eyebrow eyebrow--muted">EINBLICKE</p>
            <h2 id="location-gallery-heading">Ein Ort für vieles<span>.</span></h2>
          </div>
          <div className="location-gallery">
            {locationImages.map((image) => (
              <figure className="location-gallery__item" key={image.src}>
                <img alt={image.alt} loading="lazy" src={image.src} />
                <figcaption>{image.alt}</figcaption>
              </figure>
            ))}
          </div>
          <div className="location-address-card">
            <div>
              <p className="eyebrow eyebrow--muted">HIER FINDEST DU UNS</p>
              <h3>Plan B · Poststraße 6</h3>
              <p>72458 Albstadt</p>
            </div>
            <a className="participation-button participation-button--quiet" href="https://maps.google.com/?q=Poststra%C3%9Fe+6,+72458+Albstadt" rel="noreferrer" target="_blank">Route öffnen <span aria-hidden="true">↗</span></a>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export function ContactPage() {
  const [searchParams] = useSearchParams();
  const setupQuery = useQuery({ queryKey: ["contact-setup"], queryFn: getContactSetup });
  const [values, setValues] = useState<ContactFormValues>(() => ({
    category: searchParams.get("category") || "kontakt",
    surname: "",
    lastname: "",
    email: "",
    message: "",
    privacy_policy: false,
  }));
  const [captchaOverride, setCaptchaOverride] = useState<import("../api/auth").CaptchaChallenge | null>(null);
  const [csrfOverride, setCsrfOverride] = useState("");
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [errorMessage, setErrorMessage] = useState("");
  const [sentMessage, setSentMessage] = useState("");
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (!setupQuery.data) return;
    setValues((current) => ({
      ...current,
      surname: current.surname || setupQuery.data.prefill.surname,
      lastname: current.lastname || setupQuery.data.prefill.lastname,
      email: current.email || setupQuery.data.prefill.email,
    }));
  }, [setupQuery.data]);

  const contactMutation = useMutation({
    mutationFn: ({ csrfToken, captcha }: { csrfToken: string; captcha: import("../api/auth").CaptchaChallenge }) =>
      submitContact(values, captchaAnswer, captcha, csrfToken),
    onMutate: () => {
      setErrors({});
      setErrorMessage("");
    },
    onSuccess: (result) => {
      if (!result.success) {
        setErrors(result.errors ?? {});
        setErrorMessage(Object.values(result.errors ?? {}).flat()[0] || "Bitte überprüfe deine Angaben.");
        if (result.captcha) setCaptchaOverride(result.captcha);
        if (result.csrf_token) setCsrfOverride(result.csrf_token);
        setCaptchaAnswer("");
        return;
      }
      setSent(true);
      setSentMessage(result.message || "Danke für deine Nachricht!");
    },
    onError: (error) => setErrorMessage(error instanceof Error ? error.message : "Die Kontaktanfrage konnte nicht gesendet werden."),
  });

  const captcha = captchaOverride || setupQuery.data?.captcha;
  const csrfToken = csrfOverride || setupQuery.data?.csrf_token;
  const requiresContactDetails = ["kontakt", "mieten", "events"].includes(values.category);
  const fieldError = (field: string) => errors[field]?.[0];

  async function refreshCaptcha() {
    setCaptchaOverride(null);
    setCaptchaAnswer("");
    setErrors({});
    await setupQuery.refetch();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    if (!csrfToken || !captcha) {
      setErrorMessage("Das Formular ist noch nicht bereit. Bitte lade die Seite neu.");
      return;
    }
    contactMutation.mutate({ csrfToken, captcha });
  }

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="info-page contact-page">
        <header className="info-page__hero">
          <p className="eyebrow eyebrow--muted">WIR FREUEN UNS AUF DEINE NACHRICHT</p>
          <h1>Kontakt<span>.</span></h1>
          <p>Kritik und Lob kannst du auch anonym senden. Für Fragen und Mietanfragen brauchen wir deine Kontaktdaten.</p>
        </header>

        {sent ? (
          <section className="contact-success" role="status">
            <span aria-hidden="true" className="contact-success__check">✓</span>
            <h2>{sentMessage}</h2>
            <p>Vielen Dank, dass du dir Zeit genommen hast, uns zu schreiben.</p>
            <Link className="participation-button" to="/">Zur Startseite</Link>
          </section>
        ) : (
          <form className="contact-form" onSubmit={submit}>
            <h2>Kontaktanfrage</h2>
            {errorMessage && <p className="action-feedback action-feedback--error" role="alert">{errorMessage}</p>}
            {setupQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Das Formular konnte nicht geladen werden.</p>}

            <div className="manager-form-grid">
              <label className="profile-field manager-form-grid__wide">
                <span>Art der Anfrage</span>
                <select onChange={(e) => setValues((current) => ({ ...current, category: e.target.value }))} value={values.category}>
                  {(setupQuery.data?.categories ?? []).map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                </select>
                {fieldError("category") && <small className="auth-field-error">{fieldError("category")}</small>}
              </label>
              <label className="profile-field">
                <span>Vorname{requiresContactDetails ? " *" : ""}</span>
                <input maxLength={20} onChange={(e) => setValues((current) => ({ ...current, surname: e.target.value }))} required={requiresContactDetails} value={values.surname} />
                {fieldError("surname") && <small className="auth-field-error">{fieldError("surname")}</small>}
              </label>
              <label className="profile-field">
                <span>Nachname{requiresContactDetails ? " *" : ""}</span>
                <input maxLength={20} onChange={(e) => setValues((current) => ({ ...current, lastname: e.target.value }))} required={requiresContactDetails} value={values.lastname} />
                {fieldError("lastname") && <small className="auth-field-error">{fieldError("lastname")}</small>}
              </label>
              <label className="profile-field manager-form-grid__wide">
                <span>E-Mail{requiresContactDetails ? " *" : ""}</span>
                <input maxLength={30} onChange={(e) => setValues((current) => ({ ...current, email: e.target.value }))} required={requiresContactDetails} type="email" value={values.email} />
                {fieldError("email") && <small className="auth-field-error">{fieldError("email")}</small>}
              </label>
              <label className="profile-field manager-form-grid__wide">
                <span>Nachricht</span>
                <textarea maxLength={500} minLength={20} onChange={(e) => setValues((current) => ({ ...current, message: e.target.value }))} required rows={7} value={values.message} />
                {fieldError("message") && <small className="auth-field-error">{fieldError("message")}</small>}
              </label>
            </div>

            <div className="captcha-field">
              <div className="captcha-field__heading">
                <label htmlFor="contact-captcha">Sicherheitsabfrage</label>
                <button className="text-button" disabled={setupQuery.isFetching} onClick={() => void refreshCaptcha()} type="button">Neue Abfrage</button>
              </div>
              {captcha && <img alt="Zeichen aus dem CAPTCHA" src={captcha.image} />}
              <input autoComplete="off" id="contact-captcha" maxLength={6} minLength={6} onChange={(e) => setCaptchaAnswer(e.target.value)} placeholder="Zeichen eingeben" required value={captchaAnswer} />
              {fieldError("captcha") && <small className="auth-field-error">{fieldError("captcha")}</small>}
            </div>

            <label className="privacy-consent">
              <input checked={values.privacy_policy} onChange={(e) => setValues((current) => ({ ...current, privacy_policy: e.target.checked }))} required type="checkbox" />
              <span>Ich akzeptiere die Verarbeitung meiner Daten nach der <Link rel="noreferrer" target="_blank" to="/datenschutz">Datenschutzerklärung</Link>.</span>
            </label>
            {fieldError("privacy_policy") && <small className="auth-field-error">{fieldError("privacy_policy")}</small>}

            <button className="participation-button" disabled={contactMutation.isPending || setupQuery.isLoading} type="submit">
              {contactMutation.isPending ? "Wird gesendet …" : "Anfrage senden"}
            </button>
          </form>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}

function formatMenuPrice(cents: number | null) {
  return ((cents || 0) / 100).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

function formatMenuUpdatedAt(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function groupedMenuItems(items: DrinkMenuItem[]) {
  const groups: Array<{ label: string; items: DrinkMenuItem[] }> = [];
  for (const item of items) {
    const label = item.group_label || "";
    const existing = groups.find((group) => group.label === label);
    if (existing) existing.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

export function DrinkMenuPage() {
  const menuQuery = useQuery({ queryKey: ["public-drink-menu"], queryFn: getPublicDrinkMenu });
  const menu = menuQuery.data;

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="info-page drink-menu-page">
        <header className="info-page__hero">
          <p className="eyebrow eyebrow--muted">PLAN B · POSTSTRASSE 6</p>
          <h1>Getränkekarte<span>.</span></h1>
          <p>Was heute am Tresen steht – immer aktuell, ohne gedruckte Karte.</p>
        </header>

        {menuQuery.isLoading && <p className="detail-loading" role="status">Getränkekarte wird geladen …</p>}
        {menuQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Getränkekarte konnte nicht geladen werden.</p>}
        {menu && menu.sections.length === 0 && <p className="participation-empty">Die Getränkekarte wird gerade überarbeitet.</p>}
        {menu && menu.sections.length > 0 && (
          <div className="drink-menu-board">
            {menu.sections.map((section) => (
              <section className="drink-menu-section" key={section.uid}>
                <header className="drink-menu-section__heading">
                  <div>
                    <h2>{section.title}</h2>
                    {section.subtitle && <p>{section.subtitle}</p>}
                  </div>
                  {section.show_price && section.price_cents != null && (
                    <span className="drink-menu-section__price">{formatMenuPrice(section.price_cents)}</span>
                  )}
                </header>
                {groupedMenuItems(section.items).map((group) => (
                  <div className="drink-menu-group" key={group.label || "items"}>
                    {group.label && <h3 className="drink-menu-group__label">{group.label}</h3>}
                    <ul className="drink-menu-list">
                      {group.items.map((item) => (
                        <li className="drink-menu-item" key={item.uid}>
                          {item.image_url && <img alt="" className="drink-menu-item__image" loading="lazy" src={item.image_url} />}
                          <div className="drink-menu-item__text">
                            <span className="drink-menu-item__name">{item.name}</span>
                            {item.volume_label && <span className="drink-menu-item__volume">{item.volume_label}</span>}
                            {item.description && <span className="drink-menu-item__description">{item.description}</span>}
                          </div>
                          {item.show_price && item.price_cents != null && (
                            <span className="drink-menu-item__price">{formatMenuPrice(item.price_cents)}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </section>
            ))}
          </div>
        )}

        {menu && (
          <section className="drink-menu-share">
            {menu.qr_data_url && <img alt="QR-Code zur Getränkekarte" className="drink-menu-share__qr" src={menu.qr_data_url} />}
            <div>
              <p className="eyebrow eyebrow--muted">IMMER AKTUELL</p>
              <h2>Einfach scannen<span>.</span></h2>
              <p>Diese Karte lebt: Änderungen an Preisen und Angeboten erscheinen sofort. Speichere den Link oder scanne den QR-Code am Tresen.</p>
              {menu.updated_at && <small className="drink-menu-share__updated">Stand: {formatMenuUpdatedAt(menu.updated_at)}</small>}
            </div>
          </section>
        )}

        <p className="drink-menu-deposit">zzgl. Pfand · 2 € Becher &amp; Flaschen | 3 € Gläser &amp; Tassen</p>
      </main>
      <SiteFooter />
    </div>
  );
}
