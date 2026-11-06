"use client";

import { useState } from "react";

const sections = ["Models", "Tools", "Skills", "Behaviors", "Vision", "Audio"] as const;
type Section = (typeof sections)[number];
type SkillName = "Axiom Continuity" | "Axiom Current State" | "Memory Steward";
type SkillSettings = { enabled: boolean; required: boolean; protected: boolean; instructions: string };

const initialSettings = {
  modelTask: "Memory Recall", engine: "Engine A", server: "Project tools", tool: "Read document",
  serverEnabled: true, toolEnabled: true, behaviorTask: "Reasoning", behaviorName: "Evidence-led responses",
  behaviorEnabled: true, behaviorInstructions: "Use supplied evidence. Keep unresolved context explicit. Verify results before reporting success.",
  visionEngine: "Engine B", cameraPermission: "Not granted", audioTask: "Audio / Transcription",
  audioEngine: "Engine A", audioInput: "Microphone", voiceReference: "",
};

function initialSkills(): Record<SkillName, SkillSettings> {
  return {
    "Axiom Continuity": { enabled: true, required: true, protected: true, instructions: "Preserve the supported interaction context and follow the effective interaction lifecycle." },
    "Axiom Current State": { enabled: true, required: true, protected: true, instructions: "Keep supported state current. Preserve uncertainty and evidence when context changes." },
    "Memory Steward": { enabled: true, required: false, protected: false, instructions: "Select durable learning from the interaction and validate its supporting evidence." },
  };
}

const descriptions: Record<Section, { title: string; path: string; description: string }> = {
  Models: { title: "Endpoints & Models", path: "Task Configuration", description: "Assign an endpoint to a task. Set the recovery path independently of normal provider priority." },
  Tools: { title: "MCP Servers & Tools", path: "Endpoints, Servers & Tools", description: "Connect a tool server, discover its operations, and choose which tools are enabled." },
  Skills: { title: "Skill configuration", path: "Skills", description: "Edit the effective instructions and settings used by the Mind." },
  Behaviors: { title: "Behavior configuration", path: "Behaviors", description: "Author a behavior centrally, then select it for the tasks that need it." },
  Vision: { title: "Vision task routing", path: "Task Configuration / Vision", description: "Choose the endpoint that interprets visual input. Device permission remains a separate control." },
  Audio: { title: "Audio task routing", path: "Task Configuration / Audio", description: "Configure transcription and speech synthesis as separate task assignments." },
};

