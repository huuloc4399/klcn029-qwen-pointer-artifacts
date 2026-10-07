"""Build an ipywidgets page for the operator-assisted Colab baseline."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "Qwen3_Pointer_EndToEnd_CV_JD_Demo_Colab.ipynb"
OUTPUT = HERE / "Qwen3_Pointer_Colab_UI_Demo.ipynb"


def set_source(cell: dict, value: str) -> None:
    cell["source"] = value.strip().splitlines(keepends=True)
    if cell["source"] and not cell["source"][-1].endswith("\n"):
        cell["source"][-1] += "\n"
    if cell["cell_type"] == "code":
        cell["execution_count"] = None
        cell["outputs"] = []


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build() -> None:
    source_nb = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = source_nb["cells"]
    cells = [copy.deepcopy(original[index]) for index in (0, 1, 2, 3, 5, 6)]

    set_source(cells[0], """
# CV Insight — giao diện baseline trong Google Colab

Giao diện dưới đây mô phỏng trang web của đề tài ngay trong notebook: upload PDF, dán JD,
chọn ngôn ngữ, consent, bấm **Đánh giá CV** và xem thẻ điểm/kỹ năng/góp ý. Model chỉ nạp
một lần và có thể xử lý nhiều CV liên tiếp trong cùng runtime.

