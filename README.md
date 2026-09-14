# Amigo del Viento

*(nombre técnico del repo: `condition-alert`)*

Avisa por mail o Telegram cuando se dan las condiciones de viento que vos
elegís para volar en parapente — no solo en superficie, sino en distintas
capas de altura (despegue, aterrizaje, +1000m, corredores en altura para
travesías), más nubosidad y techo de nubes estimado. Corre solo, gratis,
en la nube — nadie tiene que dejar nada prendido.

## ¿Por qué no usar Windy Alerts o similares?

Esas herramientas evalúan un solo punto en superficie, con 8 direcciones
cardinales gruesas (N, NE, E...), y las alertas son función paga. Acá cada
suscriptor pide sus propias condiciones, con rango de grados exacto, en
varias capas de altura combinadas a la vez — gratis, y abierto para que
cualquiera lo extienda.

## Sitios disponibles hoy

Grünten (Allgäu, Alemania), Cerro Otto, Cerro San Martín / La Vieja,
Piltriquitrón, Vicente López, Loma Bola, Merlo, Cuchi Corral y Luján
(Argentina). Ver la lista completa y actualizada en
[`docs/sites.json`](docs/sites.json).

## Cómo sumarte (como piloto)

Completá la [página de alta](https://kindmartin.github.io/condition-alert/):
elegís tu sitio en un mapa satelital, cómo querés que te avisen (mail y/o
Telegram), y la condición de viento que te interesa (con un selector
visual para la dirección). Se sincroniza solo cada 15 minutos — no hace
falta pedirle nada a nadie.

¿Tu sitio no está en la lista? Proponelo en la
[página de sitios nuevos](https://kindmartin.github.io/condition-alert/new-site.html)
marcando el punto en el mapa — se revisa antes de activarse.

## Cómo sumarte al proyecto

Está recién arrancando. Si querés aportar ideas, reportar algo que no
anda, o meter mano al código — bienvenido. Para el detalle de cómo está
armado, cómo operarlo, y cómo replicarlo para tu propio club, ver
[`MANUAL.md`](MANUAL.md).

⚠️ Es un pronóstico automático — verificá siempre las condiciones en el
lugar antes de volar.
