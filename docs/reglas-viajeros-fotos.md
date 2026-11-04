# Reglas para las fotos de viajeros (`viajeros_fotos`)

> **Estado (2026-11-03): publicado.** 1 (RTDB) y 2 (Storage) publicados por el
> owner; 3 (CORS) resultó innecesario; 5 (ciclo de vida a 30 días) aplicado.
> Queda 4 por comprobar en el log de la primera corrida del sync en `main`.
> Este archivo sirve para rehacerlo si hiciera falta.

Cosas que se publican **desde la consola**, una sola vez. Las hace el
owner: la app y el script ya están listos y, mientras no estén publicadas, nada
se rompe (la ficha queda como antes y subir una foto muestra el aviso coral
"La foto NO se guardó").

Como siempre (ARCHITECTURE §4.3): **se agregan SOBRE las reglas vigentes**,
copiadas de la consola, nunca escritas de memoria ni reemplazando el archivo.

---

## 1. Realtime Database — el índice

Consola de Firebase → *Realtime Database* → *Reglas*. Pegar como hermano de
`viajeros_notas` (misma condición que el resto: `auth != null`, y cuando las
reglas cierren por uid pasa a `auth.uid === '<uid>'` como las demás):

```json
"viajeros_fotos": {
  ".read": "auth != null",
  "$pid": {
    ".write": "auth != null",
    ".validate": "newData.hasChildren(['path','ts','out'])",
    "path":   { ".validate": "newData.isString() && newData.val().beginsWith('viajeros_fotos/' + $pid + '/') && newData.val().length <= 140" },
    "ts":     { ".validate": "newData.isNumber()" },
    "out":    { ".validate": "newData.isString() && newData.val().matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)" },
    "outAt":  { ".validate": "newData.isString() && newData.val().length <= 16" },
    "hab":    { ".validate": "newData.isString() && newData.val().length <= 8" },
    "autor":  { ".validate": "newData.isString() && newData.val().length <= 24" },
    "w":      { ".validate": "newData.isNumber()" },
    "h":      { ".validate": "newData.isNumber()" },
    "_visto": { ".validate": "newData.isNumber()" },
    "$otro":  { ".validate": false }
  }
}
```

**Por qué así.** La validación es el límite de daño: el `path` sólo puede
apuntar a la carpeta de esa misma persona, el `out` tiene que ser una fecha (de
él depende la purga) y `$otro: false` rechaza cualquier campo no previsto. El
script escribe `_visto`, `out` y `outAt` con el service account, que pasa por
encima de las reglas.

## 2. Storage — los bytes

Consola de Firebase → *Storage* → *Rules*. Agregar junto a los bloques de
`estudio/` y `recepcion/`, dentro de `match /b/{bucket}/o { … }`:

```
match /viajeros_fotos/{pid}/{archivo} {
  // Ver UNA foto: con sesión (el gate). Listar la carpeta: nunca, ni con sesión.
  allow get: if request.auth != null;
  allow list: if false;
  // Subir: sólo un JPEG chico, con el nombre que arma la app ({ms}.jpg).
  // Nunca pisar uno existente: reemplazar = subir otro y borrar el viejo.
  allow create: if request.auth != null
                && pid.matches('[a-z0-9-]{1,80}')
                && archivo.matches('[0-9]{13}[.]jpg')
                && request.resource.size < 500 * 1024
                && request.resource.contentType == 'image/jpeg';
  allow update: if false;
  // Borrar: cualquiera con el gate (decisión del owner, 2026-11-03).
  allow delete: if request.auth != null;
}
```

**Por qué `list: false`.** Son fotos de huéspedes. Con `get` hace falta saber el
nombre exacto del archivo, y ese nombre sólo está en el índice de la RTDB, que
también pide sesión. Con `list` abierto, cualquiera con sesión podría bajar la
carpeta entera de una vez. La app nunca lista; el script lista con el service
account, que no pasa por estas reglas.

**El downloadToken.** Storage le pone a cada archivo subido un token que abre
la foto sin sesión (`?alt=media&token=…`). La app nunca lo usa ni lo guarda:
baja la foto con el header de auth, como las capturas de Recepción. Para leer
ese token también hace falta sesión, y muere con el archivo cuando la purga lo
borra.

## 3. CORS del bucket — NO hizo falta