Chạy cell 1–5 để chuẩn bị T4, adapter, Parser v1 và Qwen. Sau đó chạy cell 6 để mở giao
diện. Đây là UI nội bộ Colab, không tạo public URL.
""")

    install = "".join(cells[1]["source"]).rstrip() + ' "ipywidgets>=8.1,<9"\n'
    set_source(cells[1], install)

    config = "".join(cells[2]["source"])
    for line in (
        'LANGUAGE = "auto" #@param ["auto", "vi", "en"]\n',
        'FORCE_OCR = False #@param {type:"boolean"}\n',
        'JD_TEXT = "" #@param {type:"string"}\n',
        'RESEARCH_CONSENT = False #@param {type:"boolean"}\n',
        'PARTICIPANT_CODE = "" #@param {type:"string"}\n',
    ):
        config = config.replace(line, "")
    config = config.replace(
        'print({"gpu": torch.cuda.get_device_name(0), "language": LANGUAGE, "force_ocr": FORCE_OCR})',
        'print({"gpu": torch.cuda.get_device_name(0), "mode": "colab_widget_ui"})',
    )
    config = config.replace(
        'if len(JD_TEXT.strip()) < 80:\n    print("LƯU Ý: Hãy nhập JD_TEXT ít nhất 80 ký tự trước khi chạy cell 8.")\n',
        '',
    )
    set_source(cells[2], config)

    parser_cell = "".join(cells[4]["source"]).replace(
        "#@title 5. Nạp frozen Parser v1 và matching baseline",
        "#@title 4. Nạp frozen Parser v1 và matching baseline",
        1,
    )
    set_source(cells[4], parser_cell)
    model_cell = "".join(cells[5]["source"]).replace(
        "#@title 6. Nạp Qwen 4-bit và adapter (chỉ chạy một lần mỗi runtime)",
        "#@title 5. Nạp Qwen 4-bit và adapter (chỉ chạy một lần mỗi runtime)",
        1,
    )
    set_source(cells[5], model_cell)

    ocr_source = "".join(original[4]["source"])
    upload_block = '''print("Chọn đúng một CV định dạng PDF.")
uploaded = files.upload()
pdf_names = [name for name in uploaded if name.lower().endswith(".pdf")]
if len(pdf_names) != 1 or len(uploaded) != 1:
    raise RuntimeError("Cần upload đúng một tệp PDF.")

original_name = Path(pdf_names[0]).name
PDF_PATH = LOCAL_ROOT / "uploaded_cv.pdf"
PDF_PATH.write_bytes(uploaded[pdf_names[0]])
'''
    replacement = '''LANGUAGE = UI_LANGUAGE
FORCE_OCR = False
original_name = Path(UI_FILENAME).name
PDF_PATH = LOCAL_ROOT / f"ui_{hashlib.sha256(UI_PDF_BYTES).hexdigest()[:16]}.pdf"
PDF_PATH.write_bytes(UI_PDF_BYTES)
'''
    if upload_block not in ocr_source:
        raise RuntimeError("Không tìm thấy upload block trong notebook nguồn")
    ocr_source = ocr_source.replace(upload_block, replacement)
    ocr_source = ocr_source.replace('display(routing_log)\nprint("\\n--- TEXT ĐÃ ẨN PII, XEM TRƯỚC 5000 KÝ TỰ ---\\n")\nprint(source_text[:5000])', '')

    extraction_source = "".join(original[7]["source"])
    evaluation_source = "".join(original[8]["source"]).replace('files.download(str(bundle_path))', '')
    source_hashes = {
        "ocr": digest(ocr_source),
        "extraction": digest(extraction_source),
        "evaluation": digest(evaluation_source),
    }

    ui_code = f'''#@title 6. Mở giao diện CV Insight trong Colab
import html
import ipywidgets as widgets
from IPython.display import HTML, clear_output, display
from google.colab import output as colab_output
colab_output.enable_custom_widget_manager()

OCR_PIPELINE_SOURCE = {ocr_source!r}
EXTRACTION_PIPELINE_SOURCE = {extraction_source!r}
EVALUATION_PIPELINE_SOURCE = {evaluation_source!r}
EXPECTED_UI_SOURCE_HASHES = {source_hashes!r}
for name, content in {{"ocr": OCR_PIPELINE_SOURCE, "extraction": EXTRACTION_PIPELINE_SOURCE, "evaluation": EVALUATION_PIPELINE_SOURCE}}.items():
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != EXPECTED_UI_SOURCE_HASHES[name]:
        raise RuntimeError(f"Sai hash pipeline UI: {{name}}")

display(HTML("""
<style>
.cv-shell {{font-family:Arial,sans-serif;background:#f4f8f6;border:1px solid #dce9e2;border-radius:18px;overflow:hidden;margin:8px 0 18px}}
.cv-nav {{background:#087b4b;color:white;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.cv-brand {{font-size:22px;font-weight:800}} .cv-nav small {{opacity:.86}}
.cv-hero {{padding:28px 28px 10px}} .cv-hero h2 {{font-size:30px;margin:0;color:#14372a}}
.cv-hero p {{color:#597066;max-width:760px;line-height:1.55}}
.cv-card {{background:white;margin:18px 28px;padding:22px;border-radius:14px;box-shadow:0 5px 18px rgba(16,67,46,.08)}}
.score-card {{background:#effaf4;border-left:5px solid #0aa160;padding:18px;border-radius:12px;margin:12px 0}}
.score-card strong {{font-size:36px;color:#087b4b}} .tag {{display:inline-block;padding:5px 10px;margin:3px;border-radius:14px;background:#e7f6ee;color:#087b4b}}
.tag.missing {{background:#fff0e7;color:#a54c16}} .error-card {{background:#fff0f0;color:#9e1c1c;padding:16px;border-radius:10px}}
</style>
<div class="cv-shell"><div class="cv-nav"><div class="cv-brand">CV Insight</div><small>KLCN029 · Colab baseline</small></div>
<div class="cv-hero"><h2>Đánh giá CV theo mô tả công việc</h2><p>Qwen Pointer Stage 2 trích xuất CVSchema 2.0; Parser v1 kiểm tra bằng chứng; mô đun matching tính điểm riêng.</p></div></div>
"""))

upload_widget = widgets.FileUpload(accept=".pdf", multiple=False, description="Chọn CV PDF")
jd_widget = widgets.Textarea(placeholder="Dán JD tối thiểu 80 ký tự...", description="JD", layout=widgets.Layout(width="100%", height="180px"), style={{"description_width": "60px"}})
language_widget = widgets.Dropdown(options=[("Tự động", "auto"), ("Tiếng Việt", "vi"), ("English", "en")], value="auto", description="Ngôn ngữ")
participant_widget = widgets.Text(placeholder="Ví dụ U001; không nhập họ tên/email", description="Mã ứng viên")
consent_widget = widgets.Checkbox(value=False, description="Ứng viên đồng ý đóng góp CV cho nghiên cứu", indent=False)
run_button = widgets.Button(description="Đánh giá CV", button_style="success", icon="check", layout=widgets.Layout(width="180px", height="44px"))
progress = widgets.IntProgress(value=0, min=0, max=4, description="Tiến trình", bar_style="success", layout=widgets.Layout(width="100%"))
status_widget = widgets.HTML("<span style='color:#597066'>Model đã sẵn sàng. Hãy chọn PDF và nhập JD.</span>")
result_output = widgets.Output()

def _uploaded_file(widget):
    value = widget.value
    if not value:
        raise ValueError("Hãy chọn một CV PDF")
    if isinstance(value, dict):
        name, item = next(iter(value.items()))
        content = item.get("content", item)
    else:
        item = value[0]
        name = item.get("name", "uploaded.pdf")
        content = item["content"]
    if not str(name).lower().endswith(".pdf"):
        raise ValueError("Chỉ chấp nhận tệp PDF")
    return str(name), bytes(content)

def _tags(values, missing=False):
    css = "tag missing" if missing else "tag"
    return "".join(f"<span class='{{css}}'>{{html.escape(str(value))}}</span>" for value in values) or "<small>Không có</small>"

def _save_failed_research_submission(filename, pdf_bytes, jd_text, participant_code, language, exc, stage):
    import secrets
    submission_id = secrets.token_hex(12)
    withdrawal_code = secrets.token_urlsafe(18)
    consented_at_utc = datetime.now(timezone.utc).isoformat()
    target = RESULT_ROOT / "submissions" / submission_id
    target.mkdir(parents=True, exist_ok=False)
    (target / "cv.pdf").write_bytes(pdf_bytes)
    (target / "jd.txt").write_text(jd_text, encoding="utf-8")
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    consent_record = {{
        "consent_version": CONSENT_VERSION, "granted": True,
        "consented_at_utc": consented_at_utc,
        "purpose": "Đánh giá baseline đầu cuối và xây dựng tập CV thật cho nghiên cứu KLCN029",
        "retained_data": ["cv.pdf", "jd.txt", "failure.json"],
        "participant_code": participant_code.strip()[:80],
        "original_filename": filename, "pdf_sha256": pdf_hash,
        "jd_sha256": hashlib.sha256(jd_text.encode("utf-8")).hexdigest(),
    }}
    (target / "consent.json").write_text(json.dumps(consent_record, ensure_ascii=False, indent=2), encoding="utf-8")
    failure = {{
        "status": "failed", "stage": int(stage),
        "error_type": type(exc).__name__, "error": str(exc),
        "failed_at_utc": datetime.now(timezone.utc).isoformat(),
    }}
    (target / "failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt = {{
        "submission_id": submission_id,
        "participant_code": participant_code.strip()[:80],
        "consent_version": CONSENT_VERSION,
        "withdrawal_hash": hashlib.sha256(withdrawal_code.encode()).hexdigest(),
    }}
    (target / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    index_entry = {{
        "submission_id": submission_id, "participant_code": participant_code.strip()[:80],
        "consented_at_utc": consented_at_utc, "consent_version": CONSENT_VERSION,
        "pdf_sha256": pdf_hash, "language": language, "pipeline_status": "failed",
        "failed_stage": int(stage),
    }}
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    with (RESULT_ROOT / "submission_index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(index_entry, ensure_ascii=False) + "\\n")
    return {{
        "submission_id": submission_id, "withdrawal_code": withdrawal_code,
        "drive_path": str(target), "consent_version": CONSENT_VERSION,
    }}

def _on_run(_button):
    run_button.disabled = True; progress.value = 0
    filename = None; pdf_bytes = None; jd_text = ""; ns = None
    with result_output:
        clear_output()
    try:
        filename, pdf_bytes = _uploaded_file(upload_widget)
        jd_text = jd_widget.value.strip()
        if len(jd_text) < 80:
            raise ValueError("JD cần ít nhất 80 ký tự")
        status_widget.value = "<b>1/4</b> Đang đọc PDF và OCR..."
        ns = dict(globals())
        ns.update({{"UI_FILENAME": filename, "UI_PDF_BYTES": pdf_bytes, "UI_LANGUAGE": language_widget.value}})
        exec(OCR_PIPELINE_SOURCE, ns, ns); progress.value = 1
        status_widget.value = "<b>2/4</b> Qwen đang trích xuất Pointer JSON..."
        exec(EXTRACTION_PIPELINE_SOURCE, ns, ns); progress.value = 2
        if ns["parse_result"].status != "success":
            issues = ns["parse_payload"].get("issues", [])
            raise RuntimeError("Parser v1 từ chối output: " + json.dumps(issues, ensure_ascii=False))
        status_widget.value = "<b>3/4</b> Đang so khớp CV với JD..."
        ns.update({{"JD_TEXT": jd_text, "RESEARCH_CONSENT": consent_widget.value, "PARTICIPANT_CODE": participant_widget.value}})
        exec(EVALUATION_PIPELINE_SOURCE, ns, ns); progress.value = 3
        evaluation = ns["evaluation"]
        receipt = ns.get("research_receipt")
        receipt_html = ""
        if receipt:
            receipt_html = f"""<div class='score-card'><b>Đã lưu hồ sơ nghiên cứu vào Google Drive.</b>
            <p>Mã hồ sơ: <code>{{html.escape(receipt['submission_id'])}}</code><br>
            Mã rút dữ liệu: <code>{{html.escape(receipt['withdrawal_code'])}}</code><br>
            Thư mục: <code>{{html.escape(receipt['drive_path'])}}</code></p>
            <small>Hãy gửi mã rút dữ liệu cho ứng viên và lưu mã này ngoài thư mục nghiên cứu.</small></div>"""
        else:
            receipt_html = "<p><b>Không lưu nghiên cứu:</b> PDF/JD không được sao chép vào Drive và PDF tạm đã bị xóa.</p>"
        improvements = "".join(f"<li>{{html.escape(str(item))}}</li>" for item in evaluation["improvements"])
        result_html = f"""
        <div class='cv-card'><h2>Kết quả đánh giá</h2><div class='score-card'><strong>{{evaluation['total_score']:.0f}}/100</strong><h3>{{html.escape(evaluation['verdict'])}}</h3></div>
        <h3>Kỹ năng đã khớp</h3><div>{{_tags(evaluation['matched_skills'])}}</div>
        <h3>Kỹ năng JD chưa thấy</h3><div>{{_tags(evaluation['missing_skills'], True)}}</div>
        <h3>Ưu tiên cải thiện</h3><ol>{{improvements}}</ol>
        <p><b>Pipeline:</b> Qwen Pointer P0 · Parser v1 · CVSchema 2.0</p>{{receipt_html}}
        <p>Bundle: <code>{{html.escape(str(ns['bundle_path']))}}</code></p></div>"""
        with result_output:
            display(HTML(result_html))
        progress.value = 4
        status_widget.value = "<b style='color:#087b4b'>Hoàn tất.</b> Trình duyệt sẽ tải bundle kết quả."
        files.download(str(ns["bundle_path"]))
    except Exception as exc:
        status_widget.value = "<b style='color:#a12626'>Không thể hoàn tất.</b>"
        existing_receipt = ns.get("research_receipt") if ns else None
        failed_receipt = existing_receipt
        save_error = None
        if consent_widget.value and filename and pdf_bytes is not None and len(jd_text) >= 80 and not existing_receipt:
            try:
                failed_receipt = _save_failed_research_submission(
                    filename, pdf_bytes, jd_text, participant_widget.value,
                    language_widget.value, exc, progress.value,
                )
            except Exception as storage_exc:
                save_error = storage_exc
        receipt_error_html = ""
        if failed_receipt:
            receipt_error_html = f"""<hr><b>CV vẫn được lưu vì đã có đồng thuận nghiên cứu.</b><br>
            Mã hồ sơ: <code>{{html.escape(failed_receipt['submission_id'])}}</code><br>
            Mã rút dữ liệu: <code>{{html.escape(failed_receipt['withdrawal_code'])}}</code><br>
            Thư mục: <code>{{html.escape(failed_receipt['drive_path'])}}</code>"""
        elif save_error:
            receipt_error_html = f"<hr><b>Lưu nghiên cứu cũng thất bại:</b> {{html.escape(str(save_error))}}"
        with result_output:
            clear_output(); display(HTML(f"<div class='error-card'><b>Lỗi baseline:</b> {{html.escape(str(exc))}}{{receipt_error_html}}</div>"))
    finally:
        if ns:
            temporary_pdf = ns.get("PDF_PATH")
            if temporary_pdf:
                Path(temporary_pdf).unlink(missing_ok=True)
        run_button.disabled = False

run_button.on_click(_on_run)
form = widgets.VBox([
    widgets.HTML("<div class='cv-card'><h3>1. Hồ sơ và JD</h3></div>"),
    upload_widget, jd_widget,
    widgets.HBox([language_widget, participant_widget]),
    widgets.HTML("""<div style='background:#fff8e6;border-left:4px solid #d59b15;padding:12px;margin:8px 0'>
    <b>Đồng thuận đóng góp dữ liệu nghiên cứu</b><br>
    Chỉ đánh dấu khi ứng viên đã được thông báo rằng PDF gốc, JD và kết quả baseline sẽ
    được lưu trong Google Drive của nhóm cho nghiên cứu KLCN029. Hệ thống cấp mã rút dữ
    liệu sau khi lưu. Bỏ trống nếu ứng viên chỉ muốn nhận kết quả đánh giá.
    </div>"""),
    consent_widget, run_button, progress, status_widget, result_output,
], layout=widgets.Layout(border="1px solid #dce9e2", padding="22px", width="100%"))
display(form)
'''
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ui_code.splitlines(keepends=True)})
    withdrawal_cell = copy.deepcopy(original[10])
    withdrawal_source = "".join(withdrawal_cell["source"]).replace(
        "#@title 9. Rút dữ liệu đã đóng góp (chỉ chạy khi có yêu cầu)",
        "#@title 7. Quản trị: rút dữ liệu đã đóng góp (chỉ chạy khi có yêu cầu)",
        1,
    )
    set_source(withdrawal_cell, withdrawal_source)
    cells.append(withdrawal_cell)
    cells.append({"cell_type": "markdown", "metadata": {}, "source": """## Lưu ý

- Giao diện chỉ tồn tại trong runtime Colab đang mở.
- Khi runtime ngắt, chạy lại cell 1–6; adapter trên Drive hoặc Hugging Face không mất.
- Không bật consent nếu ứng viên chỉ yêu cầu đánh giá và không đóng góp nghiên cứu.
- Cell 7 chỉ dành cho người vận hành khi ứng viên yêu cầu rút dữ liệu bằng mã đã nhận.
- Không dùng điểm này như quyết định tuyển dụng.
""".splitlines(keepends=True)})

    notebook = copy.deepcopy(source_nb)
    notebook["cells"] = cells
    notebook["metadata"]["colab"]["name"] = OUTPUT.name
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    build()
