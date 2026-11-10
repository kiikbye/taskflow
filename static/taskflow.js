"use strict";

const overview = document.querySelector("#live");
if (overview) {
  const element = (id) => document.getElementById(id);
  const connection = element("connection");
  const formatter = new Intl.NumberFormat("kk-KZ");
  const write = (id, value) => { element(id).textContent = value; };

  function node(tag, value, className) {
    const item = document.createElement(tag);
    if (value !== undefined) item.textContent = value;
    if (className) item.className = className;
    return item;
  }

  function render(data) {
    connection.textContent = data.finished ? "Аяқталды" : "Жаңартылып жатыр";
    connection.classList.toggle("live", !data.finished);
    for (const key of Object.keys(data.states)) {
      overview.querySelector('[data-state="' + key + '"]').textContent = data.states[key];
    }
    element("progress").max = data.tasks.length || 1;
    element("progress").value = data.states.done + data.states.failed;
    write("elapsed", formatter.format(data.elapsed) + " с");
    write("workers", data.workers);
    write("peak", data.peak);
    write("retries", data.retries);
    write("rate", formatter.format(data.rate) + " тапсырма/с");
    write("result", data.result === null ? "—" : formatter.format(data.result));
    if (element("publish")) element("publish").disabled = data.result === null;

    const table = document.createDocumentFragment();
    const timeline = document.createDocumentFragment();
    const axis = Math.max(1, Math.ceil(data.elapsed));
    let hasAttempts = false;
    write("axis-end", axis + " с");

    for (const task of data.tasks) {
      const row = node("tr");
      const latest = task.attempts.at(-1);
      row.append(
        node("td", "#" + task.shard),
        node("td", task.label, "state " + task.state),
        node("td", task.attempts.length),
        node("td", latest?.worker ?? "—"),
        node("td", task.result === null ? "—" : formatter.format(task.result)),
      );
      table.append(row);

      for (const attempt of task.attempts) {
        hasAttempts = true;
        const label = "#" + task.shard + " · " + attempt.number;
        const line = node("div", undefined, "timeline-row");
        const track = node("div", undefined, "timeline-track");
        const style = attempt.active ? "" : attempt.state === "Дайын" ? " done" : " retry";
        const bar = node("span", undefined, "timeline-bar" + style);
        const start = Math.max(1, Math.min(100, 1 + Math.floor(attempt.start * 100 / axis)));
        const end = Math.max(start + 1, Math.min(101, 1 + Math.ceil(attempt.end * 100 / axis)));
        bar.style.gridColumn = start + " / " + end;
        bar.title = attempt.worker + " · " + attempt.state + " · " + attempt.start + "–" + attempt.end + " с";
        bar.setAttribute("aria-label", label + " · " + bar.title);
        bar.setAttribute("role", "img");
        track.append(bar);
        line.append(node("span", label, "timeline-label"), track);
        timeline.append(line);
      }
    }
    if (!hasAttempts) timeline.append(node("p", "Алғашқы worker күтілуде.", "muted small"));
    element("tasks").replaceChildren(table);
    element("timeline").replaceChildren(timeline);
  }

  async function refresh() {
    try {
      const response = await fetch(overview.dataset.url, { headers: { Accept: "application/json" }, cache: "no-store" });
      if ([401, 403].includes(response.status)) {
        connection.classList.remove("live");
        connection.textContent = "Қолжетімділік аяқталды";
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      render(data);
      if (!data.finished) setTimeout(refresh, 1000);
    } catch {
      connection.classList.remove("live");
      connection.textContent = "Қайта қосылуда";
      setTimeout(refresh, 3000);
    }
  }

  refresh();
}
