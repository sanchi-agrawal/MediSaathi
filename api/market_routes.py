"""Additive provisional listings; existing verified lookup remains unchanged."""
from fastapi import Query, Request
from pydantic import Field
from .downstream.models import Strict
from pricing_dataset.market import load,search,summary

class ListingRequest(Strict):
    item_id:str=Field(min_length=1,max_length=128)

def register_market_routes(app,authenticate,reject):
    def dataset():
        try:return load()
        except (OSError,ValueError,KeyError,TypeError,ArithmeticError):reject(503,'dataset_unavailable','Medicine listings are unavailable. No prices were inferred.')

    @app.get('/api/pricing/listings/catalogue')
    def catalogue(request:Request,q:str=Query(default='',max_length=200)):
        authenticate(request);data=dataset()
        return {'schema_version':'market-listed-v1','items':search(data,q),'coverage':summary(data),'comparisons_enabled':False}

    @app.post('/api/pricing/listings/lookup')
    def lookup(body:ListingRequest,request:Request):
        authenticate(request);data=dataset()
        item=next((v for v in data['items'] if v['item_id']==body.item_id),None)
        return {'schema_version':'market-listed-v1','state':'listed' if item else 'no_match','item':item,
            'observations':[v for v in data['observations'] if v['item_id']==body.item_id] if item else [],
            'comparisons_enabled':False,'provisional':True}
