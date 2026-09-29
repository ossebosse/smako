"""One authoritative interpretation of product quantity and checkout cost."""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal

from app.models.product import (
    CanonicalUnit,
    ProductSemantics,
    QuantityConfidence,
    SaleModel,
)
from pydantic import BaseModel, ConfigDict, Field, computed_field

_CENT = Decimal("0.01")
_CanonicalDimension = Literal["g", "ml", "st"]


class PurchaseResolution(BaseModel):
    """Resolved physical purchase and its monetary consequence.

    Decimal values are retained until an API/presentation boundary.  An
    unresolved result is data, not a fabricated zero-price purchase, and must
    therefore be rejected by a verified-basket policy.
    """

    model_config = ConfigDict(frozen=True)

    sale_model: SaleModel
    resolved: bool
    required_quantity: Decimal = Field(gt=0)
    required_unit: CanonicalUnit
    packages_needed: int | None = Field(default=None, ge=1)
    purchased_quantity: Decimal | None = Field(default=None, gt=0)
    purchased_unit: CanonicalUnit | None = None
    purchased_usable_quantity: Decimal | None = Field(default=None, gt=0)
    usable_unit: CanonicalUnit | None = None
    waste_quantity: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, gt=0)
    total_price: Decimal | None = Field(default=None, gt=0)
    quantity_confidence: QuantityConfidence
    warning: str | None = None
    error: str | None = None

    @computed_field
    @property
    def uses_estimate(self) -> bool:
        return self.quantity_confidence == QuantityConfidence.ESTIMATED


def _decimal(value: float | Decimal) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result <= 0:
        raise ValueError("quantity and price values must be finite and greater than zero")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _unit_definition(unit: str) -> tuple[_CanonicalDimension, Decimal] | None:
    normalized = unit.strip().lower().replace(" ", "")
    for prefix in ("sek/", "kr/"):
        normalized = normalized.removeprefix(prefix)
    definitions: dict[str, tuple[_CanonicalDimension, Decimal]] = {
        "g": ("g", Decimal(1)),
        "gram": ("g", Decimal(1)),
        "kg": ("g", Decimal(1000)),
        "ml": ("ml", Decimal(1)),
        "l": ("ml", Decimal(1000)),
        "liter": ("ml", Decimal(1000)),
        "litre": ("ml", Decimal(1000)),
        "st": ("st", Decimal(1)),
        "styck": ("st", Decimal(1)),
        "piece": ("st", Decimal(1)),
    }
    return definitions.get(normalized)


def _to_base(quantity: Decimal, unit: str) -> tuple[Decimal, _CanonicalDimension] | None:
    definition = _unit_definition(unit)
    if definition is None:
        return None
    dimension, factor = definition
    return quantity * factor, dimension


def project_purchase_shape(product):
    """Interpret source weight evidence without granting price eligibility.

    The shared matcher needs the physical form before request-specific price
    selection. This local projection never changes the retained source row.
    """
    terms = product.purchase_terms
    if not terms or terms.usage != 'estimated':
        return product
    quantity = terms.approximate_package_g or terms.minimum_package_g
    return product.model_copy(update={
        'sale_model': SaleModel.VARIABLE_WEIGHT_PACKAGE if terms.purchase_form == 'variable_package' else SaleModel.SOLD_BY_WEIGHT,
        'package_quantity': quantity, 'package_unit': 'g' if quantity else None,
        'usable_quantity': quantity, 'usable_unit': 'g' if quantity else None,
        'quantity_confidence': QuantityConfidence.ESTIMATED,
        'variable_weight': terms.purchase_form == 'loose_weight',
        'sale_unit': 'kg',
    })


