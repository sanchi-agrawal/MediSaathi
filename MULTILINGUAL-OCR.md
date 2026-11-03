# English, Hindi and mixed-script prescriptions

The existing Gemini extractors now request literal English/Devanagari/mixed-script source preservation independently of the interface language. Medicine records retain the original ten fields. Dosage instructions and investigations remain separate. Unknowns remain null; Hindi-derived medicine records require review. Original source text is not translated. Script metadata identifies Latin, Devanagari or mixed evidence after extraction; Devanagari is not proof of Hindi language.

Conservative checks recognize explicit digit-based Hindi day counts and ambiguity indicators, preserve raw quantities/units and Hindi meal/time expressions, and reject unsupported normalized claims. Devanagari digit readings appear separately as review aids, without altering source text or medicine names. All existing confirmation gates remain. Hindi scheduling inputs unsupported by the current safety gate remain blocked; no automatic slot translation or medicine–instruction association was added.

## What has and has not been evaluated

Offline tests use mocked SDK responses and exact-hash static fixtures. They verify contracts, Unicode preservation, ambiguity handling, independent review and provider isolation; they do **not** establish OCR accuracy. Printed Hindi recognition remains unbenchmarked; handwriting is experimental.

`api/evaluation/fixtures/manifest.json` registers three synthetic printed images (English, Hindi, mixed) and one explicitly labeled typeset handwriting-like surrogate. There are no genuine human-handwritten samples and no patient data. No Gemini requests were made. Real printed and handwritten accuracy are both unmeasured, reported separately with unavailable metrics rather than invented percentages.

Regenerate synthetic images on Windows with installed Nirmala UI native shaping (no font binary redistributed):

```powershell
python -m api.evaluation.prepare_manifest
powershell -File api/evaluation/generate_fixtures.ps1
python -m api.evaluation.evaluate
```

The evaluator has no provider calls. Optional `--predictions <file>` compares externally obtained records with synthetic reference fields, reports unsupported claims and raw-text character error rate, and labels supplied provenance unverified. A perfect mocked prediction is a metric test, not a real recognition result. Obtain separately authorized controlled real predictions before claiming language accuracy; genuine handwriting needs its own consented/synthetic human-written evaluation set.

The prescription page displays the server's extraction mode. Offline mode uses registered fixture bytes and clearly labels static simulation, never live OCR. Real mode continues using the existing server-only Gemini configuration/model, image validation and retry policy. No new OCR engine, model switch, provider retry, clinical contract change or diagnostic guard reset was introduced.
