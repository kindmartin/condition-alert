# Diseño: Alertas de corredor/travesía (XC) — documento de acuerdo

Estado: **propuesta, no implementada**. Este documento existe para fijar
el alcance y las decisiones de diseño antes de tocar código — no es una
promesa de fecha ni un compromiso de que se construya tal cual está acá.

## 1. Qué existe hoy — "Alerta de sitio"

Un suscriptor define, para UN sitio, una o más capas (`layers`) que deben
cumplirse **todas a la vez, en la misma hora**, para que esa alerta
puntual se considere "prendida" (ver `MANUAL.md` §2 y §5). Es una
condición estática: "¿en esta hora, en este punto, el viento está en el
rango que pedí?". No sabe nada de una hora a la siguiente, ni de otros
sitios.

## 2. Qué se propone — "Alerta de región/travesía"

Un segundo modo de alerta, para planificar vuelos de travesía (XC):
en vez de evaluar una condición estática, evalúa si el pronóstico ofrece
una **secuencia de corrientes de viento aprovechables**, en distintas
alturas y/o distintos puntos geográficos, encadenadas en el tiempo, que
permitirían planificar una ruta.

Ejemplo dado por el usuario: despegás de Sitio A en T0, a 1000m tenés
corriente hacia el norte por 3 horas, después a 2000m tenés viento oeste
que te permite seguir — el sistema debería poder avisar "el jueves entre
las 11 y las 17 se da esa secuencia".

## 3. Por qué es un cambio de fondo (no una capa más)

- El motor actual (`src/rules.py::evaluate_layers`) evalúa **una hora a
  la vez, un punto a la vez, todo con AND**. Una condición de corredor
  necesita razonar sobre **una ventana de varias horas consecutivas**,
  con el viento pudiendo (o debiendo) cambiar de una hora a otra según un
  plan, y potencialmente sobre **más de un punto geográfico** a la vez
  (no solo `launch`/`landing` de un sitio, sino puntos intermedios de una
  ruta).
- El formato de mail (`src/notify.py`) asume "estas horas cumplen todas
  las capas" — para un corredor habría que mostrar algo más parecido a un
  itinerario ("11:00-14:00 @1000m rumbo N, 14:00-17:00 @2000m rumbo O").
- El modelo de datos de una capa (`kind`/`point`/`meters`/`min_speed_kmh`
  /`directions`) no tiene forma de expresar "esto viene DESPUÉS de
  aquello" ni "esto es en otro lugar geográfico distinto al sitio".

## 4. Preguntas a resolver antes de diseñar el modelo de datos

Estas son las decisiones que faltan, en orden de impacto:

1. **¿Un corredor es sobre UN sitio (mismo lat/lon, solo cambia la
   altura) o sobre una ruta de varios puntos geográficos?** El ejemplo
   del usuario menciona ambos ("a 1000m vas al norte" sugiere desplazamiento
   real, no solo ganancia de altura en el mismo punto). Si es multi-punto,
   hay que definir esos puntos — ¿los elige el suscriptor a mano en un
   mapa (como el despegue de un sitio), o el sistema los infiere a partir
   de dirección+velocidad+tiempo (proyectar dónde estaría el piloto)?
2. **¿Cuántos "tramos" puede tener una alerta de corredor?** ¿2 fijos (el
   caso del ejemplo), o una lista de largo variable?
3. **¿Cómo se define la duración de cada tramo?** ¿El suscriptor fija
   "3 horas" a mano, o el sistema busca automáticamente cuánto dura la
   ventana de esa condición en el pronóstico?
4. **¿Qué significa que "se cumple"?** ¿Los tramos tienen que ser
   consecutivos sin huecos? ¿Alcanza con que existan en algún orden
   dentro de una ventana del día, o tienen que empezar en un T0 elegido
   por el usuario (ej. "despego a las 11")?
5. **¿Esto reemplaza el estado on/off actual, o convive con un tercer
   estado?** Una condición de corredor puede "casi" cumplirse (2 de 3
   tramos) — ¿eso es ruido que no se avisa, o vale la pena un aviso
   parcial?
6. **Formato del aviso**: ¿un mail con un itinerario tramo por tramo
   alcanza, o esto eventualmente necesita algo visual (un mapa con la
   ruta proyectada)? Un mapa es una página nueva tipo `new-site.html`,
   no un cambio de `notify.py`.
7. **Costo de cómputo**: hoy `wind-check.yml` hace un fetch batcheado de
   Open-Meteo por corrida. Evaluar corredores multi-punto multi-tramo
   para cada suscriptor podría requerir mucha más combinatoria (todas las
   horas × todas las alturas × todos los puntos de ruta) — hay que pensar
   el algoritmo de búsqueda antes de asumir que "correr cada hora" sigue
   siendo viable sin optimizar.

## 5. Alcance mínimo posible (si se decide construir una v1 chica)

Para no bloquear todo el diseño en las preguntas de arriba, una versión
inicial acotada podría ser:

- Un corredor = **un solo sitio** (mismo lat/lon que ya tiene, sin puntos
  de ruta nuevos), con **N tramos fijos definidos a mano** por el
  suscriptor: cada tramo es `{altura (agl/msl+metros), dirección,
  velocidad min/max, duración mínima en horas}`.
- "Se cumple" = existe una secuencia de horas consecutivas en el
  pronóstico donde el tramo 1 se sostiene por su duración mínima,
  inmediatamente seguido (o dentro de una tolerancia de horas) por el
  tramo 2 sosteniéndose la suya, etc.
- El aviso es texto plano con el itinerario encontrado (sin mapa).

Esto es significativamente más chico que "puntos de ruta geográficos
proyectados en el tiempo", pero ya resolvería el ejemplo concreto del
usuario (misma ubicación, altura y dirección cambiando con el tiempo) y
se puede extender a multi-punto más adelante si hace falta.

## 6. Próximo paso

Este documento queda como referencia. Para avanzar hace falta que el
usuario responda las preguntas de la sección 4 (al menos la 1, 2 y 4, que
determinan el modelo de datos) antes de tocar `rules.py`/`notify.py`.