class PurchaseQuantityResolver:
    """Resolve all supported sale models without comparison-price inference.

    A comparison price is used as a rate only after an upstream interpreter has
    explicitly classified the product as sold by weight or variable-weight.
    It is never converted into a package size.
    """

    def resolve(
        self,
        product: ProductSemantics,
        *,
        required_quantity: float | Decimal,
        required_unit: CanonicalUnit,
    ) -> PurchaseResolution:
        product = project_purchase_shape(product)
        required = _decimal(required_quantity)
        if product.purchase_terms and (product.purchase_terms.usage == 'blocked' or (product.purchase_terms.usage == 'variant_selection_required' and not product.conditional_variant_choice)):
            return self._unresolved(product, required, required_unit, 'unresolved purchase evidence')
        required_base = _to_base(required, required_unit)
        if required_base is None:  # pragma: no cover - CanonicalUnit prevents this
            raise ValueError(f"unsupported required unit: {required_unit}")

        handlers = {
            SaleModel.FIXED_PACKAGE: self._fixed_package,
            SaleModel.SOLD_BY_WEIGHT: self._sold_by_weight,
            SaleModel.SOLD_BY_PIECE: self._sold_by_piece,
            SaleModel.VARIABLE_WEIGHT_PACKAGE: self._variable_weight_package,
        }
        handler = handlers.get(product.sale_model)
        if handler is None:
            return self._unresolved(
                product,
                required,
                required_unit,
                "purchase model is unknown",
            )
        return handler(product, required, required_unit)

    def _fixed_package(
        self,
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
    ) -> PurchaseResolution:
        if (
            product.package_quantity is None
            or product.package_unit is None
            or product.usable_quantity is None
            or product.usable_unit is None
        ):
            return self._unresolved(
                product,
                required,
                required_unit,
                "fixed package requires explicit package and usable quantities",
            )
        usable = _to_base(_decimal(product.usable_quantity), product.usable_unit)
        required_base = _to_base(required, required_unit)
        package = _to_base(_decimal(product.package_quantity), product.package_unit)
        assert required_base is not None and usable is not None and package is not None
        if usable[1] != required_base[1]:
            return self._incompatible(product, required, required_unit, usable[1])
        if package[1] == usable[1] and usable[0] > package[0]:
            return self._unresolved(
                product,
                required,
                required_unit,
                "usable quantity cannot exceed gross package quantity",
            )

        package_count = _ceil(required_base[0] / usable[0])
        if product.purchase_terms and product.purchase_terms.complete_group_size > 1:
            multiple = product.purchase_terms.complete_group_size
            package_count = _ceil(Decimal(package_count) / multiple) * multiple
        purchased_usable = usable[0] * package_count
        purchased = package[0] * package_count
        # Offers-only multibuys can lack an independently purchasable unit.
        # The quantity stage may use the retained ranking signal; the checkout
        # resolver still has to cover the actual complete package count.
        cost_signal = product.sale_price if product.sale_price is not None else getattr(product, 'effective_price', None)
        if cost_signal is None:
            return self._unresolved(product, required, required_unit, 'missing checkout ranking evidence')
        total = _money(_decimal(cost_signal) * package_count)
        return PurchaseResolution(
            sale_model=product.sale_model,
            resolved=True,
            required_quantity=required_base[0],
            required_unit=required_base[1],
            packages_needed=package_count,
            purchased_quantity=purchased,
            purchased_unit=package[1],
            purchased_usable_quantity=purchased_usable,
            usable_unit=usable[1],
            waste_quantity=purchased_usable - required_base[0],
            unit_price=_money(_decimal(cost_signal)),
            total_price=total,
            quantity_confidence=product.quantity_confidence,
        )

    def _sold_by_weight(
        self,
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
    ) -> PurchaseResolution:
        required_base = _to_base(required, required_unit)
        assert required_base is not None
        if required_base[1] not in {"g", "ml"}:
            return self._incompatible(product, required, required_unit, "weight/volume")

        rate = self._rate(product)
        if rate is None:
            return self._unresolved(
                product,
                required,
                required_unit,
                "sold-by-weight product requires an explicit sale or comparison rate",
            )
        rate_price, rate_dimension, rate_factor = rate
        if rate_dimension != required_base[1]:
            return self._incompatible(product, required, required_unit, rate_dimension)

        # A positive checkout cost smaller than half a cent still resolves to
        # the minimum representable currency amount; never construct a
        # supposedly resolved result whose unit_price is invalid zero.
        total = max(_CENT, _money(required_base[0] * rate_price / rate_factor))
        confidence = product.quantity_confidence
        if product.purchase_terms:
            confidence = QuantityConfidence.ESTIMATED
        if confidence in {QuantityConfidence.EXACT, QuantityConfidence.DERIVED}:
            confidence = QuantityConfidence.DERIVED
        return PurchaseResolution(
            sale_model=product.sale_model,
            resolved=True,
            required_quantity=required_base[0],
            required_unit=required_base[1],
            packages_needed=1,
            purchased_quantity=required_base[0],
            purchased_unit=required_base[1],
            purchased_usable_quantity=required_base[0],
            usable_unit=required_base[1],
            waste_quantity=Decimal(0),
            unit_price=total,
            total_price=total,
            quantity_confidence=confidence,
            warning=(
                "cost is derived from actual purchased weight"
                if confidence != QuantityConfidence.UNKNOWN
                else "weight rate is known but source quantity confidence is unknown"
            ),
        )

    def _sold_by_piece(
        self,
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
    ) -> PurchaseResolution:
        piece_price = product.piece_price
        if piece_price is None:
            return self._unresolved(
                product,
                required,
                required_unit,
                "sold-by-piece product requires piece_price",
            )
        required_base = _to_base(required, required_unit)
        assert required_base is not None
        if required_base[1] == "st":
            pieces = _ceil(required_base[0])
            if product.purchase_terms:
                multiple = product.purchase_terms.complete_group_size
                pieces = _ceil(Decimal(pieces) / multiple) * multiple
            purchased_usable = Decimal(pieces)
            usable_unit: CanonicalUnit = "st"
            confidence = (
                QuantityConfidence.DERIVED
                if product.quantity_confidence != QuantityConfidence.UNKNOWN
                else QuantityConfidence.UNKNOWN
            )
        else:
            if product.estimated_piece_weight is None:
                return self._unresolved(
                    product,
                    required,
                    required_unit,
                    "weight requirement for piece product needs estimated_piece_weight",
                )
            estimated = _to_base(
                _decimal(product.estimated_piece_weight),
                product.estimated_piece_weight_unit,
            )
            assert estimated is not None
            if estimated[1] != required_base[1]:
                return self._incompatible(product, required, required_unit, estimated[1])
            pieces = _ceil(required_base[0] / estimated[0])
            purchased_usable = estimated[0] * pieces
            usable_unit = estimated[1]
            confidence = QuantityConfidence.ESTIMATED

        total = _money(_decimal(piece_price) * pieces)
        return PurchaseResolution(
            sale_model=product.sale_model,
            resolved=True,
            required_quantity=required_base[0],
            required_unit=required_base[1],
            packages_needed=pieces,
            purchased_quantity=Decimal(pieces),
            purchased_unit="st",
            purchased_usable_quantity=purchased_usable,
            usable_unit=usable_unit,
            waste_quantity=purchased_usable - required_base[0],
            unit_price=_money(_decimal(piece_price)),
            total_price=total,
            quantity_confidence=confidence,
            warning=(
                "piece count is based on estimated piece weight"
                if confidence == QuantityConfidence.ESTIMATED
                else None
            ),
        )

    def _variable_weight_package(
        self,
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
    ) -> PurchaseResolution:
        if (
            product.package_quantity is None
            or product.package_unit is None
            or product.usable_quantity is None
            or product.usable_unit is None
        ):
            return self._unresolved(
                product,
                required,
                required_unit,
                "variable-weight package requires an explicit approximate package quantity",
            )
        required_base = _to_base(required, required_unit)
        package = _to_base(_decimal(product.package_quantity), product.package_unit)
        usable = _to_base(_decimal(product.usable_quantity), product.usable_unit)
        assert required_base is not None and package is not None and usable is not None
        if usable[1] != required_base[1]:
            return self._incompatible(product, required, required_unit, usable[1])
        if package[1] == usable[1] and usable[0] > package[0]:
            return self._unresolved(
                product,
                required,
                required_unit,
                "usable quantity cannot exceed gross package quantity",
            )
        if product.quantity_confidence == QuantityConfidence.UNKNOWN:
            return self._unresolved(
                product,
                required,
                required_unit,
                "variable package weight confidence is unknown",
            )

        package_count = _ceil(required_base[0] / usable[0])
        purchased = package[0] * package_count
        purchased_usable = usable[0] * package_count
        rate = self._rate(product)
        if rate is not None and rate[1] == package[1]:
            total = _money(purchased * rate[0] / rate[2])
        else:
            # This is explicitly only an estimate for a representative package.
            total = _money(_decimal(product.sale_price) * package_count)
        return PurchaseResolution(
            sale_model=product.sale_model,
            resolved=True,
            required_quantity=required_base[0],
            required_unit=required_base[1],
            packages_needed=package_count,
            purchased_quantity=purchased,
            purchased_unit=package[1],
            purchased_usable_quantity=purchased_usable,
            usable_unit=usable[1],
            waste_quantity=purchased_usable - required_base[0],
            unit_price=_money(total / package_count),
            total_price=total,
            quantity_confidence=QuantityConfidence.ESTIMATED,
            warning=(f"Cirka-vikt och beräknad kostnad för {package_count} hela paket; "
                     f"välj sammanlagt minst {required_base[0]} {required_base[1]} användbar mängd. "
                     "Slutbelopp och överskott beror på faktisk paketvikt.") if product.purchase_terms else "variable package weight and total are estimates",
        )

    @staticmethod
    def _rate(
        product: ProductSemantics,
    ) -> tuple[Decimal, _CanonicalDimension, Decimal] | None:
        if product.sale_unit is not None:
            definition = _unit_definition(product.sale_unit)
            if definition is not None:
                return _decimal(product.sale_price), definition[0], definition[1]
        if product.comparison_price is not None and product.comparison_unit is not None:
            definition = _unit_definition(product.comparison_unit)
            if definition is not None:
                return _decimal(product.comparison_price), definition[0], definition[1]
        if (
            product.sale_model == SaleModel.SOLD_BY_WEIGHT
            and product.variable_weight
            and product.package_quantity is not None
            and product.package_unit is not None
        ):
            # Backward compatibility for the old explicit ``variable_weight``
            # contract: sale_price covered the supplied reference quantity.
            # This uses actual package/reference metadata and never a
            # comparison-price unit to manufacture package size.
            reference = _to_base(_decimal(product.package_quantity), product.package_unit)
            if reference is not None:
                return _decimal(product.sale_price), reference[1], reference[0]
        return None

    @staticmethod
    def _unresolved(
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
        error: str,
    ) -> PurchaseResolution:
        required_base = _to_base(required, required_unit)
        assert required_base is not None
        return PurchaseResolution(
            sale_model=product.sale_model,
            resolved=False,
            required_quantity=required_base[0],
            required_unit=required_base[1],
            quantity_confidence=QuantityConfidence.UNKNOWN,
            error=error,
        )

    def _incompatible(
        self,
        product: ProductSemantics,
        required: Decimal,
        required_unit: CanonicalUnit,
        product_dimension: str,
    ) -> PurchaseResolution:
        return self._unresolved(
            product,
            required,
            required_unit,
            f"incompatible required unit {required_unit!r} and product dimension "
            f"{product_dimension!r}",
        )


__all__ = ["PurchaseQuantityResolver", "PurchaseResolution"]
