"""Mocked provider/source tests. These are NOT image-recognition accuracy tests."""
import copy
import json
from pathlib import Path
from unittest.mock import MagicMock
from types import SimpleNamespace
import pytest
import reader
import medication_instructions as medication
import investigations
from prescription_language import ascii_digits,explicit_days,script_observation,hindi_flags

MANIFEST=Path(__file__).parents[2]/'api/evaluation/fixtures/manifest.json'
def sample(identifier='hindi_printed'):
    return next(f for f in json.loads(MANIFEST.read_text(encoding='utf-8-sig'))['fixtures'] if f['id']==identifier)

@pytest.mark.parametrize('text,kind',[('Take 1 tablet','latin'),('सुबह १ गोली','devanagari'),('DEMO-A सुबह 1 tablet','mixed'),('DEMO-A।','latin'),('', 'unknown')])
def test_script_evidence_is_not_language_proof(text,kind):
    assert script_observation([text])=={'script':kind,'source':'original_extracted_text','language_verified':False}

@pytest.mark.parametrize('text,count',[('५ दिन तक',5),('5 दिन तक',5),('सुबह १ गोली ५ दिन तक',5),('for 5 days',5),('३-५ दिन तक',None),('३ से ५ दिन तक',None),('हर ५ दिन',None),('५ दिन में',None),('१.५ दिन',None),('-५ दिन',None),('० दिन',None),('पाँच दिन तक',None)])
def test_only_explicit_unambiguous_numeric_days(text,count):assert explicit_days(text)==count

def test_medicine_unicode_preserved_and_ten_field_contract_unchanged():
    original=sample()['expected_medicines'];before=copy.deepcopy(original)
    record=reader.normalize_model_response(original)[0]
    assert set(record)==set(reader.FIELDS) and original==before
    assert record['name']=='डेमो-ए' and record['strength']=='10 mg'
    assert record['frequency_pattern']=='दिन में २ बार' and record['duration_days']==5
    assert record['timing']==original[0]['timing'] and record['raw_text']==original[0]['raw_text']
    assert record['needs_review'] and record['salt'] is None

def test_no_transliterated_or_unsupported_fields_or_duration_are_filled():
    record=sample()['expected_medicines'][0]
    record.update(name='Demo-A',strength='10 mg',salt='Invented ingredient',duration_days=9)
    result=reader.normalize_model_response([record])[0]
    assert all(result[k] is None for k in ('name','strength','salt','duration_days'))
    assert result['raw_text']==record['raw_text'] and result['needs_review']
    with pytest.raises(reader.ModelResponseError):reader.normalize_model_response([{**record,'needs_review':'false'}])
    with pytest.raises(reader.ModelResponseError):reader.normalize_model_response([{**record,'duration_days':'५'}])
    with pytest.raises(reader.ModelResponseError):reader.normalize_model_response([{**record,'dose_quantity':1}])

def test_explicit_bilingual_generic_identity_and_hindi_strength_are_normalized_without_changing_source():
    raw='सेटिरिज़िन 10 मि.ग्रा. (Cetirizine 10 mg)'
    source={'raw_text':raw,'name':raw,'salt':None,'strength':'10 मि.ग्रा.',
            'form':None,'frequency_pattern':None,'duration_days':None,'timing':None,
            'confidence':None,'needs_review':True}
    result=reader.normalize_model_response([source])[0]
    assert result['raw_text']==raw and result['name']=='Cetirizine'
    assert result['strength']=='10 mg' and result['needs_review'] is True
    assert result['frequency_pattern'] is None and result['duration_days'] is None
    assert result['salt'] is None
    hindi_only=reader.normalize_model_response([{**source,'raw_text':'अज्ञात 10 मि.ग्रा.',
                                                 'name':'अज्ञात'}])[0]
    assert hindi_only['name']=='अज्ञात' and hindi_only['strength']=='10 mg'

