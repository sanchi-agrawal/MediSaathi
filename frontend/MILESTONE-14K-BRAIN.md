# Milestone 14K — real cortex and more translucent shell

Implementation and automated verification are finished. **Visual acceptance remains open**; no claim of browser-verified realism is made.

## Exact assets and rights

- New cortical geometry: 37 original BodyParts3D **3.0 / 20110915** STL components from https://github.com/Kevin-Mattheus-Moerman/BodyParts3D/tree/main/assets/BodyParts3D_data/stl.
- Original creator: **BodyParts3D / The Database Center for Life Science (DBCLS), Japan**.
- License: **CC BY-SA 2.1 Japan**, commercial-compatible with attribution, license linking and share-alike for derived model material. Source statement: https://github.com/Kevin-Mattheus-Moerman/BodyParts3D/blob/main/LICENSE_content and https://lifesciencedb.jp/bp3d/info_en/license/index.html.
- Each source URL, anatomical name, pinned Git blob hash and byte size is recorded in `public/models/brain-sources.json`. Downloads used GitHub's public blob API; all source hashes were verified. No restricted viewer content, commercial model or noncommercial asset was copied.
- Reused organ/cerebellum/pons/medulla GLB: https://github.com/yamz8/human-body-simulator/blob/main/public/models/anatomy-organs.glb.
- Reused real skin GLB: https://github.com/yamz8/human-body-simulator/blob/main/public/models/anatomy-skin.glb.
- Both existing GLBs are derived from the same BodyParts3D 3.0 dataset under the same geometry license. Their bytes remain unchanged. The UI links to `public/models/ATTRIBUTION.txt`; original license text remains bundled.

The new adapted `anatomy-cerebrum.glb` is also distributed under CC BY-SA 2.1 Japan. Changes: coordinate registration, vertex welding, smoothed normals, bounded simplification, merged draw call and Draco compression. It contains actual bilateral gyri, parietal/occipital regions, insula and medial cortical parts. No spheres, procedural lumps, copied textures or invented folds were used. The existing cerebellum and brainstem are reused rather than duplicated. Deep brain anatomy is not a complete atlas.

## Alignment and materials

The raw STL meshes use a different axis/unit convention. One common rigid axis conversion, uniform scale and translation were recovered against three corresponding anatomical source/target structures: stomach FMA7148, kidney FMA7204 and pons FMA67943. No individual brain part is independently fitted to a guessed head box.

Recovered transform from original STL coordinates:

```text
x' =  0.004056572616984543 * x - 0.000010678159700474418
y' =  0.004056572616984543 * z - 3.4771711514440717
z' = -0.004056572616984543 * y + 0.00026827547102979227
```

The transform preserves orientation (positive determinant) and proportions. Maximum registration-reference bounding-coordinate residual: **0.0006374 model units**, approximately **0.157 mm** in original source units. This residual measures correspondence of source/target bounds, not a clinical accuracy certification.

Decoded cerebral bounds: x [-0.2736, 0.2682], y [2.6983, 3.1474], z [0.0183, 0.7085], within the matching skin's bounds and cranial region. The matrix is baked into the new GLB. Skin, cortex and original organs share one runtime parent and the same geometry-measured framing translation. They rotate together. No skull mesh exists in the scene, so there is no opaque skull concealing the brain.

Brain material is soft rose PBR with roughness 0.62 and restrained reflections. Both the new cortex and existing cerebellum/brainstem participate in Brain raycasting and selection highlighting. Brain is enabled only after the verified cortex loads; if it fails, the partial original brain stays hidden and a translated notice reports the missing cortex while other organ controls continue working.

The stock DoubleSide cyan shell material is now #45c8ff, roughness 0.2, metalness 0, depthWrite false, depthTest true, with opacity:

- Resting/unselected: 0.14.
- Organ selected: 0.11.
- Brain selected: 0.10.
- Hovering a selectable organ: 0.09.

There is no custom alpha multiplier and no forced render-order overlay. The existing cyan rim light defines the real skin surface. These are starting values within the requested range; their visual balance is **not yet verified**.

