# Aansluitvoorwaarden

## Waarom deze voorwaarden bestaan

De profielservice deelt persoonsgegevens van ambtenaren met aangesloten apps op basis van expliciete toestemming. Die toestemming is alleen iets waard als de afnemer-app zich gedraagt zoals de ambtenaar mag verwachten: alleen gebruiken wat nodig is, niet doorgeven, en niet een eigen kopie aanleggen.

De voorwaarden hieronder zijn de basis waarop het vertrouwensmodel rust. Wordt hier niet aan voldaan dan kan de toestemming worden ingetrokken.

## Voorwaarden

1. **Geen lokale kopie van profielgegevens.** De app slaat de opgehaalde velden niet op in eigen database of cache met lange levensduur. Gegevens worden bij elke nodige weergave opnieuw via de API opgehaald. Een korte request-scoped cache (binnen één HTTP-request of korte sessie-cache van enkele minuten) is acceptabel; persistente opslag niet. Reden: één bron van waarheid, en intrekken van toestemming of uit-dienst-treding werkt direct door. (data bij de bron)

2. **Werkt zonder toestemming.** Als de ambtenaar (nog) geen toestemming heeft gegeven of de toestemming heeft ingetrokken, blijft de app functioneren. De profielverrijking is een *plus*, geen *vereiste*. Geen blokkerende schermen, geen "geef eerst toestemming voordat je verder kunt".

3. **Incidentmelding.** Bij een vermoeden van een datalek, gecompromitteerde client-secret, of misbruik van de API meldt de afnemer dit binnen 24 uur bij de beheerder van de profielservice.
