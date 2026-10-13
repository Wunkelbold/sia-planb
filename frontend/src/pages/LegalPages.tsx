import privacyTemplate from "../../../sia-backend/flask-server/static/templates/datenschutz.html?raw";
import imprintTemplate from "../../../sia-backend/flask-server/static/templates/impressum.html?raw";

import { SiteFooter, SiteHeader } from "../components/SiteLayout";

type LegalDocument = "privacy" | "imprint";

function legacyDocumentContent(template: string, title: string) {
  const content = template.match(/{% block content %}([\s\S]*?){% endblock %}/)?.[1] ?? "";
  return content
    .replace(/<div style="padding:50px">/, "<div>")
    .replace(`<h1>${title}</h1>`, "")
    .trim();
}

const documentDetails: Record<LegalDocument, { title: string; eyebrow: string; source: string }> = {
  privacy: {
    title: "Datenschutzerklärung",
    eyebrow: "TRANSPARENZ UND DATENSCHUTZ",
    source: legacyDocumentContent(privacyTemplate, "Datenschutzerklärung"),
  },
  imprint: {
    title: "Impressum",
    eyebrow: "ANGABEN GEMÄSS GESETZ",
    source: legacyDocumentContent(imprintTemplate, "Impressum"),
  },
};

export function LegalPage({ document }: { document: LegalDocument }) {
  const details = documentDetails[document];

  return (
    <div className="site-shell">
      <SiteHeader />
      <main className="info-page legal-page">
        <header className="info-page__hero">
          <p className="eyebrow eyebrow--muted">{details.eyebrow}</p>
          <h1>{details.title}<span>.</span></h1>
        </header>
        <article
          className="legal-page__content"
          dangerouslySetInnerHTML={{ __html: details.source }}
        />
      </main>
      <SiteFooter />
    </div>
  );
}