def test_separate_hindi_instruction_is_retained_as_its_own_record():
    raw='सेटिरिज़िन 10 मि.ग्रा. (Cetirizine 10 mg) १ गोली दिन में एक बार ३ दिन रात में खाने के बाद'
    item={field:None for field in medication.TEXT_FIELDS}
    item.update(medicine_name_raw='सेटिरिज़िन',raw_text=raw,dose_quantity_raw='१',
                dose_unit_raw='गोली',frequency_raw='दिन में एक बार',
                timing_raw='रात में खाने के बाद',duration_raw='३ दिन')
    result=medication.normalize_medication_instructions_response(
        {'instructions':[{**item,'uncertainty_reasons':[],'needs_review':True}],'issues':[]},
        source_image_sha256='a'*64)
    row=result['instructions'][0]
    assert row['raw_text']==raw and row['medicine_name_raw']=='सेटिरिज़िन'
    assert row['dose_quantity_raw']=='१' and row['duration_raw']=='३ दिन'
    assert row['frequency_raw']=='दिन में एक बार' and row['timing_raw']=='रात में खाने के बाद'

def test_instructions_preserve_devanagari_digits_units_and_source_substrings():
    fixture=sample();raw=fixture['instruction_response'];before=copy.deepcopy(raw)
    result=medication.normalize_medication_instructions_response(raw,source_image_sha256='a'*64)
    r=result['instructions'][0]
    assert raw==before and r['dose_quantity_raw']=='१' and r['dose_unit_raw']=='गोली'
    assert r['duration_raw']=='५ दिन तक' and r['needs_review']
    assert ascii_digits(r['duration_raw'])=='5 दिन तक'
    changed=copy.deepcopy(raw);changed['instructions'][0]['dose_quantity_raw']='1'
    r=medication.normalize_medication_instructions_response(changed,source_image_sha256='b'*64)['instructions'][0]
    assert r['dose_quantity_raw'] is None and 'unsupported_source_value' in r['uncertainty_reasons']

@pytest.mark.parametrize('unit',['मि.ग्रा.','मिलीग्राम','ग्राम'])
def test_hindi_mass_strength_does_not_establish_dose(unit):
    r=sample()['instruction_response']['instructions'][0]
    r.update(raw_text=f'डेमो-ए ५०० {unit} गोली',medicine_name_raw='डेमो-ए',dose_quantity_raw='५००',dose_unit_raw=unit,frequency_raw=None,timing_raw=None,duration_raw=None)
    output=medication.normalize_medication_instructions_response({'instructions':[r],'issues':[]},source_image_sha256='a'*64)['instructions'][0]
    assert output['dose_quantity_raw'] is None and output['dose_unit_raw'] is None
    assert 'dose_not_explicit' in output['uncertainty_reasons']

def test_hindi_ranges_tapers_abbreviations_and_unknown_doses_require_review():
    flags=hindi_flags('सु. १ या २ गोली फिर कम करें, ३ से ५ दिन तक',duration='३ से ५ दिन तक',quantity='१ या २')
    assert {'frequency_requires_clarification','duration_range','variable_dose','variable_or_tapering_instruction'}<=flags
    r=sample()['instruction_response']['instructions'][0]
    r.update(raw_text='डेमो-ए ? गोली सुबह लें',dose_quantity_raw='?',dose_unit_raw='गोली',timing_raw='सुबह',duration_raw=None,frequency_raw=None)
    result=medication.normalize_medication_instructions_response({'instructions':[r],'issues':[]},source_image_sha256='a'*64)['instructions'][0]
    assert result['dose_quantity_raw'] is None and 'ambiguous_dose' in result['uncertainty_reasons']

def test_hindi_negated_test_is_not_turned_into_an_order():
    raw=sample()['investigation_response'];raw['investigations'][0].update(raw_text='जाँच: नमूना-जाँच नहीं कराएँ',order_context_raw='जाँच')
    result=investigations.normalize_investigations_response(raw,source_image_sha256='a'*64)
    assert not result['investigations'] and 'negated_mentions_omitted' in result['issues']

def test_real_entry_point_sends_multilingual_prompt_once_to_mocked_sdk(monkeypatch):
    fixture=sample();client=MagicMock();factory=MagicMock(return_value=client)
    client.__enter__.return_value=client
    client.models.generate_content.return_value=SimpleNamespace(text=json.dumps(fixture['expected_medicines'],ensure_ascii=False))
    monkeypatch.setattr(reader.genai,'Client',factory);monkeypatch.setattr(reader,'_configuration',lambda:('fictional-key','configured-model'))
    data=(MANIFEST.parent/fixture['file']).read_bytes()
    result=reader.read_prescription(data)
    assert result[0]['raw_text']==fixture['expected_medicines'][0]['raw_text']
    assert client.models.generate_content.call_count==1
    call=client.models.generate_content.call_args.kwargs
    assert call['model']=='configured-model' and 'mixed Hindi-English' in call['config'].system_instruction
