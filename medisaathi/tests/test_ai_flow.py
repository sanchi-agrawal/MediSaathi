"""Streamlit AppTest checks for the 12D screen flow. Offline: mocked extractor,
tiny temporary sample image, no Gemini. Skipped when streamlit is not installed.

AppTest cannot drive st.file_uploader or edit st.data_editor, so these tests use
the sample-prescription button as the upload; upload replacement/removal and cell
edits are covered by tests/test_ai_flow.py against the same controller."""
import importlib.util
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

APP = Path(__file__).resolve().parent.parent / "app.py"
HAVE_STREAMLIT = importlib.util.find_spec("streamlit") is not None


@unittest.skipUnless(HAVE_STREAMLIT, "streamlit is not installed")
class AppFlow(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        import ai_flow as flow
        import ai_integration as module
        self.flow = flow
        folder = tempfile.mkdtemp()
        sample = Path(folder) / "sample.png"
        with BytesIO() as out:
            with Image.new("RGB", (4, 4), "white") as image:
                image.save(out, format="PNG")
            sample.write_bytes(out.getvalue())
        record = dict(raw_text="Fictional-A 1 tab BD x 3 days", name="Fictional-A", salt=None,
                      strength=None, form="tablet", frequency_pattern="BD", duration_days=3,
                      timing="morning and night", confidence=0.9, needs_review=True)
        self.extractor = MagicMock(side_effect=lambda data: [dict(record)])
        patches = [
            patch.object(flow, "adapter_factory",
                         lambda: module.AIIntegration(extractors={"medicines": self.extractor})),
            patch.object(flow, "SAMPLE_IMAGE_PATH", sample),
        ]
        # confirm_utils imports constants from the real schedule module, so patch the
        # engine function itself: it must never be called in this slice.
        self.legacy = MagicMock(side_effect=AssertionError("legacy schedule called"))
        patches.append(patch("schedule.build_schedule", self.legacy))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def app(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP), default_timeout=30)
        at.run()
        self.assertFalse(at.exception, at.exception)
        return at

    def ready(self, at):
        at.button(key="ai_sample").click().run()
        self.assertEqual(at.session_state["ai_status"], "ready")
        return at

    def test_no_extraction_without_explicit_analyze(self):
        at = self.ready(self.app())
        self.assertEqual(self.extractor.call_count, 0)
        at.button(key="ai_analyze").click().run()
        self.assertEqual(self.extractor.call_count, 1)
        self.assertEqual(at.session_state["ai_status"], "extracted")

    def test_confirm_then_explain_in_three_languages_without_re_extracting(self):
        at = self.ready(self.app())
        at.button(key="ai_analyze").click().run()
        self.assertTrue(at.button(key="ai_confirm").disabled)     # unknowns not yet acknowledged
        at.checkbox[0].check().run()
        at.button(key="ai_confirm").click().run()
        self.assertIsNotNone(at.session_state["ai_confirmed_view"])
        shown = {}
        for language in ("en", "hi", "hinglish"):
            at.radio(key="ai_language").set_value(language).run()
            self.assertFalse(at.exception, at.exception)
            shown[language] = [t.value for t in at.text]
        self.assertEqual(len({tuple(v) for v in shown.values()}), 3)
        self.assertEqual(self.extractor.call_count, 1)
        self.legacy.assert_not_called()

    def test_new_upload_after_confirmation_drops_confirmation(self):
        at = self.ready(self.app())
        at.button(key="ai_analyze").click().run()
        at.checkbox[0].check().run()
        at.button(key="ai_confirm").click().run()
        self.assertIsNotNone(at.session_state["ai_confirmed_view"])
        at.button(key="ai_sample").click().run()                  # a new analysis replaces the old one
        self.assertEqual(at.session_state["ai_status"], "ready")
        self.assertIsNone(at.session_state["ai_confirmed_view"])
        self.assertEqual(self.extractor.call_count, 1)

    def test_extraction_failure_shows_a_safe_message_and_retry(self):
        import reader
        self.extractor.side_effect = [reader.PrescriptionAPIError("secret-key-123")]
        at = self.ready(self.app())
        at.button(key="ai_analyze").click().run()
        self.assertEqual(at.session_state["ai_status"], "failed")
        self.assertTrue(any("could not complete" in e.value for e in at.error))
        self.assertNotIn("secret", " ".join(e.value for e in at.error))
        at.button(key="ai_retry")                                 # raises if the retry button is missing
        self.assertEqual(self.extractor.call_count, 1)


if __name__ == "__main__":
    unittest.main()
