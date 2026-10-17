// Result page: show every to-do, and recompute the total when a reader marks a criterion as not applying.
// The stored result never changes; this only redraws the numbers on this page.
(function () {
  const more = document.getElementById("todoMore");
  if (more) {
    more.addEventListener("click", () => {
      const extras = document.querySelectorAll(".todo.extra");
      const open = more.dataset.open === "1";
      extras.forEach((item) => { item.hidden = open; });
      more.dataset.open = open ? "0" : "1";
      more.textContent = open ? more.dataset.more : more.dataset.less;
    });
  }

  const dataNode = document.getElementById("scoreData");
  const totalNode = document.getElementById("totalScore");
  if (!dataNode || !totalNode) return;
  let data;
  try { data = JSON.parse(dataNode.textContent); } catch (error) { return; }
  const verdictNode = document.getElementById("totalVerdict");
  const note = document.getElementById("naNote");
  const count = document.getElementById("naCount");
  const original = { total: totalNode.textContent, verdict: verdictNode ? verdictNode.textContent : "" };

  function verdict(score) {
    for (const [floor, label] of data.verdicts) { if (score >= floor) return label; }
    return "";
  }

  function redraw() {
    const skipped = new Set([...document.querySelectorAll(".na-toggle:checked")].map((box) => box.value));
    document.querySelectorAll(".todo").forEach((item) => {
      item.classList.toggle("not-applied", skipped.has(item.dataset.criterion));
    });
    if (!skipped.size) {
      totalNode.textContent = original.total;
      if (verdictNode) verdictNode.textContent = original.verdict;
      if (note) note.hidden = true;
      return;
    }
    const used = data.criteria.filter((c) => !skipped.has(c.id));
    const weight = used.reduce((sum, c) => sum + c.weight, 0);
    if (!weight) return;
    const score = 100 * used.reduce((sum, c) => sum + c.weight * c.score, 0) / (4 * weight);
    totalNode.textContent = Math.round(score);
    if (verdictNode) verdictNode.textContent = verdict(score);
    if (note) { note.hidden = false; count.textContent = skipped.size; }
  }

  document.querySelectorAll(".na-toggle").forEach((box) => box.addEventListener("change", redraw));
})();
