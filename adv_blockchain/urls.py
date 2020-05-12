from django.conf.urls import url
from . import api

urlpatterns = [
    url('mine', api.mine),
    # url('new_transaction', api.new_transaction),
    # url('full_chain', api.full_chain),
    url('totals', api.totals),
    url('last_proof', api.last_proof),
    url('get_balance', api.get_balance)
]
