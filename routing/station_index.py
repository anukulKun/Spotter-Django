from __future__ import annotations
import threading
import numpy as np
from django.db.models import Q
from .models import FuelStation
_lock=threading.Lock(); _data=None
def clear():
    global _data
    with _lock: _data=None
def load():
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                rows=list(FuelStation.objects.filter(latitude__isnull=False,longitude__isnull=False).values('opis_id','name','address','city','state','latitude','longitude','price_usd_per_gallon'))
                _data=rows
    return _data
def stations(): return load()
