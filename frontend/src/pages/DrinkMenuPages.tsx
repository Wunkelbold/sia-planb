import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  createDrinkMenuItem,
  createDrinkMenuSection,
  deactivateDrinkMenuItem,
  deactivateDrinkMenuSection,
  getAdminDrinkMenu,
  removeDrinkMenuItemImage,
  updateDrinkMenuItem,
  updateDrinkMenuSection,
  uploadDrinkMenuItemImage,
  type DrinkMenuItem,
  type DrinkMenuSection,
} from "../api/drinkMenu";

function priceToInput(cents: number | null) {
  return cents == null ? "" : (cents / 100).toFixed(2);
}

function priceFromInput(value: string) {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  const parsed = Number(normalized);
  if (Number.isNaN(parsed) || parsed < 0) return null;
  return Math.round(parsed * 100);
}

function orderFromInput(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.round(parsed) : 0;
}

export function AdminDrinkMenuPanel({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const menuQuery = useQuery({ queryKey: ["admin-drink-menu"], queryFn: getAdminDrinkMenu });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [newSectionTitle, setNewSectionTitle] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-drink-menu"] });
  const createSectionMutation = useMutation({
    mutationFn: () => createDrinkMenuSection({
      title: newSectionTitle.trim(),
      subtitle: "",
      price_cents: null,
      show_price: false,
      sort_order: (menuQuery.data?.sections.length ?? 0) + 1,
    }, csrfToken),
    onSuccess: async () => {
      setNewSectionTitle("");
      setNotice("Kategorie wurde angelegt.");
      setError("");
      await invalidate();
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : "Kategorie konnte nicht angelegt werden."),
  });

  const sections = menuQuery.data?.sections ?? [];

  return (
    <section aria-labelledby="admin-drink-menu-title" className="finance-admin-content">
      <header className="finance-section__heading">
        <div>
          <p className="eyebrow eyebrow--muted">GETRÄNKEKARTE</p>
          <h2 id="admin-drink-menu-title">Öffentliche Karte<span>.</span></h2>
        </div>
        <a className="text-button" href="/getraenkekarte" rel="noreferrer" target="_blank">Öffentliche Karte öffnen ↗</a>
      </header>
      <p className="finance-help-text">
        Die Getränkekarte unter <strong>/getraenkekarte</strong> zeigt nur aktive Kategorien und Artikel. Preise lassen sich pro Artikel oder Kategorie ausblenden;
        Bilder und Logos werden beim Artikel hochgeladen. Der QR-Code auf der öffentlichen Seite verlinkt immer auf die aktuelle Karte.
      </p>
      {notice && <p className="action-feedback" role="status">{notice}</p>}
      {error && <p className="action-feedback action-feedback--error" role="alert">{error}</p>}
      {menuQuery.isLoading && <p className="participation-empty" role="status">Getränkekarte wird geladen …</p>}
      {menuQuery.isError && <p className="action-feedback action-feedback--error" role="alert">Die Getränkekarte konnte nicht geladen werden.</p>}

      {menuQuery.data && (
        <>
          <section className="finance-admin-section">
            <header className="finance-section__heading"><div><p className="eyebrow eyebrow--muted">STRUKTUR</p><h3>Neue Kategorie</h3></div></header>
            <form className="manager-form-grid finance-new-item-form" onSubmit={(event) => { event.preventDefault(); createSectionMutation.mutate(); }}>
              <label className="profile-field"><span>Titel</span><input maxLength={80} onChange={(event) => setNewSectionTitle(event.target.value)} required value={newSectionTitle} /></label>
              <button className="participation-button" disabled={createSectionMutation.isPending || !newSectionTitle.trim()} type="submit">Kategorie hinzufügen</button>
            </form>
          </section>

          <div className="drink-menu-admin-list">
            {sections.map((section) => (
              <DrinkSectionEditor
                csrfToken={csrfToken}
                key={section.uid}
                section={section}
                onNotice={setNotice}
                onError={setError}
                onChanged={invalidate}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function DrinkSectionEditor({
  csrfToken,
  section,
  onNotice,
  onError,
  onChanged,
}: {
  csrfToken: string;
  section: DrinkMenuSection;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
  onChanged: () => Promise<unknown>;
}) {
  const [title, setTitle] = useState(section.title);
  const [subtitle, setSubtitle] = useState(section.subtitle);
  const [price, setPrice] = useState(priceToInput(section.price_cents));
  const [showPrice, setShowPrice] = useState(section.show_price);
  const [sortOrder, setSortOrder] = useState(String(section.sort_order));
  const [active, setActive] = useState(section.is_active);
  const [newItemName, setNewItemName] = useState("");
  const [newItemGroup, setNewItemGroup] = useState("");
  const [newItemVolume, setNewItemVolume] = useState("");
  const [newItemPrice, setNewItemPrice] = useState("");

  useEffect(() => {
    setTitle(section.title);
    setSubtitle(section.subtitle);
    setPrice(priceToInput(section.price_cents));
    setShowPrice(section.show_price);
    setSortOrder(String(section.sort_order));
    setActive(section.is_active);
  }, [section]);

  const saveMutation = useMutation({
    mutationFn: () => updateDrinkMenuSection(section.uid, {
      title: title.trim(),
      subtitle: subtitle.trim(),
      price_cents: priceFromInput(price),
      show_price: showPrice,
      sort_order: orderFromInput(sortOrder),
      is_active: active,
    }, csrfToken),
    onSuccess: async () => { onNotice(`Kategorie „${title.trim()}“ wurde gespeichert.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Kategorie konnte nicht gespeichert werden."),
  });
  const deactivateMutation = useMutation({
    mutationFn: () => deactivateDrinkMenuSection(section.uid, csrfToken),
    onSuccess: async () => { onNotice(`Kategorie „${section.title}“ wurde ausgeblendet.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Kategorie konnte nicht ausgeblendet werden."),
  });
  const addItemMutation = useMutation({
    mutationFn: () => createDrinkMenuItem({
      section_uid: section.uid,
      name: newItemName.trim(),
      group_label: newItemGroup.trim(),
      description: "",
      volume_label: newItemVolume.trim(),
      price_cents: priceFromInput(newItemPrice),
      show_price: priceFromInput(newItemPrice) != null,
      sort_order: section.items.length + 1,
    }, csrfToken),
    onSuccess: async () => {
      setNewItemName(""); setNewItemGroup(""); setNewItemVolume(""); setNewItemPrice("");
      onNotice("Artikel wurde angelegt.");
      onError("");
      await onChanged();
    },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht angelegt werden."),
  });

  return (
    <section className={`finance-admin-section drink-menu-admin-section${section.is_active ? "" : " drink-menu-admin-section--inactive"}`}>
      <header className="finance-section__heading">
        <div><p className="eyebrow eyebrow--muted">KATEGORIE</p><h3>{section.title}</h3></div>
        {!section.is_active && <span className="admin-count-badge">ausgeblendet</span>}
      </header>
      <form className="manager-form-grid" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
        <label className="profile-field"><span>Titel</span><input maxLength={80} onChange={(event) => setTitle(event.target.value)} required value={title} /></label>
        <label className="profile-field"><span>Untertitel</span><input maxLength={200} onChange={(event) => setSubtitle(event.target.value)} value={subtitle} /></label>
        <label className="profile-field"><span>Preis (€)</span><input min="0" onChange={(event) => setPrice(event.target.value)} placeholder="ohne Preis" step="0.01" type="number" value={price} /></label>
        <label className="manager-checkbox"><input checked={showPrice} onChange={(event) => setShowPrice(event.target.checked)} type="checkbox" /><span>Preis anzeigen</span></label>
        <label className="profile-field"><span>Sortierung</span><input min="0" onChange={(event) => setSortOrder(event.target.value)} type="number" value={sortOrder} /></label>
        <label className="manager-checkbox"><input checked={active} onChange={(event) => setActive(event.target.checked)} type="checkbox" /><span>Auf der Karte sichtbar</span></label>
        <div className="finance-inline-actions">
          <button className="text-button" disabled={saveMutation.isPending} type="submit">Speichern</button>
          {section.is_active && <button className="text-button text-button--danger" disabled={deactivateMutation.isPending} onClick={() => deactivateMutation.mutate()} type="button">Ausblenden</button>}
        </div>
      </form>

      <div className="drink-menu-admin-items">
        {section.items.map((item) => (
          <DrinkItemEditor
            csrfToken={csrfToken}
            item={item}
            key={item.uid}
            onNotice={onNotice}
            onError={onError}
            onChanged={onChanged}
          />
        ))}
      </div>

      <form className="manager-form-grid drink-menu-admin-new-item" onSubmit={(event) => { event.preventDefault(); addItemMutation.mutate(); }}>
        <label className="profile-field"><span>Neuer Artikel</span><input maxLength={80} onChange={(event) => setNewItemName(event.target.value)} required value={newItemName} /></label>
        <label className="profile-field"><span>Gruppe (optional)</span><input maxLength={80} onChange={(event) => setNewItemGroup(event.target.value)} value={newItemGroup} /></label>
        <label className="profile-field"><span>Menge</span><input maxLength={40} onChange={(event) => setNewItemVolume(event.target.value)} placeholder="0,33 l" value={newItemVolume} /></label>
        <label className="profile-field"><span>Preis (€)</span><input min="0" onChange={(event) => setNewItemPrice(event.target.value)} placeholder="ohne Preis" step="0.01" type="number" value={newItemPrice} /></label>
        <button className="participation-button" disabled={addItemMutation.isPending || !newItemName.trim()} type="submit">Artikel hinzufügen</button>
      </form>
    </section>
  );
}

function DrinkItemEditor({
  csrfToken,
  item,
  onNotice,
  onError,
  onChanged,
}: {
  csrfToken: string;
  item: DrinkMenuItem;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
  onChanged: () => Promise<unknown>;
}) {
  const [name, setName] = useState(item.name);
  const [groupLabel, setGroupLabel] = useState(item.group_label);
  const [volume, setVolume] = useState(item.volume_label);
  const [description, setDescription] = useState(item.description);
  const [price, setPrice] = useState(priceToInput(item.price_cents));
  const [showPrice, setShowPrice] = useState(item.show_price);
  const [sortOrder, setSortOrder] = useState(String(item.sort_order));
  const [active, setActive] = useState(item.is_active);

  useEffect(() => {
    setName(item.name);
    setGroupLabel(item.group_label);
    setVolume(item.volume_label);
    setDescription(item.description);
    setPrice(priceToInput(item.price_cents));
    setShowPrice(item.show_price);
    setSortOrder(String(item.sort_order));
    setActive(item.is_active);
  }, [item]);

  const saveMutation = useMutation({
    mutationFn: () => updateDrinkMenuItem(item.uid, {
      section_uid: "",
      name: name.trim(),
      group_label: groupLabel.trim(),
      description: description.trim(),
      volume_label: volume.trim(),
      price_cents: priceFromInput(price),
      show_price: showPrice,
      sort_order: orderFromInput(sortOrder),
      is_active: active,
    }, csrfToken),
    onSuccess: async () => { onNotice(`Artikel „${name.trim()}“ wurde gespeichert.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht gespeichert werden."),
  });
  const deactivateMutation = useMutation({
    mutationFn: () => deactivateDrinkMenuItem(item.uid, csrfToken),
    onSuccess: async () => { onNotice(`Artikel „${item.name}“ wurde ausgeblendet.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Artikel konnte nicht ausgeblendet werden."),
  });
  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDrinkMenuItemImage(item.uid, file, csrfToken),
    onSuccess: async () => { onNotice(`Bild für „${item.name}“ wurde gespeichert.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Bild konnte nicht gespeichert werden."),
  });
  const removeImageMutation = useMutation({
    mutationFn: () => removeDrinkMenuItemImage(item.uid, csrfToken),
    onSuccess: async () => { onNotice(`Bild für „${item.name}“ wurde entfernt.`); onError(""); await onChanged(); },
    onError: (mutationError) => onError(mutationError instanceof Error ? mutationError.message : "Bild konnte nicht entfernt werden."),
  });

  return (
    <article className={`drink-menu-admin-item${item.is_active ? "" : " drink-menu-admin-item--inactive"}`}>
      <div className="drink-menu-admin-item__media">
        {item.image_url
          ? <img alt={`Bild zu ${item.name}`} src={item.image_url} />
          : <span className="drink-menu-admin-item__placeholder" aria-hidden="true">kein Bild</span>}
        <input
          accept="image/png,image/jpeg,image/webp"
          aria-label={`Bild für ${item.name} hochladen`}
          disabled={uploadMutation.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) uploadMutation.mutate(file);
            event.target.value = "";
          }}
          type="file"
        />
        {item.image_url && (
          <button className="text-button text-button--danger" disabled={removeImageMutation.isPending} onClick={() => removeImageMutation.mutate()} type="button">Bild entfernen</button>
        )}
      </div>
      <form className="manager-form-grid drink-menu-admin-item__fields" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
        <label className="profile-field"><span>Name</span><input maxLength={80} onChange={(event) => setName(event.target.value)} required value={name} /></label>
        <label className="profile-field"><span>Gruppe</span><input maxLength={80} onChange={(event) => setGroupLabel(event.target.value)} value={groupLabel} /></label>
        <label className="profile-field"><span>Menge</span><input maxLength={40} onChange={(event) => setVolume(event.target.value)} value={volume} /></label>
        <label className="profile-field"><span>Preis (€)</span><input min="0" onChange={(event) => setPrice(event.target.value)} placeholder="ohne Preis" step="0.01" type="number" value={price} /></label>
        <label className="profile-field manager-form-grid__wide"><span>Beschreibung</span><input maxLength={200} onChange={(event) => setDescription(event.target.value)} value={description} /></label>
        <label className="manager-checkbox"><input checked={showPrice} onChange={(event) => setShowPrice(event.target.checked)} type="checkbox" /><span>Preis anzeigen</span></label>
        <label className="profile-field"><span>Sortierung</span><input min="0" onChange={(event) => setSortOrder(event.target.value)} type="number" value={sortOrder} /></label>
        <label className="manager-checkbox"><input checked={active} onChange={(event) => setActive(event.target.checked)} type="checkbox" /><span>Sichtbar</span></label>
        <div className="finance-inline-actions">
          <button className="text-button" disabled={saveMutation.isPending} type="submit">Speichern</button>
          {item.is_active && <button className="text-button text-button--danger" disabled={deactivateMutation.isPending} onClick={() => deactivateMutation.mutate()} type="button">Ausblenden</button>}
        </div>
      </form>
    </article>
  );
}
