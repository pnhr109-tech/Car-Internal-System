# AI Dev Rules (Django + Bootstrap UI)

## Sources of truth
- docs/ui-style-guide.md
- static/ui/tokens.css
- static/ui/bootstrap-overrides.css

## Must follow
- Use Bootstrap layout/components (container, row, col, table, form-control, btn)
- Visual rules (colors/sizes/radius/hover) must follow tokens + overrides
- Do NOT introduce new colors/sizes unless requested
- Button hover must be visible (already enforced by overrides)
- Primary buttons: recommended 1 per screen, allow up to 2 (avoid more)

## When coding templates
- Prefer Bootstrap classes for layout
- For status labels use: ui-badge + ui-badge--(success|warning|danger|info)