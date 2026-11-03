# Milestone 14K — anatomical skin, materials and studio lighting

Latest state: [real cortical brain and more translucent shell update](MILESTONE-14K-BRAIN.md). That report supersedes the earlier partial-brain and shell-opacity values below. Visual acceptance remains open.

## Urgent correction — visual acceptance remains open

The actual imported skin mesh is present and decodes as `skin__FMA7163` (177,724 bytes, 94,966 triangles). The live Vite server returns HTTP 200 for it. The confirmed rendering defect was the custom alpha multiplier: face-on opacity was `0.17 * 0.12 = 0.0204`, falling to `0.10 * 0.12 = 0.012` during hover. This made the body surface nearly invisible. FrontSide also culled back-facing surfaces; whether that contributed in the user's browser remains unverified.

The correction removes that shader, uses stock DoubleSide MeshPhysicalMaterial with depth testing enabled and depth writes disabled, and removes forced render ordering. Surface opacity is now 0.24 before selection, 0.19 when selected, and 0.16 on hover, with no further shader multiplier. Both original geometry files and their shared alignment are unchanged. There is no replacement outline or procedural body. Double-sided transparency adds a second shell surface pass during active frames; idle/offscreen pause and the pixel budget remain.

The card now occupies a reserved grid column beside the canvas rather than an absolute overlay. Width limits and text wrapping constrain it to that column; tablet/mobile place it below the canvas. Vite serves the corrected material, and the old alpha multiplication is absent from the served module.

Validation: **92 tests pass across 15 files; production build passes**. Added regressions verify two-sided skin, depth settings, removal of the alpha-erasing shader and a minimum 0.16 selection/hover opacity. The live HTTP and actual WASM decoding checks also pass.

**Not marked complete:** recognizable rendered skin and visible organ containment, real browser picking, card clearance, perceived rotation smoothness and live bilingual layout remain visually unverified. Unit/component tests cover interaction and language behavior but do not establish these visual criteria. Chrome inspection was attempted again and rejected with “Computer Use was not approved to use Google Chrome.” Please provide an updated screenshot after a hard refresh for acceptance review.

Files changed for this correction: `src/components/Anatomy.tsx`, `src/components/anatomyAppearance.ts`, `src/components/Anatomy.test.tsx`, `src/components/anatomyAppearance.test.ts`, `src/anatomy.css`, `public/models/ATTRIBUTION.txt`, and `MILESTONE-14K.md`. No model binary changes, new dependencies, protected module changes, Gemini calls, commits or pushes.

## Assets and permission

Both models are original BodyParts3D 3.0 geometry by **The Database Center for Life Science (DBCLS), Japan**, converted to Draco GLB and given semantic mesh names by the `yamz8/human-body-simulator` contributors.

- Existing organs: https://github.com/yamz8/human-body-simulator/blob/main/public/models/anatomy-organs.glb
- Added full-body skin: https://github.com/yamz8/human-body-simulator/blob/main/public/models/anatomy-skin.glb
- Distributor's license and coordinate-frame documentation: https://github.com/yamz8/human-body-simulator#bodyparts3d-skin-and-organ-assets
- Upstream geometry mirror: https://github.com/Kevin-Mattheus-Moerman/BodyParts3D
- Original license statement: https://lifesciencedb.jp/bp3d/info_en/license/index.html
- Dataset DOI: https://doi.org/10.18908/lsdba.nbdc00837-000

License: **CC BY-SA 2.1 Japan**. Commercial web reuse and adaptations are permitted with attribution, license linking and share-alike obligations for adapted model material. The complete skin GLB was obtained from the repository's public GitHub Contents API; no model viewer files or access restrictions were bypassed. Neither original GLB has been modified. The runtime presentation changes are identified as adaptations in `public/models/ATTRIBUTION.txt` and offered under the asset's share-alike terms. The UI links to that notice. The upstream license statement is bundled in `public/models/LICENSE-BodyParts3D.txt`.