## Preserved layout and interaction

The desktop hero retains 58% width for anatomy; tablet/mobile keep tall dedicated canvases. The camera measures skin and organ geometry, including the new cortex, and fits the damped pose without stretching the model. The card remains in a reserved column outside the canvas on desktop and below it on narrower screens. Pointer-driven rotation, captured touch dragging, reset, no-slider controls, reduced motion, offscreen/document-hidden pause, English/Hindi cards and keyboard buttons are preserved.

## Performance and verification

- Original cortical sources: 504,122 triangles. Optimized output: **277,680 triangles**, **896,848 bytes**, merged into **one additional mesh/draw call**, no textures. The three already-loaded brainstem/cerebellum meshes also become visible. Simplification stops at its error bound to retain the cortical folds.
- New GLB SHA-256: `56b169c7774af3abb31da1b68ef766ddef0ba7f512d7c46989eaa48d5c623dad`.
- Existing anatomy plus cortex: 515,848 source triangles; transparent skin has normal back/front passes. Actual laptop frame rate is unmeasured. DPR 1.5 and 1.6-million-pixel limits, no shadows/bloom and idle/offscreen rendering pauses remain.
- GLB is loaded lazily with the shared local Draco decoder. The source conversion tools are development dependencies and are not imported by the React application.
- Actual shipped decoder verification passes for all three GLBs, including cortical hash, finite coordinates, bilateral extent, cranial-region bounds and skin bounds.
- Frontend: **94 tests passed across 15 files**. Tests include Brain hover/click, reuse of original brain pieces, shared source frame, Hindi Brain card, keyboard controls, missing-cortex behavior, reduced-motion/touch/pointer behavior, shell alpha regression and previous language/persistence/navigation behavior.
- Production build passed. The lazy anatomy JS chunk remains about 165 KB gzipped, with Vite's existing >500 KB uncompressed chunk warning. The new cortical GLB is a separate asynchronous asset and the local dev server returns HTTP 200 for it.

## Unmet visual acceptance

Browser inventory again reported **the browser access host is unavailable**. Native Chrome access had previously been rejected and has not been granted. No screenshot of the new cortex or opacity settings was inspected.

Still pending: visible recognizable shell; recognizable folds/hemispheres through the head; surface-level organ containment/alignment; final transparency/lighting balance; live hover/picking and rotation feel; English/Hindi card clearance at desktop and mobile; actual GPU performance. Tests and numerical bounds do not establish those visual criteria. Please provide refreshed Chrome screenshots with Brain selected, in desktop and mobile layouts, plus an angled view. This upgrade is not marked visually accepted.

## Changed files in this update

- `package.json`, `package-lock.json` — development-only conversion/compression tools.
- `.gitignore` — excludes the downloaded source cache from version control.
- `src/components/Anatomy.tsx`, `src/components/anatomyAppearance.ts`.
- `src/components/Anatomy.test.tsx`, `src/components/anatomyAppearance.test.ts`.
- `src/lib/language.ts`.
- `public/models/anatomy-cerebrum.glb`, `public/models/brain-sources.json`, `public/models/ATTRIBUTION.txt`.
- `scripts/fetch-brain-sources.py`, `scripts/build-brain.mjs`, `scripts/verify-anatomy.cjs`.
- `MILESTONE-14K.md`, `MILESTONE-14K-BRAIN.md`.

No backend, scheduling, pricing, AI or diagnostic-guard edits; no Gemini requests, commits or pushes.

## View and reproduce

```powershell
cd C:\Users\ASHTAMI\MediSaathi-Frontend\frontend
npm.cmd run dev
```

Open http://localhost:5173/ and hard-refresh. Select Brain or मस्तिष्क.

To rebuild the asset from the exact licensed sources (requires network):

```powershell
python scripts/fetch-brain-sources.py
node scripts/build-brain.mjs
node scripts/verify-anatomy.cjs
```

Source downloads are cached only in `.anatomy-work`; the complete source manifest and conversion provenance remain with the distributed GLB.
