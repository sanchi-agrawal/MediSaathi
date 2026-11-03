"""Date comparison only; never a medicine safety or storage assessment."""
from datetime import date,datetime,timezone,timedelta

def expiry_status(payload,confirmed,as_of=None):
    today=as_of or datetime.now(timezone(timedelta(hours=5,minutes=30))).date()
    result={'state':'unclear','as_of':today.isoformat(),'rule':'month-current-unclear-day-inclusive-v1'}
    if not confirmed or not payload or not payload.get('expiry'):return result
    if any(o.get('uncertain') or o.get('association')!='same_product' for o in payload.get('date_observations',[]) if o.get('label_kind')=='expiry'):return result
    expiry=payload['expiry']
    if expiry['precision']=='month':
        target=(expiry['year'],expiry['month']);now=(today.year,today.month)
        result['state']='expired' if target<now else 'not_expired_by_date' if target>now else 'unclear'
    else:result['state']='expired' if date(expiry['year'],expiry['month'],expiry['day'])<today else 'not_expired_by_date'
    return result
