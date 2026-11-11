"""Contratos formais de interface para os subagentes do LapIntel (Google Antigravity SDK).

Define os schemas estruturados para dados trocados entre o Coordinator e os
subagentes especializados (DiscoveryScout, SpecExtractor, DealAuditor e SystemGuardian).
Compatível com Pydantic quando instalado, com fallback transparente para dataclasses.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Literal

try:
    import pydantic  # type: ignore[import-not-found]
    HAS_PYDANTIC = True
except ImportError:
    pydantic = None  # type: ignore[assignment]
    HAS_PYDANTIC = False


# =============================================================================
# 1. Contratos Base / Schemas Estruturados
# =============================================================================

if HAS_PYDANTIC:
    class DiscoveryCandidate(pydantic.BaseModel):
        """Candidato descoberto pelo Scout de catálogo ou sitemap."""
        url: str
        loja: str
        titulo: str
        preco_hint: float | None = None
        discovered_at: str | None = None
        source: str = "category"

    class LaptopSpecExtraction(pydantic.BaseModel):
        """Especificações técnicas normalizadas extraídas de um portátil."""
        url: str | None = None
        marca: str | None = None
        submarca: str | None = None
        cpu_modelo: str | None = None
        cpu_str_original: str | None = None
        cpu_classe: str | None = None
        gpu_modelo: str | None = None
        gpu_tipo: str = "desconhecida"
        tgp_w: int | None = None
        vram_gb: float | None = None
        ram_gb: float | None = None
        ram_type: str | None = None
        ram_expansivel: bool = False
        armazenamento_tb: float | None = None
        ssd_expansivel: bool = False
        bateria_wh: float | None = None
        peso_kg: float | None = None
        ecra_tamanho: float | None = None
        ecra_res: str | None = None
        ecra_painel: str | None = None
        ecra_hz: int | None = None
        ecra_brightness_nits: int | None = None
        ecra_srgb_percent: float | None = None
        os_status: Literal["windows", "none", "unknown", "conflict"] = "unknown"
        keyboard_layout: Literal["pt", "en", "es", "unknown"] = "unknown"
        is_new_condition: bool = True
        ean: str | None = None
        mpn: str | None = None
        sku: str | None = None

    class DealDecision(pydantic.BaseModel):
        """Decisão auditada de oportunidade económica e conformidade orçamental."""
        url: str
        loja: str
        titulo: str
        price: float
        installation_cost_eur: float = 0.0
        purchase_total_eur: float = 0.0
        value_score: float | None = None
        tier: Literal["DIAMANTE", "OURO", "PRATA", "BRONZE", "SEM_TIER", "REJEITADO"] = "SEM_TIER"
        status: Literal["ACEITE", "REJEITADO"] = "REJEITADO"
        eligible: bool = False
        rejection_reason: str | None = None
        should_notify_ntfy: bool = False
        timestamp: str | None = None

else:
    @dataclass
    class DiscoveryCandidate:
        url: str
        loja: str
        titulo: str
        preco_hint: float | None = None
        discovered_at: str | None = None
        source: str = "category"

    @dataclass
    class LaptopSpecExtraction:
        url: str | None = None
        marca: str | None = None
        submarca: str | None = None
        cpu_modelo: str | None = None
        cpu_str_original: str | None = None
        cpu_classe: str | None = None
        gpu_modelo: str | None = None
        gpu_tipo: str = "desconhecida"
        tgp_w: int | None = None
        vram_gb: float | None = None
        ram_gb: float | None = None
        ram_type: str | None = None
        ram_expansivel: bool = False
        armazenamento_tb: float | None = None
        ssd_expansivel: bool = False
        bateria_wh: float | None = None
        peso_kg: float | None = None
        ecra_tamanho: float | None = None
        ecra_res: str | None = None
        ecra_painel: str | None = None
        ecra_hz: int | None = None
        ecra_brightness_nits: int | None = None
        ecra_srgb_percent: float | None = None
        os_status: str = "unknown"
        keyboard_layout: str = "unknown"
        is_new_condition: bool = True
        ean: str | None = None
        mpn: str | None = None
        sku: str | None = None

    @dataclass
    class DealDecision:
        url: str
        loja: str
        titulo: str
        price: float
        installation_cost_eur: float = 0.0
        purchase_total_eur: float = 0.0
        value_score: float | None = None
        tier: str = "SEM_TIER"
        status: str = "REJEITADO"
        eligible: bool = False
        rejection_reason: str | None = None
        should_notify_ntfy: bool = False
        timestamp: str | None = None


# =============================================================================
# 2. Adaptadores Bidirecionais V9 <-> Contratos de Subagentes
# =============================================================================

def to_legacy_dict(extraction: LaptopSpecExtraction | dict[str, Any]) -> dict[str, Any]:
    """Converte um contrato LaptopSpecExtraction para o dicionário spec tradicional da V9."""
    if isinstance(extraction, dict):
        data = dict(extraction)
    elif HAS_PYDANTIC and isinstance(extraction, pydantic.BaseModel):
        data = extraction.model_dump()
    else:
        data = asdict(extraction)

    out = dict(data)
    # Harmonização de campos de compatibilidade com o scraper/tracker legado
    if out.get("url"):
        out["page_url"] = out["url"]
    if out.get("tgp_w") is not None:
        try:
            out["tgp_w"] = int(out["tgp_w"])
        except (TypeError, ValueError):
            out["tgp_w"] = None
    if out.get("os_status"):
        out["os_status"] = str(out["os_status"])
    if out.get("keyboard_layout"):
        out["keyboard_layout"] = str(out["keyboard_layout"])
    return out


def from_legacy_dict(spec: dict[str, Any]) -> LaptopSpecExtraction:
    """Instancia um contrato tipado LaptopSpecExtraction a partir de um spec legado da V9."""
    if not isinstance(spec, dict):
        spec = {}

    fields_map = {
        "url": spec.get("url") or spec.get("page_url"),
        "marca": spec.get("marca"),
        "submarca": spec.get("submarca"),
        "cpu_modelo": spec.get("cpu_modelo"),
        "cpu_str_original": spec.get("cpu_str_original"),
        "cpu_classe": spec.get("cpu_classe"),
        "gpu_modelo": spec.get("gpu_modelo"),
        "gpu_tipo": str(spec.get("gpu_tipo") or "desconhecida"),
        "tgp_w": spec.get("tgp_w"),
        "vram_gb": spec.get("vram_gb"),
        "ram_gb": spec.get("ram_gb"),
        "ram_type": spec.get("ram_type"),
        "ram_expansivel": bool(spec.get("ram_expansivel", False)),
        "armazenamento_tb": spec.get("armazenamento_tb"),
        "ssd_expansivel": bool(spec.get("ssd_expansivel", False)),
        "bateria_wh": spec.get("bateria_wh"),
        "peso_kg": spec.get("peso_kg"),
        "ecra_tamanho": spec.get("ecra_tamanho"),
        "ecra_res": spec.get("ecra_res"),
        "ecra_painel": spec.get("ecra_painel"),
        "ecra_hz": spec.get("ecra_hz"),
        "ecra_brightness_nits": spec.get("ecra_brightness_nits"),
        "ecra_srgb_percent": spec.get("ecra_srgb_percent"),
        "os_status": str(spec.get("os_status") or "unknown"),
        "keyboard_layout": str(spec.get("keyboard_layout") or "unknown"),
        "is_new_condition": bool(spec.get("is_new_condition", True)),
        "ean": spec.get("ean"),
        "mpn": spec.get("mpn"),
        "sku": spec.get("sku"),
    }
    # Sanitização segura de inteiros/floats
    if fields_map["tgp_w"] is not None:
        try:
            fields_map["tgp_w"] = int(fields_map["tgp_w"])
        except (TypeError, ValueError):
            fields_map["tgp_w"] = None

    if HAS_PYDANTIC:
        return LaptopSpecExtraction(**fields_map)
    return LaptopSpecExtraction(**fields_map)


def decision_from_assessment(item: dict[str, Any], spec: dict[str, Any], assessment: dict[str, Any]) -> DealDecision:
    """Converte o resultado do tracker/scoring da V9 para o contrato DealDecision."""
    price = float(item.get("preco") or 0.0)
    inst_cost = float(assessment.get("installation_cost_eur") or (110.0 if spec.get("os_status") == "none" else 0.0))
    total = float(assessment.get("purchase_total_eur") or (price + inst_cost))
    status = str(assessment.get("status") or "REJEITADO").upper()
    tier = str(assessment.get("tier") or "SEM_TIER").upper()
    value_score = float(assessment["value_score"]) if assessment.get("value_score") is not None else None
    eligible = bool(status == "ACEITE" and value_score is not None)

    # Notificação estritamente restrita a DIAMANTE >= 120 e elegível
    should_notify = bool(eligible and tier == "DIAMANTE" and (value_score or 0.0) >= 120.0 and item.get("stock") is not False)

    rejection_reason = None
    if not eligible:
        alerts = assessment.get("alertas") or []
        rejection_reason = alerts[0] if alerts else "Oferta rejeitada pelos critérios de seleção"

    decision_data = {
        "url": str(item.get("url") or spec.get("page_url") or ""),
        "loja": str(item.get("loja") or ""),
        "titulo": str(item.get("titulo") or ""),
        "price": price,
        "installation_cost_eur": inst_cost,
        "purchase_total_eur": round(total, 2),
        "value_score": round(value_score, 2) if value_score is not None else None,
        "tier": tier if tier in ("DIAMANTE", "OURO", "PRATA", "BRONZE", "SEM_TIER", "REJEITADO") else "SEM_TIER",
        "status": "ACEITE" if status == "ACEITE" else "REJEITADO",
        "eligible": eligible,
        "rejection_reason": rejection_reason,
        "should_notify_ntfy": should_notify,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if HAS_PYDANTIC:
        return DealDecision(**decision_data)
    return DealDecision(**decision_data)


def merge_official_specs(
    extraction: LaptopSpecExtraction,
    official_spec: dict[str, Any],
    source_name: str,
    source_url: str = "",
) -> tuple[LaptopSpecExtraction, list[str]]:
    """Funde especificações oficiais de fabricante no contrato LaptopSpecExtraction.

    Verifica campos essenciais (CPU, GPU) para vetar incompatibilidade de variantes.
    Preenche campos suplementares em falta (TGP, nits, sRGB, bateria, peso, tipo de RAM).
    Devolve uma cópia enriquecida e a lista de campos fundidos. Em caso de conflito,
    a fusão é abortada e devolve (extraction, []).
    """
    current_dict = to_legacy_dict(extraction)

    def _clean(val: Any) -> str:
        return str(val or "").strip().lower()

    # Validação estrita de conflito nos campos nucleares
    conflicts = []
    for field_name in ("cpu_modelo", "gpu_modelo"):
        curr_val = current_dict.get(field_name)
        off_val = official_spec.get(field_name)
        if curr_val and off_val and _clean(curr_val) not in _clean(off_val) and _clean(off_val) not in _clean(curr_val):
            conflicts.append(field_name)

    if conflicts:
        return extraction, []

    merged_fields = []
    supplemental_fields = (
        "tgp_w",
        "ecra_brightness_nits",
        "ecra_srgb_percent",
        "bateria_wh",
        "peso_kg",
        "ecra_hz",
        "ecra_res",
        "ecra_painel",
        "ram_type",
    )

    for field_name in supplemental_fields:
        curr_val = current_dict.get(field_name)
        off_val = official_spec.get(field_name)
        if (curr_val is None or curr_val == "" or curr_val == "desconhecido" or curr_val == "desconhecida") and off_val is not None:
            current_dict[field_name] = off_val
            merged_fields.append(field_name)

    for bool_field in ("ram_expansivel", "ssd_expansivel"):
        if official_spec.get(bool_field) is True and not current_dict.get(bool_field):
            current_dict[bool_field] = True
            merged_fields.append(bool_field)

    enriched_contract = from_legacy_dict(current_dict)
    return enriched_contract, merged_fields
