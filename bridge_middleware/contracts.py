"""Strong contracts for bridge batch request/response payloads."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BatchRequest(BaseModel):
    """Request contract for the unified bridge batch endpoint."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["swing", "vol"] = "swing"
    date: str | None = None
    symbols: list[str] | None = None
    limit: int = Field(default=50, ge=0)
    # Keep aligned with VA's swing decision gate (0.50 + 0.05 neutral buffer).
    min_direction_score: float = 0.55
    # Keep aligned with VA vol decision gate (0.07 + 0.05 neutral buffer).
    min_vol_score: float = 0.12
    vix_override: float | None = None
    filtering: dict[str, Any] = Field(default_factory=dict)
    sorting: dict[str, Any] = Field(default_factory=dict)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return None

        date_str = value.strip()
        if not date_str:
            return None
        if not _DATE_PATTERN.match(date_str):
            raise ValueError("date must match YYYY-MM-DD")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must be a valid calendar date in YYYY-MM-DD") from exc
        return date_str

    @field_validator("symbols", mode="before")
    @classmethod
    def validate_symbols_input(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("symbols must be a list[str]")
        return value

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str] | None) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in symbols or []:
            if not isinstance(raw, str):
                raise ValueError("symbols must contain only strings")
            symbol = raw.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            cleaned.append(symbol)
        return cleaned


class SwingMarketParams(BaseModel):
    """Market parameter payload required by swing rows."""

    model_config = ConfigDict(extra="forbid")

    vix: float
    ivr: float
    iv30: float
    hv20: float
    iv_path: str
    earning_date: str | None = None
    beta: float | None = None


class SwingBatchRow(BaseModel):
    """Result row shape for source=swing."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    market_params: SwingMarketParams
    bridge: dict[str, Any]


class VolBatchRow(BaseModel):
    """Result row shape for source=vol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    bridge: dict[str, Any]


class BatchError(BaseModel):
    """Structured error item in batch response envelope."""

    model_config = ConfigDict(extra="forbid")

    message: str
    symbol: str | None = None
    code: str | None = None
    detail: dict[str, Any] | None = None


class BatchResponse(BaseModel):
    """Unified response envelope for bridge batch calls."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    source: Literal["swing", "vol"]
    date: str | None = None
    requested_date: str | None = None
    fallback_used: bool = False
    count: int = 0
    results: list[SwingBatchRow | VolBatchRow] = Field(default_factory=list)
    errors: list[BatchError] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_source_specific_rows(self) -> "BatchResponse":
        validated_results: list[SwingBatchRow | VolBatchRow] = []

        for row in self.results:
            payload = row.model_dump() if isinstance(row, BaseModel) else row
            try:
                if self.source == "swing":
                    validated_results.append(SwingBatchRow.model_validate(payload))
                else:
                    validated_results.append(VolBatchRow.model_validate(payload))
            except ValidationError:
                raise
            except Exception as exc:
                raise ValueError(f"invalid row for source={self.source}: {exc}") from exc

        self.results = validated_results
        self.count = len(validated_results)
        return self
