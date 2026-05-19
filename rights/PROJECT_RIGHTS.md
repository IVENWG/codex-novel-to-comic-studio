# Project Rights Gate

Mode: private_experiment

Status: template_requires_user_confirmation

Before adapting any novel, choose the correct project mode in `config/user-preferences.json` and replace this file with the actual rights basis for the run.

Supported modes:

- `private_experiment`: local workflow testing only.
- `licensed_commercial`: the user has provided a publication rights basis.
- `public_domain`: the source is public-domain or otherwise cleared for the intended use.

Rules:

- Do not provide DRM bypass instructions.
- Do not publish, distribute, or package generated outputs unless the source rights support that use.
- Keep generated outputs traceable to source spans or mark them as `adaptation_added`.
- Treat user-uploaded books, parsed chapters, reference cards, finished pages, PDFs, and CBZ files as rights-sensitive by default.
