import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unicodedata
from availability_guard import availability, install


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tracker = SimpleNamespace(scraper=SimpleNamespace(norm=lambda v: unicodedata.normalize('NFKD', v).encode('ascii', 'ignore').decode().lower()))

    def test_aggregate_stock_cannot_override_no_home_delivery(self):
        item = {'loja':'Darty', 'stock':True}
        html = '<main><h1>Acer Nitro</h1>Entrega ao domícilio indisponível Recolhe na loja em 30 minutos</main>'
        row = availability(item, html, self.tracker)
        self.assertFalse(row['eligible'])
        self.assertEqual(row['status'], 'STORE_ONLY_UNVERIFIED')

    def test_home_delivery_can_confirm_darty(self):
        html = '<main><h1>Lenovo</h1>Recebe em casa Entrega 2 de outubro</main>'
        self.assertTrue(availability({'loja':'Darty','stock':True}, html, self.tracker)['eligible'])

    def test_stock_false_and_unknown_are_not_recommendations(self):
        for store in ('Darty','Globaldata','Clickfiel'):
            for stock in (False, None):
                self.assertFalse(availability({'loja':store,'stock':stock}, '', self.tracker)['eligible'])

    def test_related_products_do_not_confirm_home_delivery(self):
        html = '<main><div id="ProductInfo-test"><h1>Acer Nitro</h1>Entrega ao domícilio indisponível</div><aside>Entrega 2 de outubro</aside></main>'
        self.assertFalse(availability({'loja':'Darty','stock':True}, html, self.tracker)['eligible'])

    def test_darty_explicit_available_for_home_delivery(self):
        html = '<main><div id="ProductInfo-123"><h1>Asus TUF</h1><p>Disponível para entrega ao domicílio</p></div></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertTrue(res['eligible'])
        self.assertEqual(res['status'], 'AVAILABLE')
        self.assertTrue(res.get('home_delivery'))

    def test_darty_home_delivery_deadline_confirmed(self):
        html = '<main><div id="ProductInfo-123"><h1>HP Victus</h1><p>Entrega ao domicílio em 24/48h</p></div></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertTrue(res['eligible'])
        self.assertEqual(res['status'], 'AVAILABLE')
        self.assertTrue(res.get('home_delivery'))

    def test_darty_generic_actions_insufficient_proof(self):
        html = '<main><div id="ProductInfo-123"><h1>Lenovo LOQ</h1><button>Adicionar ao carrinho</button><span>Envio em 24h</span><button>Comprar</button></div></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertFalse(res['eligible'])
        self.assertEqual(res['status'], 'AVAILABILITY_UNCONFIRMED')
        self.assertEqual(res.get('source'), 'product_fulfilment_missing')

    def test_darty_generic_home_delivery_without_confirmation_insufficient(self):
        html = '<main><div id="ProductInfo-123"><h1>MSI Katana</h1><p>Custos de entrega ao domicílio sob consulta</p></div></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertFalse(res['eligible'])
        self.assertEqual(res['status'], 'AVAILABILITY_UNCONFIRMED')

    def test_darty_contradictory_indicators_prioritizes_unavailable(self):
        # Presença de menção positiva não anula badge de indisponibilidade
        html = '<main><div id="ProductInfo-123"><h1>Acer Predator</h1><p>Disponível para entrega ao domicílio</p><p>Entrega ao domicílio indisponível</p></div></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertFalse(res['eligible'])
        self.assertEqual(res['status'], 'STORE_ONLY_UNVERIFIED')

        # Restrição a loja física prioritária
        html_store = '<main><div id="ProductInfo-123"><h1>Acer Predator</h1><p>Disponível para entrega ao domicílio</p><p>Apenas recolha em loja</p></div></main>'
        res_store = availability({'loja':'Darty','stock':True}, html_store, self.tracker)
        self.assertFalse(res_store['eligible'])
        self.assertEqual(res_store['status'], 'STORE_ONLY_UNVERIFIED')

    def test_darty_out_of_stock_indicators(self):
        for phrase in ('Artigo esgotado', 'Fora de stock', 'Esgotado'):
            html = f'<main><div id="ProductInfo-123"><h1>Asus ROG</h1><span>{phrase}</span></div></main>'
            res = availability({'loja':'Darty','stock':True}, html, self.tracker)
            self.assertFalse(res['eligible'])
            self.assertEqual(res['status'], 'OUT_OF_STOCK')

    def test_darty_aside_recommended_isolation(self):
        html = '<main><div id="ProductInfo-main"><h1>Dell G15</h1><p>Consultar disponibilidade</p></div><aside><div>Recomendados: Disponível para entrega ao domicílio</div></aside></main>'
        res = availability({'loja':'Darty','stock':True}, html, self.tracker)
        self.assertFalse(res['eligible'])
        self.assertEqual(res['status'], 'AVAILABILITY_UNCONFIRMED')

    def test_other_stores_behavior_preserved(self):
        self.assertTrue(availability({'loja':'FNAC','stock':True}, '', self.tracker)['eligible'])
        self.assertEqual(availability({'loja':'FNAC','stock':True}, '', self.tracker)['status'], 'AVAILABLE')
        self.assertFalse(availability({'loja':'Globaldata','stock':False}, '', self.tracker)['eligible'])
        self.assertEqual(availability({'loja':'Globaldata','stock':False}, '', self.tracker)['status'], 'OUT_OF_STOCK')
        self.assertFalse(availability({'loja':'Globaldata','stock':None}, '', self.tracker)['eligible'])
        self.assertEqual(availability({'loja':'Globaldata','stock':None}, '', self.tracker)['status'], 'AVAILABILITY_UNCONFIRMED')

    def test_actual_runner_rejects_unavailable_before_tiering(self):
        code = '''
import json, runner
config=json.load(open('config/config.json'))
spec=runner.scraper.specs('Acer Nitro i9-13900H RTX 5060 32GB 1TB')
spec['offer_availability']={'eligible':False,'status':'OUT_OF_STOCK'}
assessment=runner.tracker.score_allow_unknown(spec,1138.20,config['weights'],config['settings'])
assert assessment['status']=='REJEITADO',assessment
assert assessment.get('value_score') is None
assert runner.tracker.rejection_reason(assessment)=='availability_not_eligible'
assert __import__('rejection_guard')._CURRENT_REJECTION_REASON.get()=='availability_not_eligible'
'''
        # rejection_reason is imported by the telemetry guard, not exported by tracker.
        code = code.replace('runner.tracker.rejection_reason', '__import__("rejection_guard").rejection_reason')
        result = subprocess.run([sys.executable,'-c',code], cwd=Path(__file__).resolve().parents[1], capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_actual_brain_rewards_better_display_and_confirmed_power(self):
        code = '''
import json, runner
config=json.load(open('config/config.json'))
spec=runner.scraper.specs('Lenovo Legion i7-13650HX RTX 5060 32GB 1TB 16 FHD 144Hz')
spec['teclado_pt']='confirmado'
spec['offer_availability']={'eligible':True,'status':'AVAILABLE'}
weak=dict(spec,tgp_w=60,ecra_brightness_nits=250,ecra_srgb_percent=65,ecra_painel='IPS')
strong=dict(spec,tgp_w=100,ecra_brightness_nits=500,ecra_srgb_percent=100,ecra_painel='OLED')
scores=[runner.tracker.score_allow_unknown(s,1400,config['weights'],config['settings']) for s in (weak,strong)]
assert all(s['status']=='ACEITE' for s in scores),scores
assert scores[1]['value_score']>scores[0]['value_score'],scores
assert scores[1].get('brain_policy'),scores
'''
        result = subprocess.run([sys.executable,'-c',code], cwd=Path(__file__).resolve().parents[1], capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_needs_price_refresh_triggers_for_any_store_when_availability_stale(self):
        buckets = {}
        fake_tracker = SimpleNamespace(
            adaptive_fetch=lambda *a, **k: (None, None, None),
            enrich=lambda item, cfg: (item, {}),
            select_with_cache=lambda items, *a: items,
            apply_exact_market_price_evidence=lambda records, settings: records,
            score_allow_unknown=lambda spec, *a: {'status': 'ACEITE'},
            record_offer=lambda history, *a: (None, 'k'),
            needs_price_refresh=lambda prev, item, settings, **k: False,
            bucket=lambda store: buckets.setdefault(store, {}),
        )
        install(fake_tracker)
        now = datetime.now(timezone.utc)
        fresh_ts = (now - timedelta(hours=1)).isoformat()
        stale_ts = (now - timedelta(hours=8)).isoformat()
        settings = {'availability_ttl_hours': 6}
        for store in ('Auchan', 'Clickfiel', 'Darty'):
            url = f'https://example.com/{store.lower()}/1'
            stock_val = True if store == 'Darty' else None
            item = {'loja': store, 'url': url, 'stock': stock_val}
            self.assertTrue(fake_tracker.needs_price_refresh(None, item, settings))
            buckets[store] = {'availability_by_url': {url: {'checked_at': stale_ts, 'eligible': True}}}
            self.assertTrue(fake_tracker.needs_price_refresh(None, item, settings))
            buckets[store] = {'availability_by_url': {url: {'checked_at': fresh_ts, 'eligible': True}}}
            self.assertFalse(fake_tracker.needs_price_refresh(None, item, settings))
            buckets[store] = {'availability_by_url': {url: {'checked_at': stale_ts, 'eligible': False}}}
            self.assertFalse(fake_tracker.needs_price_refresh(None, {'loja': store, 'url': url, 'stock': False}, settings))
        # Stores whose listing card already confirms stock=True do not burn refresh slots unnecessarily
        self.assertFalse(fake_tracker.needs_price_refresh(None, {'loja': 'FNAC', 'url': 'https://example.com/fnac/1', 'stock': True}, settings))
