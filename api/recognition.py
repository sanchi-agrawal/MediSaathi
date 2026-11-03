"""Mode provenance and script observations, separate from strict medical records."""
from .dependencies import reader  # Establish the existing legacy module path.
from prescription_language import script_observation,numeric_previews

def records_metadata(records):
    return {'script_observation':script_observation([r.get('raw_text') for r in records]),
            'numeric_previews':numeric_previews(records,('strength','frequency_pattern','timing','dose_quantity_raw','duration_raw'))}

def capabilities(mode):
    return {'mode':mode,'supported_scripts':['latin','devanagari','mixed'],
            'script_detection_stage':'after_extraction','script_is_not_verified_language':True,
            'ui_language_affects_extraction':False,'handwriting':'experimental',
            'accuracy_evaluated':False,'requires_explicit_analysis':True}
