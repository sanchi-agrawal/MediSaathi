"""Real reader normalization -> ordinary review -> stored count -> clock API."""
import json
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
from contextlib import contextmanager
import socket,threading,time
import httpx,uvicorn
from api.tests.test_clock_scheduling import LOCAL_CONNECT
from api.tests.test_clock_scheduling import runtime,ordinary_review,clock_state,clock_body,send,synthetic_image
from api.tests.test_local_auth import HEADERS
from api.tests.test_sections import confirm,route as section_route
from api.tests.test_downstream import current,binding,route

@contextmanager
def client(app,transport,monkeypatch):
    if transport=='asgi':
        with TestClient(app,base_url='http://localhost',headers=HEADERS) as c:yield c
        return
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def only_local(address,*args,**kwargs):
        assert address==('127.0.0.1',port),'External requests forbidden'
        return LOCAL_CONNECT(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',only_local)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.02)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers=HEADERS) as c:yield c
    finally:server.should_exit=True;thread.join(5);sock.close()

@pytest.mark.parametrize('transport',['asgi','tcp'])
@pytest.mark.parametrize('flagged',[False,True])
def test_reviewed_literal_count_case_and_whitespace_handoff(runtime,flagged,transport,monkeypatch):
    app,sdk,_=runtime
    responses=list(sdk.models.generate_content.side_effect)
    medicines=json.loads(responses[0].text);instructions=json.loads(responses[1].text)
    for index,frequency in enumerate(('twice daily','once daily','once daily')):
        text=medicines[index]['raw_text'].replace(medicines[index]['frequency_pattern'],frequency.upper()).replace('take 2 tablet','take 1 tablet')
        medicines[index].update(raw_text=text,frequency_pattern=frequency.upper())
        instructions['instructions'][index].update(raw_text=text,frequency_raw=frequency.replace(' ','  ') if index==0 else frequency.upper(),dose_quantity_raw='1')
    medicines[0]['needs_review']=flagged
    responses[:2]=[SimpleNamespace(text=json.dumps(medicines)),SimpleNamespace(text=json.dumps(instructions))]
    sdk.models.generate_content.side_effect=responses
    with client(app,transport,monkeypatch) as c:
        source=ordinary_review(c,synthetic_image(medicines),slots=False)
        state=clock_state(c)
        session=next(iter(app.state.sessions.sessions.values()))
        section=session.ai.snapshot()['prescription']['sections']['instructions']['reviewed']
        # Confirmation does not restore a field rejected by the source validator.
        assert section['instructions'][0]['frequency_raw'] is None
        assert 'unsupported_source_value' in section['instructions'][0]['uncertainty_reasons']
        assert [m['administrations_per_day'] for m in state['medicines']]==[0,1,1]
        assert [m['eligible'] for m in state['medicines']]==[False,True,True]
        partial=clock_body(state);partial['medicines']=partial['medicines'][1:]
        assert send(c,state,partial).status_code==200
        # Existing explicit review corrects the field to exactly what the
        # synthetic source says; no normalization/repair is done by Scheduling.
        old=c.get(section_route(source,'instructions')).json()
        item=old['payload']['instructions'][0]
        item.update(frequency_raw='TWICE DAILY',uncertainty_reasons=[],needs_review=False)
        old['payload']['issues']=[]
        confirm(c,old,'instructions')
        for index in range(1,4):
            fresh=current(c)
            r=c.post(route(fresh,'/associations'),json={**binding(fresh),'medicine_ref':f'medicine_{index:03}','instruction_id':f'instruction_{index:03}'})
            assert r.status_code==200,r.text
        state=clock_state(c)
        assert [m['administrations_per_day'] for m in state['medicines']]==[2,1,1]
        assert all(m['eligible'] for m in state['medicines'])
        if flagged:
            assert c.get('/api/prescriptions/current').json()['records'][0]['needs_review'] is True
            assert 'medicine_review_flag' not in state['medicines'][0]['issues']
            assert state['medicines'][0]['review_details']['flagged'] is True
        body=clock_body(state)
        response=send(c,state,body);assert response.status_code==200,response.text
        assert [len(m['days']) for m in response.json()['medicines']]==[5,3,7]
        assert [len(m['days'])*len(m['clock_times']) for m in response.json()['medicines']]==[10,3,7]
        assert c.get('/api/prescriptions/current').json()['revision']==source['revision']
        assert sdk.models.generate_content.call_count==2

@pytest.mark.parametrize('code',['blurred','clipped','unreadable','ambiguous_dose','unsupported_source_value'])
def test_unattributed_global_hazards_remain_blocking(code):
    from ai_integration import _unsafe_instruction
    safe={'uncertainty_reasons':[]}
    assert _unsafe_instruction({'instructions':[safe],'issues':[code]},safe)
    bad={'uncertainty_reasons':[code]}
    assert _unsafe_instruction({'instructions':[safe,bad],'issues':[code]},bad)
    # Quality hazards remain global even when repeated on a different record.
    assert _unsafe_instruction({'instructions':[safe,bad],'issues':[code]},safe)==(code in ('blurred','clipped','unreadable'))
