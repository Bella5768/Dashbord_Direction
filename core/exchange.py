import json
import logging
import urllib.request
from datetime import datetime

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

RATE_URL = 'https://open.er-api.com/v6/latest/USD'
CACHE_KEY = 'core.usd_gnf_rate'
CACHE_TTL = 3600
FETCH_TIMEOUT = 5
DEFAULT_USD_GNF_RATE = 8788.75


def fetch_live_rate():
    """Taux GNF pour 1 USD (API exchangerate-api, mise à jour quotidienne).

    Retourne (taux, date_source) ou (None, None) en cas d'échec — ne lève jamais d'exception.
    """
    try:
        with urllib.request.urlopen(RATE_URL, timeout=FETCH_TIMEOUT) as response:
            payload = json.loads(response.read().decode('utf-8'))
        rate = float(payload['rates']['GNF'])
        if rate <= 0:
            raise ValueError('taux non positif')
        date = timezone.now()
        raw = payload.get('time_last_update_utc')
        if raw:
            try:
                date = datetime.strptime(raw, '%a, %d %b %Y %H:%M:%S %z')
            except ValueError:
                pass
        return rate, date
    except Exception as exc:
        logger.warning('Taux de change GNF/USD indisponible : %s', exc)
        return None, None


def get_usd_gnf_rate(refresh=False):
    """Taux GNF pour 1 USD — chaîne : cache 1 h → API live → dernier connu → valeur par défaut.

    Retourne {'rate': float, 'date': datetime, 'source': 'live'|'stale'|'default'}.
    Ne bloque jamais une sauvegarde : timeout court et replis silencieux (warning logué).
    """
    cached = cache.get(CACHE_KEY)
    now = timezone.now()
    if cached and not refresh and (now - cached['fetched_at']).total_seconds() < CACHE_TTL:
        return cached

    rate, date = fetch_live_rate()
    if rate is not None:
        value = {'rate': rate, 'date': date, 'source': 'live', 'fetched_at': now}
        cache.set(CACHE_KEY, value, None)
        return value
    if cached:
        return {**cached, 'source': 'stale'}
    value = {'rate': DEFAULT_USD_GNF_RATE, 'date': now, 'source': 'default', 'fetched_at': now}
    cache.set(CACHE_KEY, value, None)
    return value
