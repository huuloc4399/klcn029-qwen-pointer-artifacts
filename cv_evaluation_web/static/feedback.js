const feedbackForm = document.querySelector("#feedbackForm");
const ratingCaption = document.querySelector("#ratingCaption");
const feedbackStatus = document.querySelector("#feedbackStatus");

if (feedbackForm) {
  for (const input of feedbackForm.querySelectorAll("input[name='rating']")) {
    input.addEventListener("change", () => {
      ratingCaption.textContent = `${input.value} sao · ${input.dataset.label}`;
    });
  }

  feedbackForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = feedbackForm.querySelector("button[type='submit']");
    button.disabled = true;
    feedbackStatus.className = "feedback-status";
    feedbackStatus.textContent = "Đang gửi đánh giá...";
    try {
      const response = await fetch(feedbackForm.action, {
        method: "POST",
        body: new FormData(feedbackForm),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await response.json();
      const done = data.status === "stored" || data.status === "duplicate";
      feedbackStatus.textContent = data.message || "Đã gửi đánh giá.";
      feedbackStatus.classList.add(done ? "success" : "error");
      if (done) {
        for (const field of feedbackForm.querySelectorAll("input, textarea")) field.disabled = true;
        button.classList.add("hidden");
        return;
      }
    } catch (_error) {
      feedbackStatus.textContent = "Chưa gửi được đánh giá. Hãy kiểm tra kết nối rồi thử lại.";
      feedbackStatus.classList.add("error");
    }
    button.disabled = false;
  });
}
