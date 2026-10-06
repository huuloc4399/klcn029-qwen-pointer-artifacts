"""CV evaluation and voluntary research collection web application."""

from __future__ import annotations

import os
import base64
import hashlib
import hmac
import secrets
import tempfile
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from baseline_extraction.privacy import redact_text
from baseline_extraction.schema import CVSchema
from services.evaluator import evaluate
from services.job_store import JobStore
from services.pdf_extractor import PDFExtractionError, extract_pdf
from services.runpod_client import RunPodClient, RunPodError, TERMINAL_STATUSES
from storage import POLICY_VERSION, SubmissionStore


ROOT = Path(__file__).resolve().parent
ALLOWED_LANGUAGES = {"auto", "vi", "en"}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("CV_WEB_SECRET_KEY", os.urandom(32)),
        MAX_CONTENT_LENGTH=int(os.getenv("CV_WEB_MAX_UPLOAD_MB", "8")) * 1024 * 1024,
        DATA_DIR=os.getenv("CV_WEB_DATA_DIR", str(ROOT / "data")),
        MAX_PDF_PAGES=int(os.getenv("CV_WEB_MAX_PDF_PAGES", "12")),
        PIPELINE_MODE=os.getenv("CV_PIPELINE_MODE", "local_baseline").strip().lower(),
        RUNPOD_ENDPOINT_ID=os.getenv("RUNPOD_ENDPOINT_ID", ""),
        RUNPOD_API_KEY=os.getenv("RUNPOD_API_KEY", ""),
        RUNPOD_WEBHOOK_SECRET=os.getenv("RUNPOD_WEBHOOK_SECRET", ""),
        PUBLIC_BASE_URL=(
            os.getenv("PUBLIC_BASE_URL", "")
            or (f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}" if os.getenv("RENDER_EXTERNAL_HOSTNAME") else "")
        ).rstrip("/"),
        CSRF_ENABLED=os.getenv("CV_WEB_CSRF_ENABLED", "1") == "1",
        RATE_LIMIT_PER_HOUR=int(os.getenv("CV_WEB_RATE_LIMIT_PER_HOUR", "5")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.getenv("RENDER_EXTERNAL_HOSTNAME")),
    )
    if test_config:
        app.config.update(test_config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    store = SubmissionStore(app.config["DATA_DIR"])
    job_store = JobStore(app.config["DATA_DIR"])
    temporary_dir = Path(app.config["DATA_DIR"]).resolve() / "tmp"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    app.config["SUBMISSION_STORE"] = store
    app.config["JOB_STORE"] = job_store
    app.config["TEMPORARY_DIR"] = temporary_dir
    finalize_lock = threading.Lock()

    def csrf_token() -> str:
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def verify_csrf():
        if not app.config["CSRF_ENABLED"] or request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.endpoint == "runpod_webhook":
            return None
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description="CSRF token is missing or invalid")
        return None

    runpod_client = app.config.get("RUNPOD_CLIENT")
    if app.config["PIPELINE_MODE"] == "runpod" and runpod_client is None:
        runpod_client = RunPodClient(
            endpoint_id=app.config["RUNPOD_ENDPOINT_ID"],
            api_key=app.config["RUNPOD_API_KEY"],
        )

    def document_from_payload(payload: dict, *, text: str = ""):
        from services.pdf_extractor import DocumentAnalysis

        return DocumentAnalysis(
            text=text,
            page_count=int(payload.get("page_count", 0)),
            native_text_pages=int(payload.get("native_text_pages", 0)),
            character_count=int(payload.get("character_count", len(text))),
            block_count=int(payload.get("block_count", 0)),
            likely_multi_column=bool(payload.get("likely_multi_column", False)),
            needs_ocr=bool(payload.get("needs_ocr", False) or payload.get("ocr_pages", 0)),
        )

    def fail_remote_job(token: str, message: str) -> dict:
        job_store.fail(token, message)
        return {"status": "FAILED", "message": message}

    def finalize_remote_job(token: str, remote: dict) -> dict:
        with finalize_lock:
            job = job_store.load(token)
            if job is None:
                return {"status": "NOT_FOUND"}
            # result.json is written atomically before temporary CV/JD are deleted.
            # Treat its presence as completion so a retry after a process interruption
            # never stores an opt-in submission twice.
            if job_store.result(token) is not None:
                return {"status": "COMPLETED", "result_url": url_for("job_result", token=token)}
            output = remote.get("output")
            if not isinstance(output, dict):
                return fail_remote_job(token, "Dịch vụ model không trả về kết quả có cấu trúc.")
            if output.get("status") != "success":
                return fail_remote_job(
                    token,
                    "Kết quả Qwen chưa vượt qua Parser v1. Hồ sơ cần được nhóm kiểm tra.",
                )
            try:
                cv_schema = CVSchema.model_validate(output.get("cv")).model_dump(mode="json")
            except Exception:
                return fail_remote_job(token, "CVSchema 2.0 trả về từ model không hợp lệ.")

            local_document = dict(job["document"])
            remote_document = ((output.get("manifest") or {}).get("document") or {})
            if remote_document:
                local_document.update({
                    key: remote_document[key]
                    for key in ("page_count", "native_text_pages", "character_count", "ocr_pages", "ocr_quality_warning")
                    if key in remote_document
                })
                local_document["needs_ocr"] = bool(remote_document.get("ocr_pages", 0))
            document = document_from_payload(local_document)
            jd_text = job_store.jd_text(token)
            result = evaluate(
                document,
                jd_text,
                language=job["language"],
                cv_schema=cv_schema,
                method="Qwen Pointer P0 + Parser v1 + deterministic matching baseline v1",
            ).to_dict()
            extraction = {
                **document.public_dict(),
                "cv_schema": cv_schema,
                "evidence": output.get("evidence") or {},
                "parser": output.get("parser") or {},
                "model_manifest": output.get("manifest") or {},
            }
            receipt = None
            if job["research_consent"]:
                receipt = store.save_opt_in(
                    pdf_path=job_store.pdf_path(token),
                    language=job["language"],
                    participant_code=job["participant_code"],
                    jd_text=jd_text,
                    extraction=extraction,
                    evaluation=result,
                )
            result_payload = {
                "result": result,
                "research_consent": bool(job["research_consent"]),
                "research_receipt": receipt,
                "pipeline": {
                    "status": "success",
                    "cv_schema_version": "2.0",
                    "parser": (output.get("parser") or {}).get("parser_version"),
                    "model": (output.get("manifest") or {}).get("model_id"),
                    "worker_version": (output.get("manifest") or {}).get("worker_version"),
                    "input_tokens": (output.get("manifest") or {}).get("input_tokens"),
                    "generated_tokens": (output.get("manifest") or {}).get("generated_tokens"),
                    "model_runtime_seconds": (output.get("manifest") or {}).get("runtime_seconds"),
                    "runpod_delay_ms": remote.get("delayTime"),
                    "runpod_execution_ms": remote.get("executionTime"),
                    "document_route": remote_document.get("route"),
                    "ocr_quality_warning": bool(remote_document.get("ocr_quality_warning", False)),
                },
            }
            job_store.complete(token, result_payload)
            return {"status": "COMPLETED", "result_url": url_for("job_result", token=token)}

    def sync_remote_job(token: str, remote: dict | None = None) -> dict:
        job = job_store.load(token)
        if job is None:
            return {"status": "NOT_FOUND", "message": "Không tìm thấy tác vụ."}
        if job_store.result(token) is not None:
            return {"status": "COMPLETED", "result_url": url_for("job_result", token=token)}
        if job.get("status") == "FAILED":
            return {"status": "FAILED", "message": job.get("error", "Tác vụ thất bại.")}
        if remote is None:
            try:
                remote = runpod_client.status(job["remote_job_id"])
            except RunPodError as exc:
                return {"status": "UNAVAILABLE", "message": str(exc)}
        remote_status = str(remote.get("status", "UNKNOWN")).upper()
        if remote_status == "COMPLETED":
            return finalize_remote_job(token, remote)
        if remote_status in TERMINAL_STATUSES:
            return fail_remote_job(token, "Tác vụ GPU kết thúc nhưng không tạo được kết quả.")
        job_store.update(token, status=remote_status)
        return {
            "status": remote_status,
            "message": "Đang chờ GPU..." if remote_status == "IN_QUEUE" else "Qwen đang trích xuất và kiểm tra CV...",
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; font-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/")
    def index():
        job_store.cleanup()
        return render_template("index.html", stats=store.public_stats(), policy_version=POLICY_VERSION)

    @app.post("/evaluate")
    def evaluate_upload():
        errors: list[str] = []
        upload = request.files.get("cv_file")
        jd_text = request.form.get("jd_text", "").strip()
        language = request.form.get("language", "auto").strip().lower()
        participant_code = request.form.get("participant_code", "").strip()[:80]
        consent_evaluation = request.form.get("consent_evaluation") == "yes"
        consent_research = request.form.get("consent_research") == "yes"

        if not consent_evaluation:
            errors.append("Bạn cần xác nhận đồng ý xử lý tạm thời để hệ thống đánh giá CV.")
        if upload is None or not upload.filename:
            errors.append("Hãy chọn một tệp CV dạng PDF.")
        elif Path(upload.filename).suffix.casefold() != ".pdf":
            errors.append("Hệ thống chỉ nhận tệp PDF.")
        if len(jd_text) < 80:
            errors.append("JD cần ít nhất 80 ký tự để kết quả so khớp có ý nghĩa.")
        if len(jd_text) > 30_000:
            errors.append("JD vượt quá giới hạn 30.000 ký tự.")
        if language not in ALLOWED_LANGUAGES:
            errors.append("Ngôn ngữ CV không hợp lệ.")
        if errors:
            return render_template("index.html", stats=store.public_stats(), errors=errors, form=request.form), 400

        remote_address = request.remote_addr or "unknown"
        secret_value = app.config["SECRET_KEY"]
        secret_bytes = secret_value if isinstance(secret_value, bytes) else str(secret_value).encode("utf-8")
        identifier_hash = hashlib.sha256(secret_bytes + remote_address.encode("utf-8")).hexdigest()
        if not store.allow_request(
            identifier_hash,
            maximum=app.config["RATE_LIMIT_PER_HOUR"],
            window_seconds=3600,
        ):
            return render_template(
                "index.html",
                stats=store.public_stats(),
                errors=["Bạn đã gửi quá nhiều yêu cầu trong một giờ. Hãy thử lại sau."],
                form=request.form,
            ), 429

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="cv_eval_", suffix=".pdf", delete=False, dir=app.config["TEMPORARY_DIR"]
            ) as temporary:
                upload.save(temporary)
                temporary_path = Path(temporary.name)
            document = extract_pdf(temporary_path, max_pages=app.config["MAX_PDF_PAGES"])
            if app.config["PIPELINE_MODE"] == "runpod":
                token = job_store.create(
                    pdf_path=temporary_path,
                    jd_text=jd_text,
                    language=language,
                    participant_code=participant_code,
                    research_consent=consent_research,
                    document=document.public_dict(),
                )
                if document.needs_ocr:
                    pdf_bytes = temporary_path.read_bytes()
                    if len(pdf_bytes) > 6 * 1024 * 1024:
                        job_store.delete(token)
                        raise PDFExtractionError("PDF cần OCR và vượt giới hạn 6 MB của pipeline GPU.")
                    remote_input = {
                        "request_id": token,
                        "language": language,
                        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
                    }
                else:
                    remote_input = {
                        "request_id": token,
                        "language": language,
                        "source_text": redact_text(document.text, first_page=True),
                        "page_count": document.page_count,
                        "native_text_pages": document.native_text_pages,
                    }
                webhook_url = None
                if app.config["RUNPOD_WEBHOOK_SECRET"] and app.config["PUBLIC_BASE_URL"]:
                    webhook_url = (
                        f"{app.config['PUBLIC_BASE_URL']}"
                        f"{url_for('runpod_webhook', secret=app.config['RUNPOD_WEBHOOK_SECRET'])}"
                    )
                try:
                    submitted = runpod_client.submit(remote_input, webhook_url=webhook_url)
                except RunPodError as exc:
                    job_store.delete(token)
                    return render_template(
                        "index.html", stats=store.public_stats(), errors=[str(exc)], form=request.form
                    ), 502
                job_store.update(token, status=str(submitted.get("status", "IN_QUEUE")), remote_job_id=submitted["id"])
                return redirect(url_for("job_page", token=token), code=303)

            result = evaluate(document, jd_text, language=language).to_dict()
            research_receipt = None
            if consent_research:
                research_receipt = store.save_opt_in(
                    pdf_path=temporary_path,
                    language=language,
                    participant_code=participant_code,
                    jd_text=jd_text,
                    extraction=document.public_dict(),
                    evaluation=result,
                )
            return render_template(
                "result.html",
                result=result,
                research_receipt=research_receipt,
                research_consent=consent_research,
            )
        except PDFExtractionError as exc:
            return render_template(
                "index.html", stats=store.public_stats(), errors=[str(exc)], form=request.form
            ), 400
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.get("/processing/<token>")
    def job_page(token: str):
        job = job_store.load(token)
        if job is None:
            return render_template("processing.html", missing=True), 404
        if job.get("status") == "COMPLETED":
            return redirect(url_for("job_result", token=token), code=303)
        return render_template("processing.html", token=token, job=job, missing=False)

    @app.get("/api/jobs/<token>")
    def job_status(token: str):
        try:
            payload = sync_remote_job(token)
        except ValueError:
            payload = {"status": "NOT_FOUND", "message": "Mã tác vụ không hợp lệ."}
        status_code = 404 if payload["status"] == "NOT_FOUND" else 200
        return jsonify(payload), status_code

    @app.get("/result/<token>")
    def job_result(token: str):
        try:
            payload = job_store.result(token)
        except ValueError:
            payload = None
        if payload is None:
            return redirect(url_for("job_page", token=token), code=303)
        return render_template(
            "result.html",
            result=payload["result"],
            research_receipt=payload.get("research_receipt"),
            research_consent=payload.get("research_consent", False),
            pipeline=payload.get("pipeline"),
        )

    @app.post("/api/runpod/webhook/<secret>")
    def runpod_webhook(secret: str):
        expected = app.config["RUNPOD_WEBHOOK_SECRET"]
        if not expected or not hmac.compare_digest(secret, expected):
            return jsonify({"status": "forbidden"}), 403
        remote = request.get_json(silent=True) or {}
        remote_id = remote.get("id")
        if not isinstance(remote_id, str):
            return jsonify({"status": "invalid"}), 400
        token = job_store.find_by_remote_id(remote_id)
        if token is None:
            return jsonify({"status": "ignored"}), 200
        return jsonify(sync_remote_job(token, remote))

    @app.route("/withdraw", methods=["GET", "POST"])
    def withdraw():
        message = None
        success = False
        if request.method == "POST":
            code = request.form.get("withdrawal_code", "").strip()
            if not code:
                message = "Hãy nhập mã rút dữ liệu."
            elif store.withdraw(code):
                success = True
                message = "CV, JD và kết quả liên quan đã được xóa khỏi kho nghiên cứu."
            else:
                message = "Không tìm thấy mã hợp lệ hoặc dữ liệu đã được xóa trước đó."
        return render_template("withdraw.html", message=message, success=success)

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html", policy_version=POLICY_VERSION)

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "cv-evaluation-web",
            "pipeline_mode": app.config["PIPELINE_MODE"],
            "policy_version": POLICY_VERSION,
        })

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_template(
            "index.html", stats=store.public_stats(), errors=[f"Tệp vượt quá giới hạn {limit_mb} MB."]
        ), 413

    return app


if __name__ == "__main__":
    application = create_app()
    host = os.getenv("CV_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("CV_WEB_PORT", "8780"))
    application.run(host=host, port=port, debug=False, threaded=True)

