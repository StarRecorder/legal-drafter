from __future__ import annotations

import dataclasses
import json
import mimetypes
import tempfile
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from legal_drafter import (
    DocumentRequest,
    DocumentKind,
    DraftRequest,
    GenerationOptions,
    LawSearchQuery,
    OllamaProvider,
    RenderOptions,
    ServiceTopic,
    generate_document,
    generate_draft,
    get_category_spec,
    list_categories,
    render_document,
    render_markdown,
    search_laws,
)
from legal_drafter.exceptions import CategorySpecError, IndexNotFoundError, ProviderError, RenderError

MODULE_PATH = Path(__file__).resolve()
DEMO_PAGE_PATHS = (
    MODULE_PATH.parents[2] / "examples" / "demo" / "index.html",
    MODULE_PATH.parents[1] / "examples" / "demo" / "index.html",
)
DEFAULT_ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "legal_drafter_artifacts"

DOCUMENT_KIND_LABELS = {
    DocumentKind.AUTO: "자동 감지",
    DocumentKind.TERMS_OF_SERVICE: "서비스 이용약관",
    DocumentKind.PRIVACY_POLICY: "개인정보 처리방침",
}

SERVICE_TOPIC_LABELS = {
    ServiceTopic.GENERAL: "일반 서비스",
    ServiceTopic.ECOMMERCE: "전자상거래",
    ServiceTopic.PLATFORM: "플랫폼",
    ServiceTopic.LOCATION_BASED: "위치기반 서비스",
    ServiceTopic.FINTECH: "핀테크",
    ServiceTopic.HEALTHCARE: "헬스케어",
}

