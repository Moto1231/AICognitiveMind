(() => {
  if (document.documentElement.dataset.axiomButtonIcons === 'ready') return;
  document.documentElement.dataset.axiomButtonIcons = 'ready';

  const controlSelector = 'button, a.primary-button, a.secondary-button, a[role="button"], #backToPortal, [data-icon-button]';
  const customIconSelector = 'svg:not(.axiom-button-icon), img, picture, canvas, i, [data-icon], .admin-section-icon, .icon, .material-icons, .material-symbols-outlined, .fa, .fas, .far, .fab';
  const nonLabelSelector = 'svg, img, picture, canvas, i, script, style, [data-icon], .admin-section-icon, .icon, .material-icons, .material-symbols-outlined, .fa, .fas, .far, .fab, [aria-hidden="true"]';
  const svgNamespace = 'http://www.w3.org/2000/svg';
  const states = new WeakMap();
  const shapes = {
    save: 'M7 5h18l6 6v22H7z M12 5v11h14V5 M12 33V21h14v12',
    refresh: 'M30 13a13 13 0 0 0-22 4 M8 8v9h9 M10 27a13 13 0 0 0 22-5 M32 31v-9h-9',
    back: 'M29 20H10 M19 10 9 20l10 10',
    forward: 'M11 20h19 M21 10l10 10-10 10',
    add: 'M20 9v22 M9 20h22',
    remove: 'M9 11h22 M15 11V6h10v5 M12 11l2 23h12l2-23 M18 16v12 M23 16v12',
    clear: 'm10 29 16-19 6 5-16 19z M8 34h22',
    send: 'm5 19 29-13-9 28-6-11-14-4z M19 23 34 6',
    vision: 'M4 20q16-20 32 0-16 20-32 0z M26 20a6 6 0 1 1-12 0 6 6 0 0 1 12 0',
    hearing: 'M15 28c-1-5-6-5-6-13a11 11 0 0 1 22 0c0 8-5 10-9 15-4 5-11 4-11-1 M24 14c-2-4-9-3-9 3',
    voice: 'M15 12a5 5 0 0 1 10 0v9a5 5 0 0 1-10 0z M10 18a10 10 0 0 0 20 0 M20 28v6 M13 34h14',
    logout: 'M21 7H9v26h12 M26 12l9 8-9 8 M35 20H17',
    login: 'M21 7h10v26H21 M14 12l9 8-9 8 M23 20H5',
    home: 'm5 18 15-13 15 13 M10 16v18h20V16 M17 34V23h6v11',
    settings: 'M20 5v5 M20 30v5 M5 20h5 M30 20h5 M9 9l4 4 M27 27l4 4 M9 31l4-4 M27 13l4-4 M30 20a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M24 20a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    search: 'M26 17a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M24 25l10 10',
    edit: 'm8 27-2 8 8-2L32 15l-6-6z M22 13l6 6',
    close: 'M10 10l20 20 M30 10 10 30',
    play: 'm14 8 19 12-19 12z',
    stop: 'M10 10h20v20H10z',
    camera: 'M6 12h8l3-5h8l3 5h6v21H6z M26 22a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
    more: 'M10 10h20 M10 19h20 M10 28h12 M29 25v10 M24 30h10',
    approve: 'm8 21 8 8L33 11',
    download: 'M20 5v22 M12 19l8 8 8-8 M7 29v6h26v-6',
    upload: 'M20 28V6 M12 14l8-8 8 8 M7 29v6h26v-6',
    copy: 'M14 13h19v22H14z M25 13V5H6v22h8',
    happy: 'M34 20a14 14 0 1 1-28 0 14 14 0 0 1 28 0 M14 15h1 M25 15h1 M12 24q8 10 16 0',
    neutral: 'M34 20a14 14 0 1 1-28 0 14 14 0 0 1 28 0 M14 15h1 M25 15h1 M13 26h14',
    mind: 'M15 7c-8-3-12 8-7 12-5 6 0 15 7 12 M25 7c8-3 12 8 7 12 5 6 0 15-7 12 M20 5v30 M9 17h6v8 M31 17h-6v8 M13 10l7 5 7-5',
    coding: 'm14 12-9 8 9 8 M26 12l9 8-9 8 M23 7l-6 26',
    image: 'M6 7h28v26H6z M6 28l10-11 8 9 4-5 6 7 M27 13h.1',
    summary: 'M10 5h15l7 7v23H10z M25 5v8h7 M15 20h12 M15 26h12',
    memory: 'M7 12c0-8 26-8 26 0v16c0 8-26 8-26 0z M7 12c0 8 26 8 26 0 M7 20c0 8 26 8 26 0',
    web: 'M35 20a15 15 0 1 1-30 0 15 15 0 0 1 30 0 M5 20h30 M20 5c-10 8-10 22 0 30 M20 5c10 8 10 22 0 30',
    structure: 'M6 7h28v26H6z M6 16h28 M6 25h28 M16 7v26',
    action: 'M8 20h1 M19 20h1 M30 20h1 M7 7h26v26H7z',
  };

  const styles = document.createElement('style');
  styles.textContent = `
    .axiom-icon-button { align-items: center; justify-content: center; gap: 0; min-inline-size: 44px; min-block-size: 44px; }
    .axiom-icon-button:not(.hidden):not([hidden]) { display: inline-flex; }
    [data-icon-button].axiom-icon-button:not(.hidden):not([hidden]) { display: inline-flex !important; }
    .axiom-icon-button.hidden, .axiom-icon-button[hidden] { display: none; }
    .axiom-button-icon { width: 28px; height: 28px; flex: none; color: #83dffe; filter: drop-shadow(0 0 3px rgba(70,182,255,.65)); }
    .axiom-icon-button[aria-pressed="false"] .axiom-button-icon { opacity: .75; }
    .axiom-icon-button:disabled { opacity: .5; cursor: not-allowed; }
    .axiom-icon-button:focus-visible { outline: 2px solid #83dffe; outline-offset: 3px; }
    .axiom-icon-button .axiom-button-label { position: absolute !important; width: 1px !important; height: 1px !important; padding: 0 !important; margin: -1px !important; overflow: hidden !important; clip: rect(0,0,0,0) !important; clip-path: inset(50%) !important; white-space: nowrap !important; border: 0 !important; }
    .axiom-icon-button .axiom-button-text-container { display: contents; }
    .axiom-button-tooltip { position: fixed; z-index: 2147483647; box-sizing: border-box; width: max-content; max-width: calc(100vw - 16px); max-height: calc(100vh - 16px); overflow-y: auto; padding: 8px 11px; border: 1px solid #4f91b5; border-radius: 7px; background: #102231; color: #e7f7ff; box-shadow: 0 4px 18px rgba(0,0,0,.4); font: 14px/1.4 system-ui, sans-serif; overflow-wrap: anywhere; pointer-events: auto; }
    .axiom-button-tooltip[hidden] { display: none; }
    @media (max-width: 500px) { .axiom-button-icon { width: 26px; height: 26px; } }
  `;
  document.head.appendChild(styles);

  function matchIcon(label) {
    const text = label.toLowerCase();
    const taskIcons = {
      reasoning: 'mind', vision: 'vision', 'audio/transcription': 'hearing', 'audio/voice': 'voice',
      coding: 'coding', 'drawing & image generation': 'image', summarizing: 'summary',
      'memory recall': 'memory', 'web research': 'web', 'structured extraction': 'structure',
    };
    if (taskIcons[text]) return [taskIcons[text], false];
    const toggle = /^(vision|hearing|voice) (on|off)$/.exec(text);
    if (toggle) return [toggle[1], toggle[2] === 'off'];
    if (/log ?out|sign out/.test(text)) return ['logout', false];
    if (/^existing axiom$/.test(text)) return ['login', false];
    if (/log ?in|sign in/.test(text)) return ['login', false];
    if (/^connect\b/.test(text)) return ['approve', false];
    if (/^live$/.test(text)) return ['play', false];
    if (/^(go back|back|return)\b/.test(text)) return ['back', false];
    if (/^main$|^home$/.test(text)) return ['home', false];
    if (/^administration$|\bsettings\b/.test(text)) return ['settings', false];
    if (/^(save|saving)\b/.test(text)) return ['save', false];
    if (/^(refresh|refreshing|reload|query)\b/.test(text)) return ['refresh', false];
    if (/^(add|create|sign up|register)\b/.test(text)) return ['add', false];
    if (/^(remove|delete|erase)\b/.test(text)) return ['remove', false];
    if (/^clear\b/.test(text)) return ['clear', false];
    if (/^(send|sending)\b/.test(text)) return ['send', false];
    if (/^(close|cancel|deny|reject)\b|^[×✕✖]$/.test(text)) return ['close', false];
    if (/^(edit|rename)\b/.test(text)) return ['edit', false];
    if (/^(discover|search|find)\b/.test(text)) return ['search', false];
    if (/^(get more|load more|more)\b/.test(text)) return ['more', false];
    if (/^(stop|pause)\b/.test(text)) return ['stop', false];
    if (/\b(camera|capture|frame)\b/.test(text)) return ['camera', false];
    if (/\b(listen|listening|hearing)\b/.test(text)) return ['hearing', false];
    if (/\b(speak|speech|voice|audio_voice)\b/.test(text)) return ['voice', false];
    if (/\bvision\b/.test(text)) return ['vision', false];
    if (/^(start|run|play)\b/.test(text)) return ['play', false];
    if (/^(allow|approve|authorize|confirm|accept)\b/.test(text)) return ['approve', false];
    if (/^(continue|next|open|enter)\b/.test(text)) return ['forward', false];
    if (/^download\b/.test(text)) return ['download', false];
    if (/^upload\b/.test(text)) return ['upload', false];
    if (/^copy\b/.test(text)) return ['copy', false];
    if (/^happy$/.test(text)) return ['happy', false];
    if (/^neutral$/.test(text)) return ['neutral', false];
    if (/\b(genesis|reasoning|mind)\b/.test(text)) return ['mind', false];
    return ['action', false];
  }

  function createIcon(type, off) {
    const svg = document.createElementNS(svgNamespace, 'svg');
    for (const [name, value] of Object.entries({ 'aria-hidden': 'true', focusable: 'false', class: 'axiom-button-icon', viewBox: '0 0 40 40', width: '28', height: '28' })) svg.setAttribute(name, value);
    const group = document.createElementNS(svgNamespace, 'g');
    for (const [name, value] of Object.entries({ fill: 'none', stroke: 'currentColor', 'stroke-width': '2.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })) group.setAttribute(name, value);
    const halo = document.createElementNS(svgNamespace, 'path');
    halo.setAttribute('opacity', '.55');
    halo.setAttribute('d', 'M5 12A17 17 0 0 1 28 5 M35 28A17 17 0 0 1 12 35');
    group.appendChild(halo);
    const symbol = document.createElementNS(svgNamespace, 'path');
    symbol.setAttribute('d', shapes[type]);
    group.appendChild(symbol);
    if (off) {
      const slash = document.createElementNS(svgNamespace, 'path');
      slash.setAttribute('d', 'M8 33 32 7');
      slash.setAttribute('stroke-width', '3.5');
      group.appendChild(slash);
    }
    svg.appendChild(group);
    const light = document.createElementNS(svgNamespace, 'circle');
    for (const [name, value] of Object.entries({ cx: '33', cy: '9', r: '1.4', fill: 'currentColor' })) light.setAttribute(name, value);
    svg.appendChild(light);
    return svg;
  }

  // Keep text nodes and child elements: application code still reads and replaces
  // button.textContent, and existing child listeners retain their identity.
  function labelNodes(control) {
    const nodes = [];
    const walker = document.createTreeWalker(control, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.parentElement.closest(nonLabelSelector)) nodes.push(node);
    }
    return nodes;
  }

  function normalize(text) { return text.trim().replace(/\s+/g, ' '); }

  function decorate(control) {
    const state = states.get(control) || { generatedLabel: null, signature: null };
    const nodes = labelNodes(control);
    const text = nodes.map(node => normalize(node.nodeValue)).filter(Boolean).join(' ');
    const currentAriaLabel = control.getAttribute('aria-label');
    const explicitAriaLabel = currentAriaLabel !== state.generatedLabel ? currentAriaLabel : null;
    const labelledBy = (control.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => document.getElementById(id)).filter(Boolean)
      .map(element => normalize(element.textContent)).join(' ');
    // Native titles would display a second tooltip over the shared one. Cache
    // authored titles, including later updates, before removing that browser UI.
    if (control.hasAttribute('title')) {
      state.title = normalize(control.getAttribute('title'));
      control.removeAttribute('title');
    }
    const title = state.title || '';
    const image = control.querySelector('img[alt]');
    const label = labelledBy || explicitAriaLabel || text || title || (image && normalize(image.alt)) || state.label || 'Action';
    state.label = label;
    state.tooltip = title || label;

    // Labels created here follow dynamic text updates. Explicit labels such as
    // "Close journal inspector" continue to name their original controls.
    if (!explicitAriaLabel && !labelledBy) {
      if (currentAriaLabel !== label) control.setAttribute('aria-label', label);
      state.generatedLabel = label;
    } else {
      state.generatedLabel = null;
    }
    for (const node of nodes) {
      if (!node.nodeValue.trim() || node.parentElement.classList.contains('axiom-button-label')) continue;
      const span = document.createElement('span');
      span.className = 'axiom-button-label';
      node.replaceWith(span);
      span.appendChild(node);
    }
    for (const element of control.querySelectorAll('strong, span, small')) {
      if (element.classList.contains('axiom-button-label') || element.matches(customIconSelector)
        || element.querySelector(customIconSelector) || !element.querySelector('.axiom-button-label')) continue;
      element.classList.add('axiom-button-text-container');
    }
    const existing = control.querySelector(':scope > .axiom-button-icon');
    if (control.querySelector(customIconSelector)) {
      if (existing) existing.remove();
      state.signature = null;
    } else {
      const taskTitle = control.matches('.task-profile-card') && control.querySelector('strong');
      const [type, off] = matchIcon(taskTitle ? normalize(taskTitle.textContent) : label);
      const signature = `${type}:${off}`;
      if (!existing || state.signature !== signature) {
        if (existing) existing.remove();
        control.prepend(createIcon(type, off));
      }
      state.signature = signature;
    }
    control.classList.add('axiom-neon-button', 'axiom-icon-button');
    states.set(control, state);
  }

  let tooltip;
  let tooltipButton = null;
  let hoveredButton = null;
  let focusedButton = null;
  let dismissedButton = null;
  let overTooltip = false;
  let hideTimer;

  function available(control) {
    return control && control.isConnected && !control.closest('[hidden], .hidden') && control.getClientRects().length > 0
      && getComputedStyle(control).visibility !== 'hidden';
  }

  function removeDescription(control) {
    if (!control) return;
    const ids = (control.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== tooltip.id);
    if (ids.length) control.setAttribute('aria-describedby', ids.join(' '));
    else control.removeAttribute('aria-describedby');
  }

  function hideTooltip() {
    clearTimeout(hideTimer);
    removeDescription(tooltipButton);
    tooltipButton = null;
    overTooltip = false;
    tooltip.hidden = true;
  }

  function positionTooltip() {
    if (!tooltipButton) return;
    if (!available(tooltipButton)) { hideTooltip(); return; }
    const rect = tooltipButton.getBoundingClientRect();
    const tip = tooltip.getBoundingClientRect();
    const width = document.documentElement.clientWidth;
    const height = document.documentElement.clientHeight;
    const left = Math.max(8, Math.min(rect.left + (rect.width - tip.width) / 2, width - tip.width - 8));
    const below = rect.bottom + 8;
    const top = below + tip.height <= height - 8 ? below : Math.max(8, rect.top - tip.height - 8);
    tooltip.style.left = `${Math.round(left)}px`;
    tooltip.style.top = `${Math.round(Math.min(top, Math.max(8, height - tip.height - 8)))}px`;
  }

  function showTooltip(control) {
    clearTimeout(hideTimer);
    if (!available(control) || dismissedButton === control) return;
    if (tooltipButton !== control) removeDescription(tooltipButton);
    tooltipButton = control;
    tooltip.textContent = states.get(control).tooltip;
    tooltip.hidden = false;
    const ids = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    ids.add(tooltip.id);
    control.setAttribute('aria-describedby', [...ids].join(' '));
    positionTooltip();
  }

  function deferHide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (overTooltip && available(tooltipButton)) return;
      const control = available(hoveredButton) ? hoveredButton : focusedButton;
      if (available(control) && dismissedButton !== control) showTooltip(control);
      else hideTooltip();
    }, 140);
  }

  function eventControl(target) {
    return target instanceof Element ? target.closest('.axiom-icon-button') : null;
  }

  function initTooltip() {
    tooltip = document.createElement('div');
    let suffix = 0;
    do { tooltip.id = `axiom-button-tooltip${suffix ? `-${suffix}` : ''}`; suffix += 1; }
    while (document.getElementById(tooltip.id));
    tooltip.className = 'axiom-button-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    // Delegation also covers controls created after the first render.
    document.addEventListener('pointerover', event => {
      const control = eventControl(event.target);
      if (!control || control.contains(event.relatedTarget)) return;
      hoveredButton = control;
      showTooltip(control);
    });
    document.addEventListener('pointerout', event => {
      const control = eventControl(event.target);
      if (!control || control.contains(event.relatedTarget)) return;
      if (hoveredButton === control) hoveredButton = null;
      if (dismissedButton === control && focusedButton !== control) dismissedButton = null;
      deferHide();
    });
    document.addEventListener('focusin', event => {
      const control = eventControl(event.target);
      if (!control) return;
      focusedButton = control;
      if (dismissedButton !== control) dismissedButton = null;
      showTooltip(control);
    });
    document.addEventListener('focusout', event => {
      const control = eventControl(event.target);
      if (!control || control.contains(event.relatedTarget)) return;
      if (focusedButton === control) focusedButton = null;
      if (dismissedButton === control && hoveredButton !== control) dismissedButton = null;
      deferHide();
    });
    tooltip.addEventListener('pointerenter', () => { overTooltip = true; clearTimeout(hideTimer); });
    tooltip.addEventListener('pointerleave', () => { overTooltip = false; deferHide(); });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || !tooltipButton) return;
      dismissedButton = tooltipButton;
      hideTooltip();
    });
    window.addEventListener('resize', positionTooltip);
    document.addEventListener('scroll', positionTooltip, true);
  }

  const observerOptions = {
    subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['aria-label', 'aria-labelledby', 'title', 'disabled', 'aria-disabled', 'class', 'hidden', 'aria-pressed', 'role'],
  };
  let pending = false;
  const observer = new MutationObserver(records => {
    if (records.every(record => record.target === tooltip || tooltip.contains(record.target))) return;
    if (!pending) { pending = true; queueMicrotask(apply); }
  });

  function apply() {
    pending = false;
    // Wrapping text and updating our SVGs must not trigger another observer pass.
    observer.disconnect();
    try {
      document.querySelectorAll(controlSelector).forEach(decorate);
      if (tooltipButton) {
        if (available(tooltipButton)) {
          tooltip.textContent = states.get(tooltipButton).tooltip;
          positionTooltip();
        } else hideTooltip();
      }
    } finally {
      observer.observe(document.body, observerOptions);
    }
  }

  function init() { initTooltip(); apply(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
