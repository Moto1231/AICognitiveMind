"use client";

import { useState } from "react";

const captures = [
  {
    id: "overview",
    label: "Overview",
    icon: "/admin-icons/admin-overview.svg",
    src: "/screenshots/overview.jpg",
    alt: "Provided Axiom overview capture showing durable memory and interaction history totals.",
    title: "See stored context and interaction history",
    description: "The overview brings memory and recorded interaction totals together. The numbers shown belong to this supplied example.",
  },
  {
    id: "behaviors",
    label: "Behaviors",
    icon: "/admin-icons/admin-behavior.svg",
    src: "/screenshots/behaviors.jpg",
    alt: "Provided Administration capture showing behavior names, priorities, instruction editors and enabled controls.",
    title: "Edit the instructions that shape interactions",
    description: "Give a behavior a name, set its priority, edit its instructions and choose whether it is enabled. The capture shows the controls and example instruction text.",
  },
  {
    id: "memories",
    label: "Memories",
    icon: "/admin-icons/admin-memories.svg",
    src: "/screenshots/memories.jpg",
    alt: "Provided Administration capture showing memory search, class and date filters, and example memory records.",
    title: "Find and inspect retained memories",
    description: "Search stored content and filter by memory class, association, grounding or date. Open a result to inspect its record; the visible entries are supplied examples.",
  },
  {
    id: "task-routing",
    label: "Task routing",
    icon: "/admin-icons/admin-task-profiles.svg",
    src: "/screenshots/task-routing.jpg",
    alt: "Provided Audio and Transcription task editor with endpoint settings, a masked API key, model assignment and ordered fallback fields.",
    title: "Configure models and recovery paths per task",
    description: "Choose an endpoint, assign a model and arrange fallback provider/model pairs. This Audio/Transcription example illustrates the fields; its provider and model choices are not verified recommendations.",
  },
] as const;

export default function Screenshots() {
  const [selectedId, setSelectedId] = useState<(typeof captures)[number]["id"]>("behaviors");
  const selected = captures.find((capture) => capture.id === selectedId) ?? captures[1];

  return (
    <div className="screenshot-gallery">
      <div className="screenshot-intro">
        <p className="screenshot-kicker">SUPPLIED PRODUCT VIEWS</p>
        <h3>Inside Administration</h3>
        <p className="screenshot-note">Provided interface captures. Navigation, totals and example settings can differ from the current release.</p>
      </div>

      <div className="screenshot-tabs" role="group" aria-label="Administration screenshot views">
        {captures.map((capture) => (
          <button
            className="screenshot-tab"
            key={capture.id}
            type="button"
            aria-pressed={selected.id === capture.id}
            aria-controls="administration-capture"
            onClick={() => setSelectedId(capture.id)}
          >
            <img className="screenshot-tab-art" src={capture.icon} alt="" aria-hidden="true" width="48" height="48" />
            <span>{capture.label}</span>
          </button>
        ))}
      </div>

      <figure className="screenshot-figure" id="administration-capture" aria-labelledby="screenshot-title">
        <div className="screenshot-image-frame">
          <img className="screenshot-image" src={selected.src} alt={selected.alt} loading="lazy" decoding="async" />
        </div>
        <figcaption className="screenshot-caption">
          <div className="screenshot-description" aria-live="polite" aria-atomic="true">
            <h4 id="screenshot-title">{selected.title}</h4>
            <p>{selected.description}</p>
          </div>
          <a className="screenshot-full-link" href={selected.src} target="_blank" rel="noreferrer" aria-label={`Open full ${selected.label.toLowerCase()} image in a new tab`}>
            Open full image <span aria-hidden="true">↗</span>
          </a>
        </figcaption>
      </figure>
    </div>
  );
}
