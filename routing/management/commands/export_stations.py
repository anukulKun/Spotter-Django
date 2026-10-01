import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from routing.models import FuelStation
class Command(BaseCommand):
    help='Export imported stations into a portable geocoded CSV.'
    def add_arguments(self,p):p.add_argument('--output',type=Path,default=Path('data/stations_geocoded.csv'))
    def handle(self,*args,**o):
        out=o['output']; out.parent.mkdir(parents=True,exist_ok=True); fields=['opis_id','name','address','city','state','lat','lng','price','price_min','price_max','rows_merged','is_price_outlier','geocode_quality']
        with out.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            for x in FuelStation.objects.order_by('opis_id'):
                w.writerow({'opis_id':x.opis_id,'name':x.name,'address':x.address,'city':x.city,'state':x.state,'lat':x.latitude or '','lng':x.longitude or '','price':x.price_usd_per_gallon,'price_min':x.price_min,'price_max':x.price_max,'rows_merged':x.price_rows_merged,'is_price_outlier':x.is_price_outlier,'geocode_quality':x.geocode_quality})
        self.stdout.write(f'Exported {FuelStation.objects.count()} stations to {out}')
