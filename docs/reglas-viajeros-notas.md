# Reglas de Firebase para `/viajeros_notas`

Bloque a **agregar** a las reglas vigentes. No reemplaces el archivo completo con
esto: las reglas se escriben SOBRE las que están en la consola, copiadas de ahí
—nunca de memoria—. Una propuesta escrita de memoria ya dejó el Checklist muerto
una vez (ARCHITECTURE §4.3).

## Qué agregar

Pegar como hermano de los paths que ya existen (`viajeros`, `comandas`, …):

```json
"viajeros_notas": {
  ".read": "auth != null",
  "$pid": {
    ".write": "auth != null",
    "_visto": { ".validate": "newData.isNumber()" },
    "$nota": {
      ".validate": "newData.hasChildren(['txt','ts'])",
      "txt":   { ".validate": "newData.isString() && newData.val().length <= 280" },
      "ts":    { ".validate": "newData.isNumber()" },
      "autor": { ".validate": "newData.isString() && newData.val().length <= 24" },
      "chip":  { ".validate": "newData.isString() && newData.val().length <= 40" },
      "$otro": { ".validate": false }
    }
  }
}
```

## Por qué así

**`/viajeros/current` sigue en `.write: false`.** Es la garantía de que la app
—donde escribe cualquiera que tenga la URL— no pueda tocar el dato duro que
viene de PGO. Alergias y dietas sólo las escribe el service account del script.
Las notas son un path aparte justamente para eso.

**La validación es el único control real.** La sesión es anónima: cualquiera con
la URL de la app tiene `auth != null`. Las reglas no pueden decir *quién*
escribe, pero sí acotan *qué* se puede escribir: 280 caracteres, forma fija, y
`$otro: false` rechaza cualquier campo no previsto. Es un límite de daño, no un
control de acceso.

**`_visto` es del script, no de la app.** Es la marca de "esta persona seguía en
casa en tal momento", y de ella depende la purga. El service account bypassea
las reglas, así que la validación de número es sólo higiene.

## Verificación desde afuera (sin credencial)

Los dos deben dar 401:

```bash
DB=https://explora-cafe-orders-default-rtdb.firebaseio.com
curl -s -o /dev/null -w '%{http_code}\n' "$DB/viajeros_notas.json"
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -d '{"x":1}' "$DB/viajeros_notas/prueba.json"
```

Y este debe seguir dando 401 (el dato duro no se escribe desde afuera ni con
sesión):

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -d '{}' "$DB/viajeros/current.json"
```

## Orden de despliegue

1. Publicar la app con la interfaz de notas (sin reglas, las escrituras dan 401
   y se ve el aviso coral: nada se rompe, sólo no guarda).
2. Recién entonces agregar el bloque en la consola.

Al revés no hay riesgo, pero así el equipo nunca ve un estado raro.