Medido el 2026-11-03, después de publicar 2: el endpoint v0
(`firebasestorage.googleapis.com`) responde el preflight con
`POST, GET, HEAD, DELETE, PATCH` y las subidas/borrados con
`Access-Control-Allow-Origin: *` por su cuenta, sin mirar el CORS del bucket.
Ese CORS (§3.4, sólo `GET`) es el de la descarga con `?alt=media`, y ya estaba.
**Sólo si** algún día subir desde el navegador da un error de CORS en la
consola, esto lo resuelve (Cloud Shell, proyecto `explora-cafe-orders`):

```bash
echo '[{"origin":["*"],"method":["GET","POST","DELETE"],"responseHeader":["Authorization","Content-Type","Content-Length"],"maxAgeSeconds":3600}]' > cors.json
gcloud storage buckets update gs://explora-cafe-orders.firebasestorage.app --cors-file=cors.json
```

`origin: *` sigue siendo deliberado: la seguridad la ponen las reglas, no el
origen, y así funcionan los previews por commit.

## 4. Permiso del service account sobre el bucket — para la purga

El sync (`purgar_fotos`) borra con el service account de `FIREBASE_KEY`. Si es
el de *Firebase Admin SDK* (`firebase-adminsdk-…@explora-cafe-orders.iam.gserviceaccount.com`),
normalmente ya tiene permiso. **Se comprueba en el log de la primera corrida en
`main`:**

- `fotos: N en el índice · … · corte …` → anda.
- `no pude listar Storage (403 …)` → falta el permiso. Darlo así:

```bash
gcloud storage buckets add-iam-policy-binding gs://explora-cafe-orders.firebasestorage.app \
  --member="serviceAccount:<client_email del FIREBASE_KEY>" --role="roles/storage.objectAdmin"
```

No hacen falta secrets nuevos: el script usa el mismo `FIREBASE_KEY`, con un
scope más (`devstorage.read_write`).

## 5. (Recomendado) Red de abajo: borrado automático a los 30 días

Si un día el cron deja de correr, que ninguna foto viva más de un mes. Es una
regla del bucket, no código. **Primero mirar que el bucket no tenga ya una
regla de ciclo de vida**, porque `--lifecycle-file` la reemplaza entera:

```bash
gcloud storage buckets describe gs://explora-cafe-orders.firebasestorage.app --format="default(lifecycle_config)"
```

Si sale vacío:

```bash
echo '{"rule":[{"action":{"type":"Delete"},"condition":{"age":30,"matchesPrefix":["viajeros_fotos/"]}}]}' > lifecycle.json
gcloud storage buckets update gs://explora-cafe-orders.firebasestorage.app --lifecycle-file=lifecycle.json
```

Sólo toca `viajeros_fotos/`: `estudio/` y `recepcion/` quedan como están.

---

## Verificación desde afuera (sin credencial)

Todos deben dar **401** (RTDB) o **403** (Storage):

```bash
DB=https://explora-cafe-orders-default-rtdb.firebaseio.com
ST=https://firebasestorage.googleapis.com/v0/b/explora-cafe-orders.firebasestorage.app/o
curl -s -o /dev/null -w '%{http_code}\n' "$DB/viajeros_fotos.json"
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -d '{"x":1}' "$DB/viajeros_fotos/prueba.json"
curl -s -o /dev/null -w '%{http_code}\n' "$ST?prefix=viajeros_fotos/"
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: image/jpeg' --data-binary 'x' "$ST?name=viajeros_fotos/prueba/1234567890123.jpg"
```

## Orden de despliegue

1. La app con la interfaz de fotos llega a `staging`. Sin las reglas, las
   lecturas dan 401 (no se dibuja ninguna foto) y subir muestra el aviso coral.
   Nada se rompe.
2. Publicar **1**, **2** y **3** (y **5** si se quiere la red de abajo).
3. QA en staging desde el PC (arrastrar, pegar, elegir) y mirar en el iPhone.
4. Mergear a `main`. **Recién ahí corre la purga del servidor**: el cron de
   GitHub Actions usa el script de la rama default. Mientras tanto la app
   esconde las fotos vencidas y las borra cuando alguien abre PGO ese día.
5. Mirar el log de la primera corrida en `main` (punto **4**).
