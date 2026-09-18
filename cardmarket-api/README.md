# cardmarket-api

Standalone, framework-free Python package that turns **Cardmarket's public daily
data files** into a local pricing API: no account, no API key, no quota.

Cardmarket regenerates its Pokémon price guide every night (~02:49 Paris) on a
public S3 bucket. This package downloads it (conditional GET), caches it on
disk, indexes it in RAM by `idProduct`, and serves EUR price views.

```python
from cardmarket_api import CardmarketPriceApi

api = CardmarketPriceApi(cache_dir="var/cardmarket")
api.refresh()                      # network only when stale (ETag / If-Modified-Since)
prices = api.get_card_prices(719636)   # Mewtwo AR — sv2a 183
print(prices.reference_eur)        # trend-based reference, never `low`
```

## Design notes

- **`low` is banned as a value reference.** It is the single cheapest listing of
  the product, any language (Korean on Japanese sets) and any condition. The
  reference order is sales-based: `trend → avg7 → avg30 → avg1 → avg`.
- **The package knows nothing about TCGdex or GoupixDex.** Mapping a card to its
  Cardmarket `idProduct` is the consumer's job (GoupixDex harvests it from the
  TCGdex `pricing.cardmarket.idProduct` field at scan time).
- `*-holo` columns of the guide describe the product's reverse-holo variant
  (e.g. Poké Ball / Master Ball patterns on Japanese sets) and are exposed as
  `reverse_reference_eur`.

## Layout

```
cardmarket_api/
  price_api.py                 CardmarketPriceApi (facade)
  types.py                     PriceGuideRow / CardmarketCardPrices / refresh report
  errors.py
  clients/price_guide_download_client.py   S3 download, conditional GET
  stores/price_guide_store.py              disk cache + RAM index (thread-safe)
  services/card_price_service.py           reference picking rules
  services/price_guide_refresh_service.py  staleness + refresh orchestration
```

The package is deliberately self-contained (httpx as sole dependency) so it can
be extracted from the GoupixDex monorepo as-is.
