"""Boucle asyncio pour uvicorn + nodriver sous Windows.

Avec ``--reload``, uvicorn peut sélectionner ``SelectorEventLoop``, incompatible avec
``create_subprocess_exec`` (Chrome / nodriver).

Pour un ``--loop`` **personnalisé**, uvicorn importe **un seul** objet et le passe à
``asyncio.Runner`` : ce doit être la **classe** de boucle (ex. ``ProactorEventLoop``),
appelée sans argument pour créer l'instance — **pas** une fonction du type
``lambda use_subprocess: ProactorEventLoop`` (voir ``uvicorn.config.Config.get_loop_factory``).

Référence à passer à ``uvicorn --loop`` sur Windows :
"""

from __future__ import annotations

# Classe d'event loop du stdlib (importable uniquement sous Windows).
UVICORN_WINDOWS_NODRIVER_LOOP = "asyncio.windows_events:ProactorEventLoop"
