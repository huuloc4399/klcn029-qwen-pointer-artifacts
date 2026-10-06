const fileInput = document.querySelector("#cvFile");
const fileName = document.querySelector("#fileName");
const dropZone = document.querySelector("#dropZone");
const jdText = document.querySelector("textarea[name='jd_text']");
const jdCount = document.querySelector("#jdCount");
const form = document.querySelector("#evaluationForm");
const submitButton = document.querySelector("#submitButton");

function updateFileName() {
  if (!fileInput || !fileName) return;
  const file = fileInput.files?.[0];
  fileName.textContent = file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB` : "PDF · tối đa 8 MB";
  dropZone?.classList.toggle("has-file", Boolean(file));
}

function updateJdCount() {
  if (jdText && jdCount) jdCount.textContent = jdText.value.length.toLocaleString("vi-VN");
}

if (fileInput) fileInput.addEventListener("change", updateFileName);
if (jdText) {
  jdText.addEventListener("input", updateJdCount);
  updateJdCount();
}
if (dropZone) {
  for (const eventName of ["dragenter", "dragover"]) dropZone.addEventListener(eventName, () => dropZone.classList.add("dragging"));
  for (const eventName of ["dragleave", "drop"]) dropZone.addEventListener(eventName, () => dropZone.classList.remove("dragging"));
}
if (form && submitButton) {
  form.addEventListener("submit", () => {
    submitButton.disabled = true;
    submitButton.querySelector("span").textContent = "Đang phân tích CV...";
    submitButton.querySelector("small").textContent = "Vui lòng giữ nguyên trang này";
  });
}
