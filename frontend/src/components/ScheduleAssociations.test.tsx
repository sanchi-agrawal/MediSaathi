// @vitest-environment jsdom
import {afterEach,it,expect,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ScheduleAssociations from './ScheduleAssociations'
import type {ScheduleContext,SchedulingClient} from '../lib/scheduling'
import {setLanguage} from '../lib/language'
import {ApiError} from '../lib/prescriptions'
import {setTheme} from '../lib/theme'
const state:ScheduleContext={analysis_id:'a',medicine_revision:'m',instruction_revision:'i',scheduling_revision:'s',ready:true,status:'ready',medicines:[{raw_text:'DEMO 1 tablet BD morning and night for 3 days',name:'DEMO',salt:null,strength:null,form:'tablet',frequency_pattern:'BD',duration_days:3,timing:'morning and night',confidence:null,needs_review:false}],instructions:[{instruction_id:'instruction_001',medicine_name_raw:'DEMO',raw_text:'DEMO 1 tablet BD morning and night for 3 days',dose_quantity_raw:'1',dose_unit_raw:'tablet',frequency_raw:'BD',timing_raw:'morning and night',duration_raw:'3 days',route_raw:null,uncertainty_reasons:[],needs_review:false,confirmation_required:true}],instruction_issues:[],association:null,plan:null,result:null,error:null,association_proposals:[{medicine_ref:'medicine_001',instruction_id:'instruction_001',status:'proposed'}]}
function client(value=state){let current=value;return {current:vi.fn(async()=>current),associate:vi.fn(async()=>{current={...value,associations:[{association_id:'link',medicine_ref:'medicine_001',instruction_id:'instruction_001'}],association_proposals:[{medicine_ref:'medicine_001',instruction_id:'instruction_001',status:'confirmed' as const}]};return current})} as unknown as SchedulingClient}

afterEach(()=>{cleanup();setLanguage('en');setTheme('dark')})
it('prepares an exact pair for explicit approval without associating on mount',async()=>{
 const api=client();render(<ScheduleAssociations client={api}/>);await screen.findByRole('button',{name:'Confirm suggested link: DEMO'});expect(api.associate).not.toHaveBeenCalled();expect(screen.getAllByText('DEMO 1 tablet BD morning and night for 3 days')[0]).toBeTruthy()
 await userEvent.setup().click(screen.getByRole('button',{name:'Confirm suggested link: DEMO'}));await screen.findByText('Association confirmed.');expect(api.associate).toHaveBeenCalledWith(state,'medicine_001','instruction_001')
})
it('never chooses an ambiguous pair automatically',async()=>{
 const api=client({...state,association_proposals:[{medicine_ref:'medicine_001',instruction_id:null,status:'ambiguous'}]});render(<ScheduleAssociations client={api}/>);await screen.findByText('More than one pairing is possible. Compare the source and choose the correct pair below.');expect(screen.queryByRole('button',{name:/Confirm suggested link/})).toBeNull();expect(api.associate).not.toHaveBeenCalled()
})
it('distinguishes instruction extraction that never ran from unconfirmed instructions',async()=>{
 const api=client({...state,ready:false,instructions:[],instruction_state:{status:'not_requested',reviewed:false,confirmed:false},association_proposals:[]});render(<ScheduleAssociations client={api}/>);await screen.findByText('Dosage instructions have not been extracted. Select Dosage instructions and explicitly analyze that section.');expect(api.associate).not.toHaveBeenCalled()
})
it('translates suggestions without changing medical source values',async()=>{
 setLanguage('hi');setTheme('light');const api=client();render(<ScheduleAssociations client={api}/>);await screen.findByRole('button',{name:'सुझाए गए संबंध की पुष्टि करें: DEMO'});expect(screen.getAllByText('DEMO 1 tablet BD morning and night for 3 days')[0]).toBeTruthy();expect(document.documentElement.dataset.theme).toBe('light')
})
it('does not mark a failed confirmation as successful',async()=>{
 const api=client();vi.mocked(api.associate).mockRejectedValue(new Error('stale'));render(<ScheduleAssociations client={api}/>);await userEvent.setup().click(await screen.findByRole('button',{name:'Confirm suggested link: DEMO'}));await waitFor(()=>expect(screen.queryByText('Association confirmed.')).toBeNull());await screen.findByRole('status')
})
it('rejects a successful-looking POST if the saved pair is absent on the next GET',async()=>{
 const api=client();vi.mocked(api.current).mockResolvedValue(state)
 render(<ScheduleAssociations client={api}/>);await userEvent.setup().click(await screen.findByRole('button',{name:'Confirm suggested link: DEMO'}))
 await screen.findByRole('alert');expect(screen.queryByText('Link saved and verified in the current workspace.')).toBeNull()
})
it('preserves the actual stale revision error instead of a generic failure only',async()=>{
 const api=client();vi.mocked(api.associate).mockRejectedValue(new ApiError('stale_result','Reload current scheduling revision.',409));render(<ScheduleAssociations client={api}/>);await userEvent.setup().click(await screen.findByRole('button',{name:'Confirm suggested link: DEMO'}))
 expect((await screen.findByRole('alert')).textContent).toContain('stale_result')
})
it('requires a separate explicit acknowledgement before confirming numeric slot meaning',async()=>{
 const association={association_id:'link',medicine_ref:'medicine_001',instruction_id:'instruction_001'}
 const value:ScheduleContext={...state,association,associations:[association],association_proposals:[],instructions:[{...state.instructions[0],frequency_raw:'1-0-1'}],automatic:[{medicine_ref:'medicine_001',association,template:null,issues:['notation_confirmation_required']}]}
 const api=client(value);api.confirmNotation=vi.fn(async()=>{const fresh={...value,scheduling_revision:'new',automatic:[{...value.automatic![0],issues:[]}]};vi.mocked(api.current).mockResolvedValue(fresh);return fresh})
 render(<ScheduleAssociations client={api}/>);const button=await screen.findByRole('button',{name:'Confirm named timing slots'})
 expect((button as HTMLButtonElement).disabled).toBe(true);expect(api.confirmNotation).not.toHaveBeenCalled()
 const u=userEvent.setup();await u.click(screen.getByRole('checkbox'));await u.click(button)
 await waitFor(()=>expect(api.confirmNotation).toHaveBeenCalledTimes(1));expect(vi.mocked(api.confirmNotation).mock.calls[0][0].association?.association_id).toBe('link')
})
it('submits backend-proposed named slots and verifies their persisted values',async()=>{
 const association={association_id:'link',medicine_ref:'medicine_001',instruction_id:'instruction_001'}
 const pending={medicine_ref:'medicine_001',association,template:null,issues:['notation_confirmation_required'],proposed_slots:['morning','night'] as ('morning'|'night')[],confirmed_slots:[]}
 const value:ScheduleContext={...state,association,associations:[association],association_proposals:[],automatic:[pending]}
 const api=client(value);api.confirmSlots=vi.fn(async()=>{const fresh:ScheduleContext={...value,scheduling_revision:'fresh',automatic:[{...pending,issues:[],confirmed_slots:['morning','night']}]};vi.mocked(api.current).mockResolvedValue(fresh);return fresh})
 render(<ScheduleAssociations client={api}/>);await screen.findByText(/Proposed time-of-day slots: morning, night/)
 expect(api.confirmSlots).not.toHaveBeenCalled();const user=userEvent.setup();await user.click(screen.getByRole('checkbox'));await user.click(screen.getByRole('button',{name:'Confirm named timing slots'}))
 await waitFor(()=>expect(api.confirmSlots).toHaveBeenCalledWith(expect.objectContaining({association}),['morning','night']))
 await screen.findByText(/Confirmed time-of-day slots: morning, night/)
})
