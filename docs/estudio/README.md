# Fichas de estudio del menú

Material para que el equipo de sala **memorice** el menú antes del turno. No
reemplaza al handbook, que es la herramienta de consulta *durante* el servicio:
esto es lo que se estudia antes.

Cada ficha condensa un día del ciclo de almuerzo:

1. Cómo se lee una restricción — los cuatro estados y los nueve ejes.
2. El esqueleto del día — las posiciones fijas, que son la percha de memoria.
3. El menú preparación por preparación, tal como aparece en la app.
4. Un gancho por plato.
5. Las trampas del día y las dudas abiertas para cocina.
6. Autoevaluación.
7. Anexo: el prompt para generar el podcast de repaso.

## Regenerar

```
pip install reportlab
python3 docs/estudio/generar_ficha_estudio.py 1     # día 1..4
```

Los **datos de los platos** (nombre, guion, matriz de nueve ejes, notas de
condicional) se leen de `index.html` en cada corrida. No se transcriben: así la
ficha no puede terminar diciendo algo distinto de lo que muestra la app. Si el
menú cambia, se regenera y ya está.

La **prosa didáctica** —los ganchos, las trampas, las preguntas— vive en los
diccionarios `GANCHOS`, `TRAMPAS`, `DUDAS` y `PREGUNTAS` al final del script,
con una entrada por día. Hoy sólo está escrito el día 1; los días 2 a 4 piden
agregar su entrada en esos cuatro diccionarios.

## El PDF no está versionado

`.gitignore` excluye `*.pdf` a propósito, así que el archivo generado no entra
al repo. Se regenera en un comando, que es el motivo por el que el generador sí
está versionado. Si en algún momento conviene tener el PDF en el repo, hay que
agregar la excepción explícita en `.gitignore`.

## Dependencias

`reportlab` (no es dependencia de la app: el handbook sigue sin build step ni
paquetes). Las tipografías se toman del sistema: IBM Plex Serif para la prosa y
DejaVu Sans Mono para las franjas de veredicto — esta última es obligatoria
donde haya `✗` o `✓`, porque ninguna serif disponible trae esos glifos y salen
como cajas vacías.
