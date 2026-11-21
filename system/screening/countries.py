"""Country gazetteer: canonical name, ISO2, ISO3, other names, demonyms.

Territories count as their own country (POLICY.md principle 6), so they get
their own rows. Each line: Canonical|ISO2|ISO3|alias;alias|demonym;demonym
"""

_RAW = """
Afghanistan|AF|AFG||Afghan
Albania|AL|ALB||Albanian
Algeria|DZ|DZA||Algerian
Andorra|AD|AND||Andorran
Angola|AO|AGO||Angolan
Antigua and Barbuda|AG|ATG|Antigua|Antiguan
Argentina|AR|ARG||Argentine;Argentinian
Armenia|AM|ARM||Armenian
Australia|AU|AUS||Australian
Austria|AT|AUT||Austrian
Azerbaijan|AZ|AZE||Azerbaijani;Azeri
Bahamas|BS|BHS|The Bahamas|Bahamian
Bahrain|BH|BHR||Bahraini
Bangladesh|BD|BGD||Bangladeshi
Barbados|BB|BRB||Barbadian
Belarus|BY|BLR||Belarusian
Belgium|BE|BEL||Belgian
Belize|BZ|BLZ||Belizean
Benin|BJ|BEN||Beninese
Bhutan|BT|BTN||Bhutanese
Bolivia|BO|BOL|Plurinational State of Bolivia|Bolivian
Bosnia and Herzegovina|BA|BIH|Bosnia|Bosnian
Botswana|BW|BWA||Motswana;Batswana
Brazil|BR|BRA|Brasil|Brazilian
Brunei|BN|BRN|Brunei Darussalam|Bruneian
Bulgaria|BG|BGR||Bulgarian
Burkina Faso|BF|BFA||Burkinabe
Burundi|BI|BDI||Burundian
Cabo Verde|CV|CPV|Cape Verde|Cape Verdean
Cambodia|KH|KHM||Cambodian
Cameroon|CM|CMR||Cameroonian
Canada|CA|CAN||Canadian
Central African Republic|CF|CAF||Central African
Chad|TD|TCD||Chadian
Chile|CL|CHL||Chilean
China|CN|CHN|People's Republic of China|Chinese
Colombia|CO|COL||Colombian
Comoros|KM|COM||Comorian
Congo|CG|COG|Republic of the Congo;Congo-Brazzaville|Congolese
Democratic Republic of the Congo|CD|COD|DR Congo;DRC;Congo-Kinshasa;Democratic Republic of Congo|
Costa Rica|CR|CRI||Costa Rican
Côte d'Ivoire|CI|CIV|Cote d'Ivoire;Ivory Coast|Ivorian
Croatia|HR|HRV||Croatian
Cuba|CU|CUB||Cuban
Cyprus|CY|CYP||Cypriot
Czech Republic|CZ|CZE|Czechia|Czech
Denmark|DK|DNK||Danish;Dane
Djibouti|DJ|DJI||Djiboutian
Dominica|DM|DMA||
Dominican Republic|DO|DOM||Dominican
Ecuador|EC|ECU||Ecuadorian
Egypt|EG|EGY||Egyptian
El Salvador|SV|SLV||Salvadoran
Equatorial Guinea|GQ|GNQ||Equatoguinean
Eritrea|ER|ERI||Eritrean
Estonia|EE|EST||Estonian
Eswatini|SZ|SWZ|Swaziland|Swazi
Ethiopia|ET|ETH||Ethiopian
Fiji|FJ|FJI||Fijian
Finland|FI|FIN||Finnish;Finn
France|FR|FRA||French
Gabon|GA|GAB||Gabonese
Gambia|GM|GMB|The Gambia|Gambian
Georgia|GE|GEO||Georgian
Germany|DE|DEU|Deutschland|German
Ghana|GH|GHA||Ghanaian
Greece|GR|GRC||Greek
Grenada|GD|GRD||Grenadian
Guatemala|GT|GTM||Guatemalan
Guinea|GN|GIN||Guinean
Guinea-Bissau|GW|GNB|Guinea Bissau|Bissau-Guinean
Guyana|GY|GUY||Guyanese
Haiti|HT|HTI||Haitian
Honduras|HN|HND||Honduran
Hungary|HU|HUN||Hungarian
Iceland|IS|ISL||Icelandic;Icelander
India|IN|IND||Indian
Indonesia|ID|IDN||Indonesian
Iran|IR|IRN|Islamic Republic of Iran|Iranian
Iraq|IQ|IRQ||Iraqi
Ireland|IE|IRL|Republic of Ireland|Irish
Israel|IL|ISR||Israeli
Italy|IT|ITA|Italia|Italian
Jamaica|JM|JAM||Jamaican
Japan|JP|JPN||Japanese
Jordan|JO|JOR||Jordanian
Kazakhstan|KZ|KAZ||Kazakh;Kazakhstani
Kenya|KE|KEN||Kenyan
Kiribati|KI|KIR||I-Kiribati
North Korea|KP|PRK|Democratic People's Republic of Korea;DPRK|North Korean
South Korea|KR|KOR|Republic of Korea;Korea|South Korean;Korean
Kosovo|XK|XKX||Kosovar;Kosovan
Kuwait|KW|KWT||Kuwaiti
Kyrgyzstan|KG|KGZ|Kyrgyz Republic|Kyrgyz
Laos|LA|LAO|Lao People's Democratic Republic|Lao;Laotian
Latvia|LV|LVA||Latvian
Lebanon|LB|LBN||Lebanese
Lesotho|LS|LSO||Basotho
Liberia|LR|LBR||Liberian
Libya|LY|LBY||Libyan
Liechtenstein|LI|LIE||Liechtensteiner
Lithuania|LT|LTU||Lithuanian
Luxembourg|LU|LUX||Luxembourgish;Luxembourger
Madagascar|MG|MDG||Malagasy
Malawi|MW|MWI||Malawian
Malaysia|MY|MYS||Malaysian
Maldives|MV|MDV||Maldivian
Mali|ML|MLI||Malian
Malta|MT|MLT||Maltese
Marshall Islands|MH|MHL||Marshallese
Mauritania|MR|MRT||Mauritanian
Mauritius|MU|MUS||Mauritian
Mexico|MX|MEX|México|Mexican
Micronesia|FM|FSM|Federated States of Micronesia|Micronesian
Moldova|MD|MDA|Republic of Moldova|Moldovan
Monaco|MC|MCO||Monegasque
Mongolia|MN|MNG||Mongolian
Montenegro|ME|MNE||Montenegrin
Morocco|MA|MAR||Moroccan
Mozambique|MZ|MOZ||Mozambican
Myanmar|MM|MMR|Burma|Burmese
Namibia|NA|NAM||Namibian
Nauru|NR|NRU||Nauruan
Nepal|NP|NPL||Nepali;Nepalese
Netherlands|NL|NLD|The Netherlands;Holland|Dutch
New Zealand|NZ|NZL||New Zealander
Nicaragua|NI|NIC||Nicaraguan
Niger|NE|NER||Nigerien
Nigeria|NG|NGA||Nigerian
North Macedonia|MK|MKD|Macedonia|Macedonian
Norway|NO|NOR||Norwegian
Oman|OM|OMN||Omani
Pakistan|PK|PAK||Pakistani
Palau|PW|PLW||Palauan
Palestine|PS|PSE|Palestina;State of Palestine;Palestinian Territories|Palestinian
Panama|PA|PAN||Panamanian
Papua New Guinea|PG|PNG||Papua New Guinean
Paraguay|PY|PRY||Paraguayan
Peru|PE|PER|Perú|Peruvian
Philippines|PH|PHL|The Philippines|Filipino;Philippine
Poland|PL|POL||Polish;Pole
Portugal|PT|PRT||Portuguese
Qatar|QA|QAT||Qatari
Romania|RO|ROU||Romanian
Russia|RU|RUS|Russian Federation|Russian
Rwanda|RW|RWA||Rwandan
Saint Kitts and Nevis|KN|KNA|St Kitts and Nevis|Kittitian
Saint Lucia|LC|LCA|St Lucia|Saint Lucian
Saint Vincent and the Grenadines|VC|VCT|St Vincent and the Grenadines|Vincentian
Samoa|WS|WSM||Samoan
San Marino|SM|SMR||Sammarinese
Sao Tome and Principe|ST|STP|São Tomé and Príncipe|Santomean
Saudi Arabia|SA|SAU||Saudi;Saudi Arabian
Senegal|SN|SEN||Senegalese
Serbia|RS|SRB||Serbian
Seychelles|SC|SYC||Seychellois
Sierra Leone|SL|SLE||Sierra Leonean
Singapore|SG|SGP||Singaporean
Slovakia|SK|SVK|Slovak Republic|Slovak
Slovenia|SI|SVN||Slovenian;Slovene
Solomon Islands|SB|SLB||Solomon Islander
Somalia|SO|SOM||Somali
South Africa|ZA|ZAF||South African
South Sudan|SS|SSD||South Sudanese
Spain|ES|ESP|España|Spanish
Sri Lanka|LK|LKA||Sri Lankan
Sudan|SD|SDN||Sudanese
Suriname|SR|SUR||Surinamese
Sweden|SE|SWE||Swedish;Swede
Switzerland|CH|CHE||Swiss
Syria|SY|SYR|Syrian Arab Republic|Syrian
Taiwan|TW|TWN|Republic of China|Taiwanese
Tajikistan|TJ|TJK||Tajik
Tanzania|TZ|TZA|United Republic of Tanzania|Tanzanian
Thailand|TH|THA||Thai
Timor-Leste|TL|TLS|East Timor|Timorese
Togo|TG|TGO||Togolese
Tonga|TO|TON||Tongan
Trinidad and Tobago|TT|TTO|Trinidad|Trinidadian;Tobagonian
Tunisia|TN|TUN||Tunisian
Turkey|TR|TUR|Türkiye;Turkiye|Turkish
Turkmenistan|TM|TKM||Turkmen
Tuvalu|TV|TUV||Tuvaluan
Uganda|UG|UGA||Ugandan
Ukraine|UA|UKR||Ukrainian
United Arab Emirates|AE|ARE|UAE;Emirates|Emirati
United Kingdom|GB|GBR|UK;Great Britain;Britain;England;Scotland;Wales;Northern Ireland;United Kingdom of Great Britain and Northern Ireland|British;Scottish;Welsh
United States|US|USA|United States of America;U.S.;U.S.A.;America|American
Uruguay|UY|URY||Uruguayan
Uzbekistan|UZ|UZB||Uzbek
Vanuatu|VU|VUT||Ni-Vanuatu
Vatican City|VA|VAT|Holy See;Vatican|
Venezuela|VE|VEN|Bolivarian Republic of Venezuela|Venezuelan
Vietnam|VN|VNM|Viet Nam|Vietnamese
Yemen|YE|YEM||Yemeni
Zambia|ZM|ZMB||Zambian
Zimbabwe|ZW|ZWE||Zimbabwean
Hong Kong|HK|HKG|Hong Kong SAR;Hong Kong Special Administrative Region of China|Hongkonger
Macao|MO|MAC|Macau;Macao SAR;Macao Special Administrative Region of China|Macanese
Puerto Rico|PR|PRI||Puerto Rican
Guam|GU|GUM||Guamanian
Northern Mariana Islands|MP|MNP|Commonwealth of the Northern Mariana Islands|
American Samoa|AS|ASM||
United States Virgin Islands|VI|VIR|US Virgin Islands;U.S. Virgin Islands|
British Virgin Islands|VG|VGB|Virgin Islands (British)|
Cayman Islands|KY|CYM||Caymanian
Bermuda|BM|BMU||Bermudian
Gibraltar|GI|GIB||Gibraltarian
Jersey|JE|JEY||
Guernsey|GG|GGY||
Isle of Man|IM|IMN||Manx
Anguilla|AI|AIA||Anguillan
Montserrat|MS|MSR||
Turks and Caicos Islands|TC|TCA||
Falkland Islands|FK|FLK||
Greenland|GL|GRL||Greenlandic
Faroe Islands|FO|FRO|Faroes|Faroese
Aruba|AW|ABW||Aruban
Curaçao|CW|CUW|Curacao|
Sint Maarten|SX|SXM||
New Caledonia|NC|NCL||
French Polynesia|PF|PYF||
Réunion|RE|REU|Reunion|
Martinique|MQ|MTQ||
Guadeloupe|GP|GLP||
French Guiana|GF|GUF||
Mayotte|YT|MYT||
Western Sahara|EH|ESH||
"""

NOT_COUNTRIES = {"international", "europe", "worldwide", "global", "africa", "asia",
                 "middle east", "european union", "eu", "unknown", "none", "n/a", "na"}


def _rows():
    for line in _RAW.strip().splitlines():
        canon, iso2, iso3, aliases, demonyms = (line.split("|") + ["", "", "", "", ""])[:5]
        yield (canon.strip(), iso2.strip(), iso3.strip(),
               [a.strip() for a in aliases.split(";") if a.strip()],
               [d.strip() for d in demonyms.split(";") if d.strip()])


ROWS = list(_rows())