Skin SHA-256: `6d5a0c0ff45f42d91193d36c459fe44bcd89d93c96507e7246425ca73c404a4c`.

## Model inspection and alignment

The original organ GLB contains 16 named meshes. Six organ groups are available: heart (FMA7274), lung lobes (FMA7333, FMA7337, FMA7383, FMA7370, FMA7371), liver (FMA7197), stomach (FMA7148), paired kidneys (FMA7204/FMA7205), and intestines (FMA7206/FMA7207/FMA7208). The partial cerebellum/brainstem group stays hidden and is not presented as a complete selectable brain. No major blood vessel layer is present or invented.

The skin GLB contains the actual named anatomical mesh `skin__FMA7163`, not a capsule-based substitute. Its decoded bounds are approximately x [-1.339, 1.334], y [-3.535, 3.183], z [-0.187, 0.971]. The organ bounds lie within those bounds. The distributor explicitly documents that skin and organs retain their shared source frame. Both roots are children of one group centered from the decoded geometry. The lower framing edge is inferred from the lowest abdominal organ, while the head and shoulders are measured from skin vertices above that edge. No per-organ rescaling or offsets are applied. The original proportions and inter-organ placement are preserved.

The camera deliberately frames the **upper body, head through pelvis**, instead of shrinking the organs to fit the entire body. The full skin geometry remains intact; legs extend below the viewport. Camera distance is calculated from the measured region and the current damped pose at each viewport aspect ratio. It fits the rotated bounds with a margin; no fixed camera distance or body stretch is used. Automated bounds checks are not surface-level medical validation. Source mesh holes, transparency sorting artifacts or fine anatomical inaccuracies cannot be ruled out without rendered inspection.

## Integrated immersive hero requirement

The desktop hero now uses a 42% copy / 58% anatomy grid within a wider, responsive 1480-pixel maximum composition. The anatomy visual is 740?1000 pixels tall according to viewport height, with an open canvas and cyan atmosphere extending into the navy background. There is no enclosing model card. The model starts near the navigation area; the exact rendered body-height ratio and subjective prominence remain pending visual review.

Tablets up to 900 pixels stack the hero to preserve model detail. Mobile uses a dedicated 560?740 pixel canvas, and tablet uses 640?820 pixels. Organ cards and wrapped keyboard/touch selection controls remain below the canvas at these sizes. On desktop the compact information card is placed low and to the right, away from the central chest/head. Text, navigation and the existing landing sections are retained.

The camera now derives its common center and head-to-pelvis framing region from decoded organ and skin vertices, rather than fixed offsets. It uses a slight three-quarter resting angle and adjusts perspective distance with the same damped rotation to keep the rotated region inside the viewport. Geometry and source proportions remain untouched. Tests project all fitted bounding corners at desktop, tablet and narrow mobile aspects, including drag limits, and verify that changing source dimensions changes the camera distance proportionally.

## Appearance

- Organs now use MeshPhysicalMaterial: deep coral heart, muted pink lungs, reddish-brown liver, soft pink stomach, dark rose kidneys and muted pink intestines. Metalness is zero, roughness is moderate and clearcoat is restrained. Original assets contain no texture/normal/roughness maps; none are claimed or fabricated.
- The real skin mesh has stock double-sided cyan PBR material, depth testing enabled and depth writes disabled. No custom alpha shader, geometry inflation or transmission/refraction pass is used.
- Selected organs retain their natural base color with restrained coral emissive emphasis; other organs are slightly dimmed. Hover adds a cool highlight and further lowers shell opacity. The skin's face-on opacity remains low enough to reveal the selected organs. Posterior kidneys can still be occluded by other organs from the front; rotation is available rather than relocating them.
- Neutral key light, cool cyan rim light, gentle fill and low hemisphere light replace the earlier strong blue wash. A generated 128-pixel studio PMREM supplies modest reflections, without an HDRI download. Output is explicitly sRGB with ACES filmic tone mapping and exposure 1.05. No bloom, shadow maps or postprocessing passes.
- Desktop information cards occupy a reserved grid column outside the canvas. On tablet and mobile the card moves below the canvas. The existing hero layout and landing content remain in place.

