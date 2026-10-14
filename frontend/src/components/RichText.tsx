import { Fragment, useMemo } from "react";
import type { ReactNode } from "react";

const inlineTags = new Set(["STRONG", "B", "EM", "I", "U", "SPAN"]);
const droppedTags = new Set(["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED"]);

function isAllowedHref(href: string): boolean {
  if (href.startsWith("/") || href.startsWith("#")) return true;
  return /^(https?:|mailto:|tel:)/i.test(href);
}

function renderNode(node: Node, path: string): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.nodeType !== Node.ELEMENT_NODE) return null;

  const element = node as Element;
  const tag = element.tagName.toUpperCase();

  if (droppedTags.has(tag)) return null;

  const children = Array.from(element.childNodes).map((child, index) => (
    <Fragment key={index}>{renderNode(child, `${path}-${index}`)}</Fragment>
  ));

  if (tag === "BR") return <br key={path} />;

  if (tag === "A") {
    const href = (element.getAttribute("href") ?? "").trim();
    if (!isAllowedHref(href)) return <Fragment key={path}>{children}</Fragment>;
    return (
      <a href={href} key={path} rel="noopener noreferrer" target="_blank">
        {children}
      </a>
    );
  }

  if (!inlineTags.has(tag)) return <Fragment key={path}>{children}</Fragment>;

  if (tag === "STRONG" || tag === "B") return <strong key={path}>{children}</strong>;
  if (tag === "EM" || tag === "I") return <em key={path}>{children}</em>;
  if (tag === "U") return <u key={path}>{children}</u>;
  return <span key={path}>{children}</span>;
}

function renderHtml(html: string): ReactNode {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  return Array.from(parsed.body.childNodes).map((node, index) => (
    <Fragment key={index}>{renderNode(node, String(index))}</Fragment>
  ));
}

export function RichText({ fallback, text }: { fallback: string; text: string | null | undefined }) {
  const content = useMemo(() => (text ? renderHtml(text) : null), [text]);
  return <>{content ?? fallback}</>;
}
