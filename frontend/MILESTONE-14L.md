# Milestone 14L — anatomy layout and typography polish

The confirmed anatomical assets, cortical geometry, material settings, organ mappings and rotation handlers are preserved. This update changes layout, typography, controls markup, translated help text and camera framing only. No assets were regenerated or replaced.

## Presentation changes

- The anatomy stage targets a **72/28 model/card grid**. The information panel has a **260 px readability floor**; this can increase its percentage on constrained desktop columns. The page's left hero copy remains separate from the model's own viewport. Below 1200 px the outer hero stacks to give anatomy enough width; below 850 px the card moves below the model. No card overlays the canvas.
- The card is centered vertically alongside the model's chest/upper-abdomen, with no percentage bottom margin. It has 26 px desktop padding, a translucent navy background, a thin blue border, 20 px corners and a restrained shadow. Width is constrained to its grid column; text can wrap rather than overflow.
- Card typography: 13 px uppercase eyebrow; 32 px semibold organ heading; 16 px description with line-height 1.6. On smaller screens the title is 30 px and card padding is 24 px. Hindi retains Noto Sans Devanagari, normal letter spacing and extra line-height for matras. Text contrast is increased.
- A dedicated control region sits **below both model and card**, with a subtle top divider, centered wrapping rows, 15 px labels, 46 px minimum button height and 10 px gaps. Selected organs have coral borders/background; hover and keyboard focus have distinct feedback.
- Rotation instructions now read “Move your pointer to rotate. Drag to explore.” with a decorative pointer icon. Reset View has a rotate icon. Both remain translated, at readable 14-15 px sizes. They align beside each other where there is room and stack on mobile. No slider was added.
- The scene eyebrow, status, education caption and credit are enlarged; anatomy labels no longer use 8-11 px typography. The model remains unboxed with the existing cyan/navy atmosphere.

## Camera and alignment

The camera continues to fit the actual decoded anatomy bounds and current pose. The model is centered **inside its dedicated canvas**, without including the card width in its camera aspect ratio.

Inspection found that the earlier abdominal crop excluded some lateral hand vertices: the source hands extend to approximately y=-0.83, below the earlier crop. The framing helper now includes the actual lateral arms/hands of the known standing source pose while excluding the feet. The measured upper-body bounds are approximately:

```text
min: [-1.33892, -0.85471, -0.18732]
max: [ 1.33378,  3.18296,  0.91776]
```

This adjusts the common framing center and camera distance; it does not edit or stretch vertices, independently reposition organs, alter shell opacity, or change mouse/touch rotation parameters. The head, hands and organs are numerically inside the fitted view at resting and drag-limit poses.

## Verification

- **96 frontend tests passed across 15 files.** Existing language/persistence, Brain/organ selection, pointer/touch rotation, reduced-motion and fallback coverage passes. New tests cover the source hand crop and translated accessible control region/instructions/reset.
- `npm.cmd run check`: passed.
- `npm.cmd run build`: passed. The existing lazy anatomy chunk-size warning remains; no new dependencies, geometry, textures or rendering passes were added.
- `node scripts/verify-anatomy.cjs`: all three actual GLBs decode and retain the recorded original SHA-256 hashes. Their assets and proportions are unchanged.
- `node scripts/verify-anatomy-framing.mjs`: 755,019 actual-vertex projections per layout case pass, covering the resting pose and both drag limits. This is a numerical geometry check, **not a browser CSS-box measurement**.

| Page-width case | Assumed canvas used for projection checks | Layout intent |
| --- | --- | --- |
| 1440 px | 482 × 640 px | Outer hero columns; card beside model |
| 1024 px | 676 × 680 px | Outer hero stacked; card beside model |
| 768 px | 704 × 620 px | Model, card, controls stacked |
| 390 px | 358 × 560 px | Tall touch viewport and wrapped controls |

**Browser visual verification is pending.** The current browser inventory reports that the browser access host is unavailable, and native Chrome access has not been granted. Actual rendered DOM rectangles, typography at those four widths in English/Hindi, card clearance, control wrapping and the subjective model/card balance were not visually inspected. These results are not claimed from compilation or jsdom. Please provide updated screenshots at the requested widths for visual review, including Hindi.

## Exact files changed in 14L

- `src/anatomy.css`
- `src/components/Anatomy.tsx` — card/control markup and decorative icons only; rotation/load/selection logic unchanged.
- `src/components/anatomyAppearance.ts` — camera-framing measurement only; material functions unchanged.
- `src/components/Anatomy.test.tsx`
- `src/components/anatomyAppearance.test.ts`
- `src/lib/language.ts`
- `scripts/verify-anatomy-framing.mjs` (new)
- `MILESTONE-14L.md` (new)

No FastAPI, OCR, AI, pricing, scheduling, diagnostic-guard or navigation changes. No Gemini requests, commits or pushes.

## View locally

```powershell
cd C:\Users\ASHTAMI\MediSaathi-Frontend\frontend
npm.cmd run dev
```

Open http://localhost:5173/ and refresh. The anatomy presentation does not require the backend.
