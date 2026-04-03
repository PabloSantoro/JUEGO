# BLSA Bot en Replit (desde el celular)

## Pasos para correr el bot desde tu celular

### 1. Registrate en MetaApi (gratis)
- Entrá a https://app.metaapi.cloud
- Creá una cuenta gratis
- Andá a **Accounts → Add account**
- Completá:
  - Login: `10010390946`
  - Password: `K!Ks1pHn`
  - Server: `MetaQuotes-Demo`
  - Platform: `MT5`
- Guardá el **Account ID** que te da (lo vas a necesitar)

### 2. Copiá tu API Token
- En MetaApi andá a **API Tokens**
- Copiá el token

### 3. Creá un proyecto en Replit (desde el celular)
- Entrá a https://replit.com
- Registrate gratis
- Creá un **Python** repl nuevo
- Subí o pegá el archivo `metaapi_bot.py`

### 4. Instalá la dependencia en Replit
En la consola de Replit escribí:
```
pip install metaapi-cloud-sdk pandas numpy
```

### 5. Completá tus datos en metaapi_bot.py
```python
API_TOKEN  = "pega tu token aqui"
ACCOUNT_ID = "pega tu account id aqui"
```

### 6. Corré el bot
Presioná el botón **Run** en Replit

---

## ¿Qué hace el bot?
1. Se conecta a tu cuenta demo MT5 vía la nube
2. Analiza EURUSD (SMA20, SMA50, RSI14)
3. Abre una orden de compra de prueba
4. Muestra el resultado en pantalla
