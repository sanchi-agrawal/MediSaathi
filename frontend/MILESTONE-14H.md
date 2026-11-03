# Milestone 14H

Run locally from PowerShell:

```powershell
cd C:\Users\ASHTAMI\MediSaathi-Frontend\frontend
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173/. The backend is unnecessary for landing-page exploration. Existing API routes continue to proxy to http://127.0.0.1:8000. No AI calls were made for this work.

The English/Hindi switch uses `medisaathi.interface-language` in localStorage with an in-memory fallback if storage is unavailable. The shared hook can be reused by other pages; their main content has not been translated. Shared brand text follows the selected language. Prescription explanation language is independent.

## Anatomy and licenses

This implementation uses original procedural Three.js geometry, not an imported medical model. Brain folds, paired lungs, heart, liver, stomach, posterior kidneys, intestinal loops and simplified major vessels are approximate educational geometry. Mesh raycasting selects the actual organ geometry; there are no decorative hotspots. This is a simplified fallback, not the requested realistic anatomical atlas. It needs replacement with a curated, medically reviewed asset to meet that visual standard.

Investigated source: https://github.com/nqwrc/3d-anatomy/tree/master/public/models. Its actual `License.txt`, retrieved through GitHub's contents API, requires BodyParts3D / DBCLS attribution (CC BY-SA 2.1 Japan) and Z-Anatomy attribution (CC BY-SA 4.0), and also lists third-party kidney CC BY-NC 4.0 and inner-ear CC BY-NC-SA 4.0 content. No meshes from that mixed-license collection were incorporated. Redistribution would require confirming provenance per mesh and preserving applicable notices and share-alike terms.

Three.js: MIT. Noto Sans Devanagari: SIL Open Font License 1.1, bundled locally via @fontsource/noto-sans-devanagari; license in that package's LICENSE file. No external font service or asset request is required at runtime.

## Verification

Automated tests cover language changes, preference across remounts, WebGL failure, translated organ selection, absence of sliders and unchanged landing link destinations. Existing prescription and scheduling suites remain intact. Pointer hover and drag use bounded Three.js group rotations and raycasting; touch uses pointer capture with touch-action:none only on the model. Reduced motion disables automatic hover motion. Rendering stops when settled/offscreen/hidden; resources are disposed on unmount. The anatomy chunk is lazy-loaded.

Manual verification still required: real GPU appearance and picking, touch-device drag, Hindi typography at 375/768/1440 px, and live login/signup/dashboard/analysis navigation with backend running. Unit tests do not establish these browser-level results. The existing signup route is preserved and remains reachable through authentication navigation.

Only frontend files were changed. No commits, merges or pushes were made.
