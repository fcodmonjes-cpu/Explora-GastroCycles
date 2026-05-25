# `assets/` — imágenes de referencia

Archivos estáticos referenciados desde el código. Versionados explícitamente
en `.gitignore` mediante `!assets/**` (que sobreescribe las reglas globales
`*.png`, `*.svg`, etc.).

## Convenciones

- **Nombres descriptivos en kebab-case**: `montaje-desayuno-mesa.jpg`,
  `bar-montaje-botellas.jpg`, `cierre-cafetera.jpg`. Que el archivo se lea
  solo, sin abrir el código.
- **Formatos**: preferir `.jpg` para fotos (peso), `.svg` para diagramas.
- **Resolución**: comprimir antes de commitear. Una foto de referencia no
  necesita más de ~1500px de lado largo. El módulo Checklist las muestra
  como thumbnail 96×64 y como fullscreen `max-width:92vw`.
- **Rutas en el código**: siempre relativas a la raíz, ej.
  `'assets/montaje-desayuno-mesa.jpg'`.

## Uso desde Checklist

En `CHK_SEED`, cualquier tarea puede ser un objeto con `image` en vez de un
string. El render genera un thumbnail clickable que abre la imagen en
fullscreen.

```js
montaje: {
  desayuno: [
    { label: 'Texto de la tarea …',
      image: 'assets/montaje-desayuno-mesa.jpg' },
    'Otra tarea sin imagen',
    …
  ]
}
```
