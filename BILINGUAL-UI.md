# English / हिंदी interface coverage

## Root cause

The existing `medisaathi.interface-language` store, refresh restoration and
cross-tab storage listener already worked. Most workflow pages rendered English
JSX directly and did not subscribe to this store. Their headings, accessibility
labels and asynchronous state messages bypassed the dictionary. The prescription
explanation selector also initially used English independently of the interface.

## Changes

`frontend/src/lib/language.ts` now exposes shared render-time translation,
parameter substitution, safe category-based error presentation, known warning
code translations and narrowly matched existing refill-message templates.
`workflowHindi.ts` extends the existing English-keyed catalogue. There are more
than 750 reviewed interface entries across the combined catalogues. New UI copy
must use the shared hook/catalogue rather than adding English JSX or a second
language store.

Pages and reusable components now subscribe to the same language preference.
Language switching updates visible headings, descriptions, labels, actions,
placeholders, warnings, loading states, search results and accessibility text.
Dashboard search also searches translated labels. English and Hindi route titles
update with the selected language. The existing localStorage entry stores only
the non-sensitive language preference; account/session storage is unchanged.

Coverage includes the landing page and anatomy controls, local and existing
alternative auth screens, profile/navigation, dashboard, prescription upload and
ten-field review, independent instruction/investigation review, schedules,
reminder previews, catalogue matching, pricing restrictions, current records,
expiry scanning, settings, inactive future account-history UI and the 404 page.
Hindi uses the already installed Noto Sans Devanagari font. Scoped button/badge
wrapping avoids forcing longer Hindi phrases onto a single line.

The prescription explanation selection starts in the interface language and
follows subsequent interface changes. If medicines are already confirmed,
switching interface language uses the existing confirmed explanation endpoint;
it does not upload an image or invoke extraction. The explicit English/Hindi/
Hinglish explanation buttons remain available. Their selected output language
can intentionally differ from the surrounding interface. Old-language results
remain hidden until the correctly selected payload arrives. Unconfirmed records
cannot request an explanation.

Known backend error categories have actionable Hindi messages. Unknown technical
failures get a safe Hindi fallback plus a validated diagnostic code, without
showing an unknown provider body. Known uncertainty/price-availability codes are
translated at display time. Unknown source uncertainty remains original evidence
or a clearly identified diagnostic code; it is never turned into medical advice.

## Preserved medical and security boundaries

- Raw OCR/source lines, medicine and salt names, strengths, quantities, dates,
  abbreviations, units, catalogue names/IDs and user names are not blindly
  translated. Edited and original records remain separate.
- Standard form/unit dropdown labels may be localized, but explicit option
  `value` attributes retain their original API enums such as `tablet` and `mL`.
- Numbers, nulls, review flags, analysis IDs/revisions and confirmation scopes do
  not change when language changes. A translated label is never saved as medical
  data. Unknown information is not filled in.
- Structured clinical explanations come from the existing Python explanation
  contract. The browser does not fabricate a Hindi diagnosis, indication, dose,
  ingredient, side effect or schedule.
- Existing server/session expiry, separate review/confirmation, invalidation,
  scheduling approval, price restrictions and disabled notification behavior are
  unchanged. No authentication architecture or backend file changed in this task.
- The old prescription/strip notice claiming authentication was disconnected
  was replaced by the accurate temporary-prescription-storage disclosure.

Intentional English includes original extracted text and free-text source
uncertainty, proper names, medical abbreviations/measurements, file names, IDs,
licensing attribution, original historical JSON/schema data in the inactive
archive screen, and language choices. Explicitly chosen English/Hinglish clinical
explanations retain that chosen language. Unknown future clinical wording is kept
as source text rather than guessed. These are not missing UI translation keys.

## Verification and manual check

Final results: **157 frontend tests passed across 23 files**; TypeScript checks
and the Vite production build passed; `git diff --check` passed. The combined
catalogue has **772 entries**, with no missing literal UI keys or duplicate
workflow entries in the source audit. Vite still reports large JavaScript chunks
(main and anatomy); this does not prevent the build. The running Vite server
returned HTTP 200 for the new catalogue module. No provider requests were made.

Offline frontend tests cover English rendering, all Hindi prescription steps,
shared switching without reload, route/remount preference persistence, fresh
module restoration from storage, auth/dashboard Hindi, known/unknown errors,
unchanged source medicines and values, original dropdown API values, independent
instruction/investigation confirmations, schedule approval prerequisites, and
translated pricing restrictions. Source-level regression checks reject missing
literal translation keys, hardcoded English JSX, and literal untranslated
descriptions/placeholders/accessibility labels. Existing clinical and auth tests
remain part of the full frontend suite. No external provider request is needed.

Manual browser follow-up (not performed during this task): open the existing
localhost:5177 app, sign in, switch हिंदी, navigate Analysis → Medicines → Schedule
→ Expiry → Pricing, refresh and reopen a review panel. Check the Hindi labels,
long-button wrapping, unchanged original medical text and English switch-back.
Use only the registered fictional fixtures; do not make a live OCR request just
to verify translations. No browser/screenshot verification is claimed.

## Exact source files changed for this translation task

All paths below are relative to `frontend/src/`:

- `App.tsx`, `main.tsx`, `bilingual.css` (new)
- `lib/language.ts`, `lib/workflowHindi.ts` (new), `lib/translationCoverage.test.ts` (new)
- `components/AccountAccess.tsx`, `components/Anatomy.tsx`, `components/AuthSplitLayout.tsx`
- `components/DashboardLayout.tsx`, `components/ImageUploader.tsx`, `components/LanguageToggle.tsx`
- `components/LocalAccounts.tsx`, `components/MedicineMatching.tsx`, `components/OfflineDemoNotice.tsx`
- `components/PrescriptionExplanation.tsx`, `components/ReminderPreview.tsx`, `components/SectionReview.tsx`
- `components/SessionAccess.tsx`, `components/ui.tsx`
- `pages/CurrentWorkspace.tsx`, `pages/DemoSignIn.tsx`, `pages/ExpiryScanner.tsx`
- `pages/Landing.tsx`, `pages/Landing.test.tsx`, `pages/MyPrescriptions.tsx`, `pages/Overview.tsx`
- `pages/PrescriptionFlow.tsx`, `pages/Pricing.tsx`, `pages/Schedule.tsx`, `pages/Workspace.tsx`
- `pages/BilingualWorkflow.test.tsx` (new)

Also added this root `BILINGUAL-UI.md`. Temporary audit/edit helpers are ignored
under `api/.venv/`. Existing uncommitted local-account work was preserved. No
packages, backend code, runtime guards, medical source assets or teammate worktrees
were changed. No changes were staged, committed or pushed.
