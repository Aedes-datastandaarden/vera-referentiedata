# VERA Referentiedata
<img align="right" width="300" src="https://github.com/Aedes-datastandaarden/.github/blob/main/350px-Logo_Stichting_VERA.png">In deze repository wordt de VERA referentie data beheerd. All referentie data wordt vastgelegd in een zgn. CSV bestand.
Dit CSV bestand kan eenvoudig worden geimporteerd in Excel.

Periodiek zullen nieuwe versies van de referentiedata worden vrijgegeven in de vorm van een release. Het versienummer bevat de datum van vrijgave (yymmdd).

Het CSV bestand kent de volgende kolommen:
|Kolom|Toelichting|
|---|---|
|Soort|Type aanduiding van de referentiedata|
|Code|Unieke code|
|Naam|Unieke naam|
|Omschrijving|Aanvullende omschrijving |
|Begindatum|Datum waarop de rerefentiedata is geintroduceerd|
|Einddatum|Datum waarop de rerefentiedata uit gebruik is genomen (obsolete)|
|Parent|Gekoppelde referentiedata. Bijv. Soort en detailsoort|
|Informatiedomein|Tot welke informatiedomein behoort de referentie data|

Alle referentiedata staat ook gepubliceerd op de [CORA/VERA site](https://cora.wikixl.nl/index.php/VERA_Referentiedata).

## API Referentiedata
Referentiedata kan nu ook via een API worden opgevraagd. De OpenAPI definitie is te vinden op: https://vera-service.azurewebsites.net/swagger/index.html
De API ondersteunt twee endpoints:
|Endpoint|Beschrijving|
|---|---|
|https://vera-service.azurewebsites.net/api/referentiedata|Opvragen van all referentiedata|
|https://vera-service.azurewebsites.net/api/referentiedata/{soort}|Opvragen referentiedata voor één referentiedata soort|

Als optionele parameter kan de query string parameter "version" worden meegegeven. Hiermee kan een specifieke versie van de referentie data worden opgevraagd. Alle beschikbare versies zijn terug te vinden op github via [Releases](https://github.com/Aedes-datastandaarden/vera-referentiedata/releases). Wanneer parameter version niet is gespecificeerd, wordt de meest recente versie (latest) teruggegeven. Version wordt ook vermeld in de response header.

Voorbeeld aanroepen:
|Url|Toelichting|
|---|---|
|https://vera-service.azurewebsites.net/api/referentiedata?version=v4.0.221125|Ophalen alle referentiedata van [Release 4.0.221125](https://github.com/Aedes-datastandaarden/vera-referentiedata/releases/tag/v4.0.221125)|
|https://vera-service.azurewebsites.net/api/referentiedata/AANBIEDINGSTATUS|Ophalen referentiedata voor referentiedata soort AANBIEDINGSTATUS|