FALLBACK_DEMO_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>legal-drafter demo</title></head><body><p>examples/demo/index.html 파일을 찾을 수 없습니다.</p></body></html>"""
PARENT_CATEGORY_LABELS = {
    "privacy_policy": "개인정보처리방침",
    "contract": "계약서",
    "settlement": "합의서",
    "content_certification": "내용증명",
    "payment_order": "지급명령",
    "criminal_complaint": "고소장",
    "employment_contract": "근로계약",
    "loan_note": "차용증",
    "power_of_attorney": "위임장",
}


def create_demo_server(
    *,
    index_path: Path,
    model: str,
    host: str,
    port: int,
) -> ThreadingHTTPServer:
    handler = create_demo_handler(index_path=index_path, model=model)
    return ThreadingHTTPServer((host, port), handler)


def create_demo_handler(*, index_path: Path, model: str):
    demo_html = _load_demo_html()

    class DemoHandler(BaseHTTPRequestHandler):
        server_version = "legal-drafter-demo/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(demo_html)
                return
            if parsed.path == "/api/options":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "document_kinds": [
                            {"value": kind.value, "label": DOCUMENT_KIND_LABELS[kind]}
                            for kind in DocumentKind
                        ],
                        "service_topics": [
                            {"value": topic.value, "label": SERVICE_TOPIC_LABELS[topic]}
                            for topic in ServiceTopic
                        ],
                        "default_model": model,
                    },
                )
                return
            if parsed.path == "/api/categories":
                categories = list_categories()
                parents = sorted({spec.parent_category for spec in categories})
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "parent_categories": [
                            {
                                "value": parent,
                                "label": PARENT_CATEGORY_LABELS.get(parent, parent.replace("_", " ")),
                            }
                            for parent in parents
                        ],
                        "categories": [
                            {
                                **_serialize_payload(spec),
                                "parent_label": PARENT_CATEGORY_LABELS.get(spec.parent_category, spec.parent_category.replace("_", " ")),
                            }
                            for spec in categories
                        ],
                        "default_model": model,
                    },
                )
                return
            if parsed.path.startswith("/api/categories/"):
                category_id = unquote(parsed.path.removeprefix("/api/categories/"))
                try:
                    spec = get_category_spec(category_id)
                except CategorySpecError as exc:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND", "message": str(exc)})
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "category": {
                            **_serialize_payload(spec),
                            "parent_label": PARENT_CATEGORY_LABELS.get(spec.parent_category, spec.parent_category.replace("_", " ")),
                        }
                    },
                )
                return
            if parsed.path == "/api/laws/search":
                params = parse_qs(parsed.query)
                query_text = _optional_text(params.get("q", [None])[0])
                category_id = _optional_text(params.get("category_id", [None])[0])
                top_k = int(params.get("top_k", ["20"])[0])
                try:
                    hits = search_laws(
                        LawSearchQuery(
                            index_path=index_path,
                            category_id=category_id,
                            text=query_text,
                            top_k=top_k,
                        )
                    )
                except Exception as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "VALIDATION_ERROR", "message": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, {"hits": _serialize_payload(hits)})
                return
            if parsed.path.startswith("/api/artifacts/"):
                self._send_artifact(parsed.path.removeprefix("/api/artifacts/"))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND", "message": "요청한 경로를 찾을 수 없습니다."})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/generate":
                if parsed.path == "/api/documents":
                    self._handle_document_generation()
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND", "message": "요청한 경로를 찾을 수 없습니다."})
                return
            self._handle_legacy_generation()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)

        def _handle_legacy_generation(self) -> None:
            try:
                payload = self._read_json_body()
                request = DraftRequest(
                    prompt=str(payload["prompt"]),
                    document_kind=DocumentKind(payload.get("document_kind", DocumentKind.AUTO.value)),
                    service_topic=ServiceTopic(payload["service_topic"]) if payload.get("service_topic") else None,
                    organization_name=_optional_text(payload.get("organization_name")),
                    service_description=_optional_text(payload.get("service_description")),
                    data_categories=_coerce_list(payload.get("data_categories")),
                    constraints=_coerce_list(payload.get("constraints")),
                    tone=_optional_text(payload.get("tone")),
                )
                provider = OllamaProvider(model=_optional_text(payload.get("model")) or model)
                result = generate_draft(
                    request,
                    provider,
                    GenerationOptions(index_path=index_path),
                )
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "VALIDATION_ERROR", "message": f"필수 필드가 없습니다: {exc.args[0]}"})
                return
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_JSON", "message": "JSON 본문을 해석할 수 없습니다."})
                return
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "VALIDATION_ERROR", "message": str(exc)})
                return
            except IndexNotFoundError as exc:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "INDEX_NOT_READY", "message": str(exc)})
                return
            except ProviderError as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "PROVIDER_ERROR", "message": str(exc)})
                return
            except Exception as exc:  # pragma: no cover
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "INTERNAL_ERROR", "message": str(exc)})
                return

            self._send_json(
                HTTPStatus.OK,
                {
                    "result": result.as_dict(),
                    "markdown": render_markdown(result),
                },
            )

        def _handle_document_generation(self) -> None:
            generated_result = None
            try:
                payload = self._read_json_body()
                request = DocumentRequest(
                    category_id=str(payload["category_id"]),
                    field_values=payload.get("field_values") or {},
                    selected_law_ids=_coerce_list(payload.get("selected_law_ids")),
                    selected_article_ids=_coerce_list(payload.get("selected_article_ids")),
                    freeform_facts=_optional_text(payload.get("freeform_facts")),
                    constraints=_coerce_list(payload.get("constraints")),
                    tone=_optional_text(payload.get("tone")),
                )
                provider = OllamaProvider(model=_optional_text(payload.get("model")) or model)
                generated_result = generate_document(
                    request,
                    provider,
                    GenerationOptions(index_path=index_path, artifact_root=DEFAULT_ARTIFACT_ROOT),
                )
                rendered_result = render_document(
                    generated_result,
                    RenderOptions(
                        artifact_root=DEFAULT_ARTIFACT_ROOT,
                        artifact_base_url="/api/artifacts",
                    ),
                )
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "VALIDATION_ERROR", "message": f"필수 필드가 없습니다: {exc.args[0]}"})
                return
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_JSON", "message": "JSON 본문을 해석할 수 없습니다."})
                return
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "VALIDATION_ERROR", "message": str(exc)})
                return
            except IndexNotFoundError as exc:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "INDEX_NOT_READY", "message": str(exc)})
                return
            except RenderError as exc:
                payload = {"error": "RENDER_BLOCKED", "message": str(exc)}
                if generated_result is not None:
                    payload["result"] = generated_result.as_dict()
                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, payload)
                return
            except ProviderError as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "PROVIDER_ERROR", "message": str(exc)})
                return
            except Exception as exc:  # pragma: no cover
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "INTERNAL_ERROR", "message": str(exc)})
                return

            self._send_json(
                HTTPStatus.OK,
                {
                    "result": rendered_result.as_dict(),
                    "artifacts": rendered_result.as_dict().get("rendered_artifacts", []),
                },
            )

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_artifact(self, artifact_path: str) -> None:
            parts = [part for part in artifact_path.split("/") if part]
            if len(parts) < 2:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND", "message": "아티팩트를 찾을 수 없습니다."})
                return
            token = parts[0]
            relative = Path(*parts[1:])
            target = (DEFAULT_ARTIFACT_ROOT / token / relative).resolve()
            root = DEFAULT_ARTIFACT_ROOT.resolve()
            if root not in target.parents or not target.exists() or not target.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND", "message": "아티팩트를 찾을 수 없습니다."})
                return
            content = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return DemoHandler


def serve_demo(*, index_path: Path, model: str, host: str, port: int) -> None:
    server = create_demo_server(index_path=index_path, model=model, host=host, port=port)
    print(f"legal-drafter demo server listening on http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()


def _load_demo_html() -> str:
    for path in DEMO_PAGE_PATHS:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return FALLBACK_DEMO_HTML


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return tuple(part for part in parts if part)
    if isinstance(value, list):
        return tuple(str(part).strip() for part in value if str(part).strip())
    raise ValueError("목록 필드는 문자열 또는 배열이어야 합니다.")


def _serialize_payload(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return {key: _serialize_payload(inner) for key, inner in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize_payload(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_payload(inner) for inner in value]
    return value
