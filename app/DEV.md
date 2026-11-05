# Développement local

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
pip install pytest httpx
export DEV_OTP=true COOKIE_SECURE=false APP_ENV=development
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Ouvrir http://127.0.0.1:8000. Le code de test OTP est renvoyé seulement lorsque `DEV_OTP=true` et la requête provient de localhost ; il est interdit en production. En local, SQLite est utilisé par défaut.

Tests : `pytest -q tests/test_api.py`. Attention : exécuter des tests ne remplace pas un audit.

Pour simuler deux utilisateurs localement : utiliser deux profils de navigateur distincts, chacun avec une adresse étudiante de démonstration différente ; aucun email réel n'est envoyé en DEV_OTP.
