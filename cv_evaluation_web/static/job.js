const monitor = document.querySelector("#jobMonitor");
const message = document.querySelector("#jobMessage");
const errorBox = document.querySelector("#jobError");

const terminalFailures = new Set(["FAILED", "TIMED_OUT", "CANCELLED", "NOT_FOUND"]);
let attempts = 0;

async function pollJob() {
  if (!monitor) return;
  attempts += 1;
  try {
    const response = await fetch(monitor.dataset.statusUrl, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const data = await response.json();
    if (data.status === "COMPLETED" && data.result_url) {
      window.location.assign(data.result_url);
      return;
    }
    if (terminalFailures.has(data.status)) {
      monitor.querySelector(".spinner")?.classList.add("stopped");
      errorBox.textContent = data.message || "Tác vụ không thể hoàn tất.";
      errorBox.classList.remove("hidden");
      message.textContent = "Hệ thống đã dừng xử lý tác vụ này.";
      return;
    }
    message.textContent = data.message || "Qwen đang xử lý CV...";
  } catch (_error) {
    message.textContent = "Kết nối tạm thời gián đoạn; hệ thống sẽ tự thử lại.";
  }
  const delay = attempts < 5 ? 2500 : 5000;
  window.setTimeout(pollJob, delay);
}

if (monitor) window.setTimeout(pollJob, 800);