export default function Configuration() {
  const [section, setSection] = useState<Section>("Models");
  const [settings, setSettings] = useState(initialSettings);
  const [skill, setSkill] = useState<SkillName>("Axiom Continuity");
  const [skills, setSkills] = useState(initialSkills);
  const change = (patch: Partial<typeof initialSettings>) => setSettings(previous => ({ ...previous, ...patch }));
  const changeSkill = (patch: Partial<SkillSettings>) => setSkills(previous => ({ ...previous, [skill]: { ...previous[skill], ...patch } }));
  const current = descriptions[section];
  const fallback = settings.engine === "Engine A" ? "Engine B" : "Engine A";
  const summary: [string, string][] = section === "Models"
    ? [["Task", settings.modelTask], ["Primary endpoint", settings.engine], ["Fallback endpoint", fallback], ["Provider order", "Failure-triggered"]]
    : section === "Tools"
      ? [["MCP server", settings.server], ["Server", settings.serverEnabled ? "Enabled" : "Disabled"], ["Tool", settings.tool], ["Tool access", settings.serverEnabled && settings.toolEnabled ? "Enabled" : "Disabled"]]
      : section === "Skills"
        ? [["Skill", skill], ["Enabled", skills[skill].enabled ? "Yes" : "No"], ["Required", skills[skill].required ? "Yes" : "No"], ["Protected", skills[skill].protected ? "Yes" : "No"]]
        : section === "Behaviors"
          ? [["Behavior", settings.behaviorName || "Untitled example"], ["Selected task", settings.behaviorTask], ["Status", settings.behaviorEnabled ? "Enabled" : "Disabled"]]
          : section === "Vision"
            ? [["Task", "Vision"], ["Endpoint", settings.visionEngine], ["Camera permission", settings.cameraPermission]]
            : [["Task", settings.audioTask], ["Endpoint", settings.audioEngine], [settings.audioTask === "Audio / Voice" ? "Voice reference" : "Example input", settings.audioTask === "Audio / Voice" ? settings.voiceReference || "Provider default" : settings.audioInput]];

  return <div className="configuration-demo">
    <div className="configuration-toolbar">
      <span className="configuration-window-mark" aria-hidden="true"><i /><i /><i /></span>
      <span>AXIOM / ADMINISTRATION</span>
      <span className="configuration-sample">Interactive configuration preview · sample data</span>
    </div>
    <div className="configuration-body">
      <nav className="configuration-nav" aria-label="Example configuration sections">
        {sections.map((item, index) => <button type="button" key={item} aria-pressed={section === item} onClick={() => setSection(item)}><span aria-hidden="true">0{index + 1}</span>{item}</button>)}
      </nav>
      <div className="configuration-panel" aria-labelledby="configuration-panel-heading">
        <p className="configuration-path">{current.path}</p>
        <h3 id="configuration-panel-heading">{current.title}</h3>
        <p className="configuration-description">{current.description}</p>

        {section === "Models" && <>
          <label className="configuration-field">Task<select value={settings.modelTask} onChange={event => change({ modelTask: event.target.value })}><option>Memory Recall</option><option>Reasoning</option><option>Coding</option></select></label>
          <label className="configuration-field">Primary endpoint<select value={settings.engine} onChange={event => change({ engine: event.target.value })}><option>Engine A</option><option>Engine B</option></select></label>
          <div className="configuration-static"><span>Fallback endpoint</span><strong>{fallback}</strong></div>
          <p className="configuration-hint">A successful provider stays in use. A failure advances to the next eligible fallback, within the configured limits.</p>
        </>}

        {section === "Tools" && <>
          <label className="configuration-field">Configured server<select value={settings.server} onChange={event => change({ server: event.target.value })}><option>Project tools</option><option>Research tools</option></select></label>
          <label className="configuration-toggle"><input type="checkbox" checked={settings.serverEnabled} onChange={event => change({ serverEnabled: event.target.checked })} /><span>Enable this server</span></label>
          <label className="configuration-field">Tool<select value={settings.tool} onChange={event => change({ tool: event.target.value })}><option>Read document</option><option>Search files</option></select></label>
          <label className="configuration-toggle"><input type="checkbox" checked={settings.toolEnabled} onChange={event => change({ toolEnabled: event.target.checked })} /><span>Enable this tool</span></label>
          <p className="configuration-hint">MCP Servers → Tools is separate from Endpoints → Models. These example names do not identify connected services.</p>
        </>}

        {section === "Skills" && <>
          <label className="configuration-field">Skill<select value={skill} onChange={event => setSkill(event.target.value as SkillName)}>{Object.keys(skills).map(name => <option key={name}>{name}</option>)}</select></label>
          <div className="configuration-toggle-group">
            <label className="configuration-toggle"><input type="checkbox" checked={skills[skill].enabled} onChange={event => changeSkill({ enabled: event.target.checked })} /><span>Enabled</span></label>
            <label className="configuration-toggle"><input type="checkbox" checked={skills[skill].required} onChange={event => changeSkill({ required: event.target.checked })} /><span>Required</span></label>
            <label className="configuration-toggle"><input type="checkbox" checked={skills[skill].protected} onChange={event => changeSkill({ protected: event.target.checked })} /><span>Protected</span></label>
          </div>
          <label className="configuration-field">Instructions<textarea rows={3} value={skills[skill].instructions} onChange={event => changeSkill({ instructions: event.target.value })} /></label>
          <p className="configuration-hint">The authenticated Administrator can edit the instructions and all three settings. Protected does not lock the Administrator out.</p>
        </>}

        {section === "Behaviors" && <>
          <label className="configuration-field">Behavior name<input type="text" maxLength={120} value={settings.behaviorName} onChange={event => change({ behaviorName: event.target.value })} /></label>
          <label className="configuration-field">Selected task<select value={settings.behaviorTask} onChange={event => change({ behaviorTask: event.target.value })}><option>Reasoning</option><option>Coding</option><option>Memory Recall</option></select></label>
          <label className="configuration-field">Instructions<textarea rows={3} maxLength={4000} value={settings.behaviorInstructions} onChange={event => change({ behaviorInstructions: event.target.value })} /></label>
          <label className="configuration-toggle"><input type="checkbox" checked={settings.behaviorEnabled} onChange={event => change({ behaviorEnabled: event.target.checked })} /><span>Enable behavior</span></label>
          <p className="configuration-hint">Behavior authoring and task assignment are separate controls in Administration.</p>
        </>}

        {section === "Vision" && <>
          <div className="configuration-static"><span>Task</span><strong>Vision</strong></div>
          <label className="configuration-field">Endpoint<select value={settings.visionEngine} onChange={event => change({ visionEngine: event.target.value })}><option>Engine A</option><option>Engine B</option></select></label>
          <label className="configuration-field">Example camera permission<select value={settings.cameraPermission} onChange={event => change({ cameraPermission: event.target.value })}><option>Not granted</option><option>Granted</option></select></label>
          <p className="configuration-hint">Live vision requires an authorized Body path, device permission and a compatible provider. Account-scoped Body access is currently restricted.</p>
        </>}

        {section === "Audio" && <>
          <label className="configuration-field">Task<select value={settings.audioTask} onChange={event => change({ audioTask: event.target.value })}><option>Audio / Transcription</option><option>Audio / Voice</option></select></label>
          <label className="configuration-field">Endpoint<select value={settings.audioEngine} onChange={event => change({ audioEngine: event.target.value })}><option>Engine A</option><option>Engine B</option></select></label>
          {settings.audioTask === "Audio / Voice"
            ? <label className="configuration-field">Voice / reference ID<input type="text" maxLength={200} placeholder="Optional example reference" value={settings.voiceReference} onChange={event => change({ voiceReference: event.target.value })} /></label>
            : <label className="configuration-field">Example input<select value={settings.audioInput} onChange={event => change({ audioInput: event.target.value })}><option>Microphone</option><option>Audio file</option></select></label>}
          <p className="configuration-hint">Transcription and speech synthesis use separate assignments. Actual audio requires the supported service path, provider and device permissions.</p>
        </>}
      </div>
      <aside className="configuration-readout" aria-label="Example configuration summary">
        <p className="configuration-path">CURRENT EXAMPLE</p>
        <h4>{section}</h4>
        <dl>{summary.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        <span className="configuration-local">Browser-local changes</span>
        <button type="button" className="configuration-reset" onClick={() => { setSettings({ ...initialSettings }); setSkills(initialSkills()); setSkill("Axiom Continuity"); }}>Reset example</button>
      </aside>
    </div>
    <p className="configuration-caption">Illustrated configuration controls · sample data. Changes stay in this example; no Axiom accounts, devices or settings are changed.</p>
  </div>;
}
