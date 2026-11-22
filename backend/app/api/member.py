"""Members' recipe ratings and receipt points (owner request 2026-11-22)."""

from __future__ import annotations

from typing import Any

from app.api.beta_ops import _require_same_origin
from app.config import get_settings
from app.services import member_rewards as rewards
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/member", tags=["member"])
PDF_LIMIT = 5 * 1024 * 1024


def _store(request):
    from app.api.plan import _store as plan_store

    return plan_store(request)


def _member(request, response, *, mutation=False):
    from app.api.account import verified_owner

    if mutation:
        _require_same_origin(request, get_settings())
    response.headers["Cache-Control"] = "private, no-store"
    owner = verified_owner(request)
    if not owner:
        raise HTTPException(401, "Logga in som medlem för att gilla recept och samla poäng.")
    return owner


def _fail(exc):
    raise HTTPException(422, str(exc)) from exc


class Rating(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int = Field(ge=-1, le=1)


@router.get("/recipe-ratings")
def recipe_ratings(request: Request, response: Response, ids: str = Query(default="", max_length=6000)):
    from app.api.account import verified_owner

    response.headers["Cache-Control"] = "private, no-store"
    return {"ratings": rewards.ratings(_store(request), [i for i in ids.split(",") if i], verified_owner(request)),
            "member": bool(verified_owner(request))}


@router.put("/recipe-ratings/{base_id}")
def rate_recipe(base_id: str, payload: Rating, request: Request, response: Response):
    owner = _member(request, response, mutation=True)
    try:
        rewards.rate(_store(request), owner, base_id, payload.value)
    except rewards.RewardError as exc:
        _fail(exc)
    return {"ratings": rewards.ratings(_store(request), [base_id], owner)}


@router.get("/points")
def points(request: Request, response: Response):
    owner = _member(request, response)
    return rewards.points_summary(_store(request), owner)


@router.post("/receipts/pdf-text")
async def pdf_text(request: Request, response: Response):
    """Text of a digital receipt (PDF). The file itself is not kept."""
    _member(request, response, mutation=True)
    body = await request.body()
    if len(body) > PDF_LIMIT:
        raise HTTPException(413, "Kvittot är för stort. Högst 5 MB.")
    if not body.startswith(b"%PDF"):
        raise HTTPException(422, "Välj en PDF eller fota kvittot.")
    try:
        import fitz

        with fitz.open(stream=body, filetype="pdf") as document:
            text = "\n".join(page.get_text() for page in list(document)[:6])
    except Exception as exc:  # a broken or encrypted file
        raise HTTPException(422, "PDF:en gick inte att läsa. Fota kvittot i stället.") from exc
    if not text.strip():
        raise HTTPException(422, "PDF:en innehåller ingen text, bara en bild. Fota kvittot i stället.")
    return {"text": text[:50_000]}


class ReceiptLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = Field(min_length=1, max_length=120)
    price: float = Field(gt=0, le=5000)
    quantity: float | None = Field(default=None, gt=0, le=1000)
    unit: str | None = Field(default=None, max_length=4)
    unit_price: float | None = Field(default=None, gt=0, le=5000)
    gtin: str | None = Field(default=None, pattern=r"^\d{8,14}$")


class ReceiptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=80)
    text: str | None = Field(default=None, max_length=50_000)
    store_text: str | None = Field(default=None, max_length=120)
    purchased_on: str | None = Field(default=None, pattern=r"^20\d\d-\d\d-\d\d$")
    lines: list[ReceiptLine] | None = Field(default=None, max_length=80)


def _evaluate(request, owner, payload):
    from app.services.planning_rules import load
    from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

    store = _store(request)
    response_json = rewards.load_plan(store, owner, payload.plan_id)
    if payload.lines is not None:
        parsed = {"store_text": payload.store_text or "", "chain": None, "purchased_on": payload.purchased_on,
                  "lines": [line.model_dump(exclude_none=True) for line in payload.lines]}
        if not parsed["store_text"]:
            raise rewards.RewardError("Skriv vilken butik kvittot är från.")
    elif payload.text:
        parsed = rewards.parse_receipt(payload.text)
    else:
        raise rewards.RewardError("Fota kvittot eller välj en PDF.")
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(response_json.get("postal_code") or "22350", {})
    known = [{"store_id": s.store_id, "name": s.name, "chain": s.chain} for s in (prepared.stores if prepared else ())]
    products = (lambda store_id: _store_products(prepared, store_id)) if prepared else None
    return parsed, rewards.evaluate(parsed, response_json, load(), known, store_text=payload.store_text,
                                    store_products=products)


_CATALOGUES: dict = {}


def _store_products(prepared, store_ids):
    """Smako's products in one store (all its price contexts), kept for the loaded price universe."""
    key = (prepared.universe.universe_id, store_ids)
    if key not in _CATALOGUES:
        if len(_CATALOGUES) > 8:
            _CATALOGUES.clear()
        _CATALOGUES[key] = rewards.StoreProducts(
            {"name": p.name, "brand": p.brand, "price": p.price, "effective_price": p.effective_price,
             "member_price": p.member_price, "gtin": p.gtin, "offer_prices": rewards.offer_prices(p.offers),
             "sizes": rewards.sizes(f"{p.package_quantity:g} {p.package_unit}") if p.package_quantity and p.package_unit else {}}
            for p in prepared.universe.products if p.store_id in store_ids)
    return _CATALOGUES[key]


@router.post("/receipts/preview")
def preview(payload: ReceiptRequest, request: Request, response: Response) -> dict[str, Any]:
    owner = _member(request, response, mutation=True)
    try:
        _parsed, result = _evaluate(request, owner, payload)
    except rewards.RewardError as exc:
        _fail(exc)
    return result


@router.post("/receipts", status_code=201)
def claim(payload: ReceiptRequest, request: Request, response: Response) -> dict[str, Any]:
    from app.services.planning_rules import load

    owner = _member(request, response, mutation=True)
    if payload.lines is None:
        raise HTTPException(422, "Bekräfta kvittots rader först.")
    try:
        _parsed, result = _evaluate(request, owner, payload)
        return {**rewards.save_receipt(_store(request), owner, payload.plan_id, result, load()), "result": result}
    except rewards.RewardError as exc:
        _fail(exc)
