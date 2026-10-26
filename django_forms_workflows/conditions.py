"""
Evaluate trigger_conditions against form submission data.

Condition format (same as FormField.conditional_rules):

    {
        "operator": "AND" | "OR",
        "conditions": [
            {
                "field": "field_name",
                "operator": "equals" | "not_equals" | "gt" | "lt" |
                            "gte" | "lte" | "contains" | "in",
                "value": <expected_value>
            },
            ...
        ]
    }

``evaluate_conditions(conditions, data)`` returns ``True`` when the
submission data satisfies the rule set, or when ``conditions`` is
``None`` / empty (unconditional).
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)


def extract_target_value(form_data: dict | None) -> int:
    """Extract and normalize numerical target value from submission form data.

    Supports:
    1. Direct 'nilai_target' (integer, float, or formatted currency string e.g. 'Rp 80.000.000').
    2. 'target_incentive' JSON string / list with [{'target_bulanan': 80000000, ...}].
    3. 'tier_support' JSON string / list with [{'target_tahunan': 80000000, ...}].
    """
    if not form_data or not isinstance(form_data, dict):
        return 0

    # 1. Cek jika nilai_target sudah ada dan bernilai valid
    raw_val = form_data.get("nilai_target")
    if raw_val is not None and str(raw_val).strip() != "":
        coerced = _coerce_numeric(raw_val)
        if coerced is not None and coerced > 0:
            return int(coerced)

    # 2. Ekstrak dari target_incentive (JSON string array atau list dict)
    raw_incentive = form_data.get("target_incentive")
    if raw_incentive:
        try:
            if isinstance(raw_incentive, str):
                data_list = json.loads(raw_incentive)
            else:
                data_list = raw_incentive

            if isinstance(data_list, list) and len(data_list) > 0:
                targets = []
                for item in data_list:
                    if isinstance(item, dict):
                        tb = item.get("target_bulanan")
                        if tb is not None:
                            coerced_tb = _coerce_numeric(tb)
                            if coerced_tb is not None:
                                targets.append(int(coerced_tb))
                if targets:
                    return max(targets)
        except Exception:
            pass

    # 3. Fallback: Ekstrak dari tier_support jika ada target_tahunan
    raw_tier = form_data.get("tier_support")
    if raw_tier:
        try:
            if isinstance(raw_tier, str):
                tier_list = json.loads(raw_tier)
            else:
                tier_list = raw_tier

            if isinstance(tier_list, list) and len(tier_list) > 0:
                tier_targets = []
                for item in tier_list:
                    if isinstance(item, dict):
                        tt = item.get("target_tahunan")
                        if tt is not None:
                            coerced_tt = _coerce_numeric(tt)
                            if coerced_tt is not None:
                                tier_targets.append(int(coerced_tt))
                if tier_targets and max(tier_targets) > 0:
                    return max(tier_targets)
        except Exception:
            pass

    return 0


def _coerce_numeric(val: Any) -> Decimal | None:
    """Try to coerce a value to Decimal for numeric comparisons.
    Handles int, float, Decimal, and formatted currency strings (e.g. 'Rp 80.000.000', '80,000,000').
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    val_str = str(val).strip()
    try:
        return Decimal(val_str)
    except (InvalidOperation, ValueError, TypeError):
        pass

    # Clean non-numeric characters (strip Rp, commas/dots as thousands)
    cleaned = re.sub(r"[^\d.,\-]", "", val_str)
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and parts[0] != "0"):
            cleaned = cleaned.replace(".", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and parts[0] != "0"):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _is_empty_value(actual: Any) -> bool:
    """Return True when ``actual`` represents an empty / absent value."""
    if actual is None:
        return True
    if isinstance(actual, str):
        return actual.strip() == ""
    if isinstance(actual, list | dict):
        return len(actual) == 0
    return False


def _evaluate_single(condition: dict, data: dict) -> bool:
    """Evaluate a single condition dict against submission data."""
    field = condition.get("field", "")
    raw_operator = str(condition.get("operator", "equals")).strip()
    operator_map = {
        ">=": "gte",
        "<=": "lte",
        ">": "gt",
        "<": "lt",
        "==": "equals",
        "=": "equals",
        "!=": "not_equals",
        "<>": "not_equals",
    }
    operator = operator_map.get(raw_operator, raw_operator.lower())
    expected = condition.get("value")

    actual = data.get(field) if isinstance(data, dict) else None

    # Fallback normalizer for 'nilai_target' if missing or None
    if field == "nilai_target" and (actual is None or str(actual).strip() in ("", "None", "0")):
        extracted = extract_target_value(data)
        if extracted:
            actual = extracted
            if isinstance(data, dict):
                data["nilai_target"] = extracted

    # Presence / absence operators (no expected value needed)
    if operator == "not_empty":
        return not _is_empty_value(actual)

    if operator == "is_empty":
        return _is_empty_value(actual)

    # Normalise to strings for simple comparisons
    actual_str = str(actual).strip() if actual is not None else ""
    expected_str = str(expected).strip() if expected is not None else ""

    if operator == "equals":
        return actual_str.lower() == expected_str.lower()

    if operator == "not_equals":
        return actual_str.lower() != expected_str.lower()

    if operator == "contains":
        return expected_str.lower() in actual_str.lower()

    if operator == "in":
        # expected should be a list; check if actual is in it
        if isinstance(expected, list):
            return actual_str.lower() in [str(v).strip().lower() for v in expected]
        # Fallback: comma-separated string
        return actual_str.lower() in [
            v.strip().lower() for v in expected_str.split(",")
        ]

    # Numeric comparisons
    actual_num = _coerce_numeric(actual)
    expected_num = _coerce_numeric(expected)
    if actual_num is None or expected_num is None:
        logger.debug(
            "Non-numeric comparison attempted: field=%s op=%s actual=%r expected=%r",
            field,
            operator,
            actual,
            expected,
        )
        return False

    if operator == "gt":
        return actual_num > expected_num
    if operator == "lt":
        return actual_num < expected_num
    if operator == "gte":
        return actual_num >= expected_num
    if operator == "lte":
        return actual_num <= expected_num

    logger.warning("Unknown condition operator: %s", operator)
    return False


def evaluate_conditions(conditions: dict | None, data: dict) -> bool:
    """Evaluate a trigger_conditions rule set against form data.

    Supports two formats:

    *Compound* (multi-condition group)::

        {
            "operator": "AND" | "OR",
            "conditions": [
                {"field": "foo", "operator": "equals", "value": "bar"},
                ...
            ]
        }

    *Simple* (single condition, no wrapping ``conditions`` list)::

        {"field": "foo", "operator": "not_empty"}

    Returns ``True`` when:
    - ``conditions`` is ``None`` or an empty dict (unconditional — always matches)
    - The condition(s) evaluate to True according to the configured logic
    """
    if not conditions:
        return True

    condition_list = conditions.get("conditions")

    # Simple single-condition format: {"field": "...", "operator": "..."}
    if not condition_list:
        if "field" in conditions:
            return _evaluate_single(conditions, data)
        # No conditions key and no field key — unconditional
        return True

    group_operator = conditions.get("operator", "AND").upper()

    results = [_evaluate_single(c, data) for c in condition_list]

    if group_operator == "OR":
        return any(results)
    # Default: AND
    return all(results)