## Interaction and resilience

Mouse position controls damped yaw and small pitch. Explicit drag is constrained to yaw [-1.05, 0.95] and pitch [-0.16, 0.2] radians. Pointer exit and Reset View restore the same resting pose. Touch drag uses pointer capture, accepts one pointer at a time and restores the resting pose on release. Touch-action is disabled only within the model viewport. Mouse drag can retain its orientation until pointer exit. There is no slider.

Raycasting only targets actual organ meshes; skin does not intercept selections. Hover and click are distinct. The English/Hindi cards and keyboard organ buttons are retained. Reduced motion disables automatic hover rotation and damping, while deliberate touch/mouse drag and selection remain usable. Rendering is on demand and stops after motion settles, offscreen, or when the document is hidden.

The anatomy component remains lazy-loaded, with local asynchronous GLB loads. The camera performs eight bounds-corner projections during active frames; it does not scan the full geometry per frame. Existing loading/WebGL fallback remains. If just the skin fails, the original organs remain and a translated notice explicitly reports the missing outline; no replacement shell is fabricated. Resources and listeners are released on unmount.

## Performance and verification

- Added asset: **177,724 bytes / 94,966 triangles**, no textures. Combined source geometry: 238,168 triangles (some incomplete brain meshes are hidden). The decoder is shared between both model loads and disposed after both settle.
- DPR stays capped at 1.5, with an additional 1.6-million-pixel rendering budget for the larger viewport. The environment is generated once at 128-pixel resolution. No new package dependencies or external runtime downloads.
- `node scripts/verify-anatomy.cjs`: both actual GLBs decode through the shipped WASM decoder; finite positions, expected mesh names, untransformed source frames and encompassing skin bounds verified.
- Frontend tests: **92 passed across 15 files**. Coverage includes common skin/organ frame, PBR shell, camera fitting at desktop/tablet/mobile ratios, selection dimming, successful and failed shell loads, language switching/persistence, keyboard selection, pointer rotation/exit, touch limits, reduced motion, offscreen pause, shell alpha regression and existing frontend flows.
- Production build: passed. Vite retains an anatomy chunk-size warning; the scene is lazy-loaded. GPU frame rate and shader appearance were not measured.

**Visual inspection is pending.** Browser inventory reported the browser access host unavailable. The native Chrome inspection attempt was also rejected with “Computer Use was not approved to use Google Chrome.” No screenshot has been inspected for this milestone, and compilation does not establish realism. Please provide Chrome screenshots at desktop and mobile widths, including a selected organ and an angled view, so skin alignment, source-mesh quality, surface transparency, framing and card placement can be reviewed.

## Changed files for 14K

- `src/components/Anatomy.tsx`
- `src/components/anatomyAppearance.ts` (new)
- `src/components/Anatomy.test.tsx`
- `src/components/anatomyAppearance.test.ts` (new)
- `src/pages/Landing.test.tsx`
- `src/lib/language.ts`
- `src/anatomy.css`
- `public/models/anatomy-skin.glb` (new)
- `public/models/ATTRIBUTION.txt`
- `scripts/verify-anatomy.cjs`
- `MILESTONE-14K.md` (new)

Earlier uncommitted 14H/14J files remain. No FastAPI, Gemini, scheduling, pricing, AI contract or diagnostic-guard changes. No Gemini requests, commits or pushes.

## View locally

```powershell
cd C:\Users\ASHTAMI\MediSaathi-Frontend\frontend
npm.cmd run dev
```

Open http://localhost:5173/ and hard refresh Chrome. The landing model does not require the backend.
