import pytest
from api.downstream.association_proposals import proposals
from api.tests.test_downstream import setup,current,associate,save,approve


def test_confirmed_records_are_proposed_but_never_automatically_linked():
    c,app,_,_=setup();state=current(c)
    assert state['instruction_state']=={'status':'succeeded','reviewed':True,'confirmed':True}
    assert state['association_proposals']==[{'medicine_ref':'medicine_001','instruction_id':'instruction_001','status':'proposed'}]
    assert not state['associations'] and state['automatic'][0]['template'] is None
    state=associate(c)
    assert state['association_proposals'][0]['status']=='confirmed'
    assert state['instructions'][0]['dose_quantity_raw']=='1'
    assert state['automatic'][0]['template']['dose_quantity']==1
    assert approve(c,save(c,state)).status_code==200


@pytest.mark.parametrize('meds,ins,status',[
    ([{'name':'Dolo'}],[],'missing_instruction'),
    ([{'name':'Dolo'}],[{'instruction_id':'i','medicine_name_raw':'Different'}],'unmatched'),
    ([{'name':'Dolo'},{'name':'Dolo'}],[{'instruction_id':'i','medicine_name_raw':'Dolo'}],'ambiguous'),
    ([{'name':'Dolo'}],[{'instruction_id':'i','medicine_name_raw':'Dolo'},{'instruction_id':'j','medicine_name_raw':'Dolo'}],'ambiguous'),
    ([{'name':None}],[{'instruction_id':'i','medicine_name_raw':None}],'unmatched'),
])
def test_uncertain_and_missing_pairs_are_never_proposed(meds,ins,status):
    assert all(p['status']==status and p['instruction_id'] is None for p in proposals(meds,ins,[]))


def test_multiple_exact_pairs_are_independent_and_whitespace_case_only():
    meds=[{'name':'Dolo'},{'name':'Cetirizine'},{'name':'Omeprazole'}]
    ins=[{'instruction_id':str(i),'medicine_name_raw':m['name'].upper()+' ','raw_text':m['name']+' explicitly written'} for i,m in enumerate(meds)]
    result=proposals(meds,ins,[])
    assert [p['instruction_id'] for p in result]==['0','1','2']
    assert all(p['status']=='proposed' for p in result)


def test_review_edits_remove_confirmed_links_and_proposals_until_reconfirmed():
    from api.tests.test_prescriptions import post
    c,_,med,_=setup();associate(c)
    assert post(c,med,'invalidate').status_code==200
    state=current(c)
    assert not state['ready'] and state['association_proposals']==[] and state['associations']==[]
