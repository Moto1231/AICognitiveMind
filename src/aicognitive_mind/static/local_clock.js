(() => {
  const clocks = Array.from(document.querySelectorAll("[data-local-clock]"));
  if (!clocks.length) return;

  const dateFormatter = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const timeFormatter = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local time";

  function updateClocks() {
    const now = new Date();
    const dateText = dateFormatter.format(now);
    const timeText = timeFormatter.format(now);

    for (const clock of clocks) {
      const dateNode = clock.querySelector("[data-local-clock-date]");
      const timeNode = clock.querySelector("[data-local-clock-time]");
      if (dateNode) dateNode.textContent = dateText;
      if (timeNode) timeNode.textContent = timeText;
      clock.dateTime = now.toISOString();
      clock.title = `Current local date and time (${timeZone})`;
      clock.setAttribute("aria-label", `${dateText}, ${timeText}, ${timeZone}`);
    }
  }

  updateClocks();
  window.setInterval(updateClocks, 1_000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) updateClocks();
  });
})();
