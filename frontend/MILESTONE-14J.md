# Milestone 14J — licensed geometry replacement, visual review pending

## Reference investigation

Reference: https://sketchfab.com/3d-models/human-internal-organs-fe69d7b1ed6f46a3bd0b6933b796092e

The official public API at https://api.sketchfab.com/v3/models/fe69d7b1ed6f46a3bd0b6933b796092e returned creator **unlim3d**, license **Standard**, and **isDownloadable: false** on October 28, 2026. The model page itself returned HTTP 403 to the research tool. No reference meshes, textures, or viewer files were copied. A Standard license label is not evidence that MediSaathi has purchased or otherwise acquired a license.

## Obtained replacement

Exact GLB source: https://github.com/yamz8/human-body-simulator/blob/main/public/models/anatomy-organs.glb

Original creator: BodyParts3D / The Database Center for Life Science (DBCLS), Japan. GLB conversion and semantic grouping: yamz8/human-body-simulator contributors. Upstream source mirror: https://github.com/Kevin-Mattheus-Moerman/BodyParts3D. Dataset DOI: https://doi.org/10.18908/lsdba.nbdc00837-000.

License: **CC BY-SA 2.1 Japan**, commercial-compatible, with attribution, license linking and share-alike obligations for adapted model material. Verified against the upstream geometry license and the GLB distributor's README. The complete 319,764-byte published GLB was obtained from GitHub's public Contents API, decoded from its base64 response and retained without modification. No authentication or access restrictions were bypassed. It is an organ subset of BodyParts3D, not the entire anatomical dataset.

SHA-256: `fa0f8a32e6f1fdc8f8c469f81409289b0141cebe5d37e3e0048a134cf8bf6eb6`.

Bundled notices: `public/models/ATTRIBUTION.txt`, `public/models/LICENSE-BodyParts3D.txt`, `public/draco/LICENSE.txt`. The UI links to attribution. Draco uses Apache 2.0; Three.js uses MIT. Runtime colors, common framing transform, highlights and hidden incomplete brain parts are declared adaptations under the asset's share-alike license. Unrelated application code is not relicensed.

## Geometry and interaction

All procedural capsules, spheres and tubes were removed from the anatomy component. The GLB's source meshes keep their original relative placement and scale. A single common translation and uniform scale frame the organ assembly. Mesh names retain FMA IDs:

- Heart: FMA7274.
- Lungs: FMA7333, FMA7337, FMA7383, FMA7370, FMA7371 (lobes).
- Liver: FMA7197.
- Stomach: FMA7148.
- Kidneys: FMA7204, FMA7205.
- Intestines: FMA7206, FMA7207, FMA7208.

The source brain group only contains cerebellum/brainstem structures. Those meshes are hidden and brain selection is unavailable. No complete brain, vessels or outer body were fabricated. This presentation is an assembled internal-organ model, not a full-body atlas or a textured photorealistic substitute for the reference.

Hover gives a blue highlight; clicking locks the coral selection and bilingual educational card. Selection uses actual mesh raycasting. The accessible button list is populated only after supported geometry loads. Pointer rotation, captured touch drag, bounded angles, reset, reduced-motion behavior and offscreen/hidden-page pause remain. Under reduced motion explicit drag remains available without interpolation and automatic hover rotation is disabled. WebGL/asset failure shows the static fallback and does not expose unverified organ controls.

## Performance and verification

The GLB uses Draco compression, 16 source meshes and 143,202 triangles, with no textures. The decoder is self-hosted (192,420-byte WASM plus 58,456-byte wrapper); no CDN is needed. Anatomy and its GLB load lazily, DPR is capped at 1.5, there are no shadows or postprocessing passes, and frames stop once rotation settles. The anatomy JavaScript chunk is about 162 KB gzipped; Vite warns that its uncompressed size exceeds 500 KB. Actual GPU/frame-rate performance is unmeasured.

Automated result: **83 tests passed across 14 files**, production build passed. Tests cover successful asset loading, supported-organ controls, Hindi cards, keyboard activation, no slider, failure fallback, reduced-motion idle behavior, and prior landing language/persistence/navigation behavior. `node scripts/verify-anatomy.cjs` additionally decodes the actual shipped GLB using the shipped WASM decoder.

Browser inspection was attempted but the browser access host reported unavailable. Real rendered proportions, source-facing direction, silhouette, framing at desktop/tablet/mobile sizes, occlusion, touch feel and card overlap remain **unverified**. This milestone is pending human visual review; realism is not claimed complete from compilation or metadata alone. Please supply Chrome screenshots at approximately 1440, 768 and 375 CSS pixels, including an angled view and a selected organ.

## Files changed for 14J

- `src/components/Anatomy.tsx`, `src/components/Anatomy.test.tsx`, `src/components/AnatomyFallback.tsx`.
- `src/pages/Landing.test.tsx`, `src/lib/language.ts`, `src/anatomy.css`.
- `public/models/anatomy-organs.glb`, `public/models/ATTRIBUTION.txt`, `public/models/LICENSE-BodyParts3D.txt`.
- `public/draco/draco_wasm_wrapper.js`, `public/draco/draco_decoder.wasm`, `public/draco/LICENSE.txt`, `public/draco/README.md`.
- `scripts/verify-anatomy.cjs`, `MILESTONE-14J.md`.

No backend, scheduling, pricing, AI or diagnostic-guard edits. No Gemini requests. No commit or push. Existing uncommitted 14H changes remain.

## View locally

```powershell
cd C:\Users\ASHTAMI\MediSaathi-Frontend\frontend
npm.cmd run dev
```

Open http://localhost:5173/, then hard refresh Chrome to avoid viewing the previous development bundle.
