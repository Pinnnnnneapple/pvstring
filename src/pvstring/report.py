"""Portable, dependency-free renderers for pvstring design results."""

from __future__ import annotations

import html
import json
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .calc import DesignResult


_DISCLAIMER = (
    "Design aid only. Verify manufacturer specifications and installation instructions, "
    "applicable local electrical codes, and site conditions. Obtain qualified professional "
    "review and licensed professional sign-off before installation."
)


def _text(value):
    return html.escape(str(value), quote=True)


def _status_badge(value):
    # Only fixed classes can reach the attribute; unknown statuses remain escaped text.
    classes = {"PASS": "status-pass", "WARN": "status-warn", "FAIL": "status-fail"}
    return '<span class="badge {}">{}</span>'.format(classes.get(str(value), "status-unknown"), _text(value))


def _number(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _fmt(value):
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return "{:,.2f}".format(value).rstrip("0").rstrip(".")
    return "—" if value is None else str(value)


def _candidates(data):
    design = max(1, int(_number(data["array"].get("modules_per_string"), 1)))
    limits = data.get("limits", {})
    low = max(1, int(_number(limits.get("min_modules"), design - 3)))
    high = int(_number(limits.get("max_modules"), design + 3))
    if high < low:
        low, high = max(1, design - 3), design + 3
    window = 40 if low <= design <= high else 39
    if high - low + 1 <= window:
        return sorted(set(range(low, high + 1)) | {design})
    start = max(low, min(design - window // 2, high - window + 1))
    return sorted(set(range(start, start + window)) | {design})


def _voltage_chart(data):
    inv, metrics = data["inverter"], data["metrics"]
    counts = _candidates(data)
    design = int(_number(data["array"].get("modules_per_string"), 1))
    series = (("Cold Voc", "voc_cold", "#7c3aed"),
              ("Hot Vmp", "vmp_hot", "#d97706"),
              ("STC Vmp", None, "#0284c7"))
    bands = (("MPPT operating", "mppt_min", "mppt_max", "#60a5fa"),
             ("Full power MPPT", "full_power_mppt_min", "full_power_mppt_max", "#34d399"))
    values = [_number(metrics.get(key)) if key else _number(data["module"].get("vmp"))
              for _, key, _ in series]
    maximum = max([1.0] + [max(0, v) * max(counts) for v in values] +
                  [_number(inv.get(key)) for key in (
                      "max_dc_voltage", "start_voltage", "mppt_max", "full_power_mppt_max")]) * 1.08
    left, width, top, row = 108, 660, 94, 53
    bottom = top + len(counts) * row
    height = bottom + 52

    def x(value):
        return left + max(0, _number(value)) / maximum * width

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="voltage-title voltage-desc" '
        'viewBox="0 0 820 {}">'.format(height),
        '<title id="voltage-title">String voltage window by modules per string</title>',
        '<desc id="voltage-desc">Three bars per count: cold open-circuit voltage, hot maximum-power '
        'voltage, and STC maximum-power voltage. Shading shows MPPT operating and full-power bands. '
        'Dashed lines show maximum DC and start voltages. The design count is marked with an asterisk. '
        'Up to 40 candidate counts are shown near the design; consult the stated limits for the full range.</desc>',
    ]
    for i, (label, _, color) in enumerate(series):
        parts.append('<rect x="{}" y="10" width="13" height="10" fill="{}"/>'.format(108 + i * 210, color))
        parts.append('<text x="{}" y="20">{}</text>'.format(126 + i * 210, label))
    for i, (label, lo, hi, color) in enumerate(bands):
        if inv.get(lo) is not None and inv.get(hi) is not None:
            lower, upper = _number(inv[lo]), _number(inv[hi])
            if upper >= lower:
                parts.append('<rect x="{:.2f}" y="{}" width="{:.2f}" height="{}" fill="{}" opacity="0.18"/>'.format(
                    x(lower), top, x(upper) - x(lower), bottom - top, color))
                parts.append('<text x="108" y="{}">{}: {}–{} V</text>'.format(
                    42 + i * 19, label, _text(_fmt(lower)), _text(_fmt(upper))))
    for i in range(6):
        value = maximum * i / 5
        parts.append('<path d="M {0:.2f} {1} V {2}" stroke="currentColor" opacity="0.15"/>'.format(x(value), top, bottom))
        parts.append('<text x="{:.2f}" y="{}" text-anchor="middle">{} V</text>'.format(x(value), bottom + 25, _fmt(value)))
    for key, label, dash, offset in (("max_dc_voltage", "Max DC", "6 3", 0),
                                    ("start_voltage", "Start", "2 3", 16)):
        if inv.get(key) is not None:
            pos = x(inv[key])
            parts.append('<path d="M {0:.2f} {1} V {2}" stroke="currentColor" stroke-width="2" stroke-dasharray="{3}"/>'.format(pos, top, bottom, dash))
            parts.append('<text x="{:.2f}" y="{}" text-anchor="end">{}: {} V</text>'.format(
                pos, 77 + offset, label, _text(_fmt(inv[key]))))
    for i, count in enumerate(counts):
        y = top + i * row
        parts.append('<text x="98" y="{}" text-anchor="end">{}{} modules</text>'.format(y + 27, count, "*" if count == design else ""))
        for j, ((label, _, color), value) in enumerate(zip(series, values)):
            voltage = max(0, value * count)
            parts.append('<rect x="108" y="{}" width="{:.2f}" height="10" fill="{}"><title>{}: {} V at {} modules</title></rect>'.format(
                y + j * 13, x(voltage) - left, color, label, _text(_fmt(voltage)), count))
    parts.append('</svg>')
    return "".join(parts)


def _current_bars(data):
    inv, metrics = data["inverter"], data["metrics"]
    strings = list(data["array"].get("strings_per_mppt") or [])
    count = max(len(strings), max(0, int(_number(inv.get("num_mppts")))))
    output = []
    for index in range(count):
        parallel = max(0, _number(strings[index])) if index < len(strings) else 0
        output.append('<section class="mppt"><h3>MPPT {} · {} strings</h3>'.format(index + 1, _fmt(parallel)))
        for label, metric, limit_key in (("Operating current", "imp_hot", "max_input_current_per_mppt"),
                                         ("Design short-circuit current", "isc_design", "max_isc_per_mppt")):
            used = max(0, _number(metrics.get(metric)) * parallel)
            raw_limit = inv.get(limit_key)
            limit = _number(raw_limit)
            available = raw_limit is not None and limit > 0
            percent = min(100, used / limit * 100) if available else 0
            note = "{} A headroom".format(_fmt(limit - used)) if available else "limit unavailable"
            summary = "{}: {} / {} A; {}".format(label, _fmt(used), _fmt(raw_limit), note)
            output.append('<p>{}</p><div class="track" role="img" aria-label="{}"><span class="fill{}" style="width:{:.2f}%"></span></div>'.format(
                _text(summary), _text(summary), " over" if available and used > limit else "", percent))
        output.append('</section>')
    return "".join(output) or '<p>No MPPT inputs configured.</p>'


def _table(mapping):
    return '<table><tbody>' + "".join(
        '<tr><th scope="row">{}</th><td>{}</td></tr>'.format(_text(key), _text(_fmt(value)))
        for key, value in mapping.items()) + '</tbody></table>'


def html_report(result: DesignResult) -> str:
    """Return a self-contained, printable HTML document with accessible charts."""
    data = result.to_dict()
    checks = "".join('<tr>' + "".join('<td>{}</td>'.format(_status_badge(check.get(key)) if key == "status" else _text(_fmt(check.get(key))))
                                   for key in ("name", "status", "value", "limit", "explanation", "reference")) + '</tr>'
                     for check in data.get("checks", []))
    details = "".join('<section><h2>{}</h2>{}</section>'.format(title, _table(data.get(key, {})))
                      for title, key in (("Module", "module"), ("Inverter", "inverter"),
                                         ("Site", "site"), ("Array", "array"),
                                         ("Module / string metrics", "metrics"), ("Module count limits", "limits")))
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PV string design report</title><style>
:root{color-scheme:light dark;--bg:#fff;--fg:#18212f;--muted:#e5e7eb;--accent:#0369a1}
@media(prefers-color-scheme:dark){:root{--bg:#111827;--fg:#f3f4f6;--muted:#374151;--accent:#38bdf8}}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:1100px}
h1,h2,h3{line-height:1.2}h2{margin-top:2rem}table{border-collapse:collapse;width:100%;margin:1rem 0;overflow-wrap:anywhere}
th,td{border:1px solid var(--muted);padding:.45rem;text-align:left;vertical-align:top}th{font-weight:600}
.scroll{overflow-x:auto}svg{display:block;width:100%;height:auto;min-width:620px}svg text{fill:currentColor;font:12px system-ui,sans-serif}
.track{height:16px;background:var(--muted);border:1px solid currentColor}.fill{display:block;height:100%;background:var(--accent)}.over{background:#dc2626}
.mppt{break-inside:avoid}footer{border-top:2px solid var(--muted);margin-top:2rem;padding-top:1rem}
.badge{display:inline-block;padding:.1rem .45rem;border:1px solid currentColor;border-radius:.25rem;font-weight:700}.status-pass{background:#dcfce7;color:#14532d}.status-warn{background:#fef3c7;color:#78350f}.status-fail{background:#fee2e2;color:#7f1d1d}.status-unknown{background:var(--muted);color:var(--fg)}
@media print{:root{color-scheme:light;--bg:#fff;--fg:#000;--muted:#bbb;--accent:#0369a1}body{padding:0;max-width:none;font-size:10pt}.scroll{overflow:visible}svg{min-width:0}thead{display:table-header-group}tr{break-inside:avoid}h2,h3{break-after:avoid}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
</style></head><body><main><h1>PV string design report</h1>
<p><strong>Status: ''' + _status_badge(data.get("status", "")) + '''</strong> · Schema ''' + _text(data.get("schema_version", "")) + '''</p>
<p>''' + _text(data["module"].get("name", "")) + " · " + _text(data["inverter"].get("name", "")) + " · " + _text(data["site"].get("name", "")) + '''</p>
<h2>Voltage window</h2><p>Voltages below are per string. * marks the design. Up to 40 counts near the design are shown. Full limits appear below.</p>
<div class="scroll">''' + _voltage_chart(data) + '''</div>
<h2>Current headroom per MPPT</h2>''' + _current_bars(data) + '''
<h2>Design checks</h2><div class="scroll"><table><thead><tr><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Value</th><th scope="col">Limit</th><th scope="col">Explanation</th><th scope="col">Reference</th></tr></thead><tbody>''' + checks + '''</tbody></table></div>
<p>Raw voltage metrics are per module (V); current metrics are per string (A). Temperatures are °C and power is W. MPPT bars multiply string currents by parallel string counts.</p>
''' + details + '''</main><footer>''' + _text(_DISCLAIMER) + '</footer></body></html>'


def _md(value):
    return html.escape(_fmt(value), quote=False).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", "<br>").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")


def markdown_report(result: DesignResult) -> str:
    """Return a Markdown report, escaping input-derived markup."""
    data = result.to_dict()
    lines = ["# PV string design report", "", "Status: " + _md(data.get("status")), "", _DISCLAIMER, "",
             "Voltage metrics: per module (V); currents: per string (A); temperatures: °C; power: W.", ""]
    for key in ("module", "inverter", "site", "array", "metrics", "limits"):
        lines.extend(["## " + key.capitalize(), "", "| Field | Value |", "| --- | --- |"])
        lines.extend("| {} | {} |".format(_md(k), _md(v)) for k, v in data.get(key, {}).items())
        lines.append("")
    columns = ("name", "status", "value", "limit", "explanation", "reference")
    lines.extend(["## Checks", "", "| Check | Status | Value | Limit | Explanation | Reference |", "| --- | --- | --- | --- | --- | --- |"])
    lines.extend("| " + " | ".join(_md(check.get(k)) for k in columns) + " |" for check in data.get("checks", []))
    return "\n".join(lines) + "\n"


def json_report(result: DesignResult) -> str:
    """Serialize the versioned result without changing its numeric semantics."""
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
