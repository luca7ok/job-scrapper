from __future__ import annotations

import re
import unicodedata

EUROPE_CODES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO", "CH", "GB",
    "RS", "MK", "BA", "ME", "AL", "XK",
    "UA", "MD", "TR",
}

COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France",
    "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "ES": "Spain", "SE": "Sweden", "IS": "Iceland", "LI": "Liechtenstein", "NO": "Norway",
    "CH": "Switzerland", "GB": "United Kingdom", "RS": "Serbia", "MK": "North Macedonia",
    "BA": "Bosnia and Herzegovina", "ME": "Montenegro", "AL": "Albania", "XK": "Kosovo",
    "UA": "Ukraine", "MD": "Moldova", "TR": "Türkiye", "EU": "Europe (remote)",
}

_COUNTRY_ALIASES = {
    "AT": ["austria", "osterreich", "oesterreich", "autriche"],
    "BE": ["belgium", "belgie", "belgique", "belgien", "belgio"],
    "BG": ["bulgaria", "bulgarien", "balgariya"],
    "HR": ["croatia", "hrvatska", "kroatien"],
    "CY": ["cyprus", "chypre", "zypern", "kypros"],
    "CZ": ["czechia", "czech republic", "ceska republika", "cesko", "tschechien", "republique tcheque"],
    "DK": ["denmark", "danmark", "danemark", "danemark"],
    "EE": ["estonia", "eesti", "estland"],
    "FI": ["finland", "suomi", "finnland", "finlande"],
    "FR": ["france", "frankreich", "francia"],
    "DE": ["germany", "deutschland", "allemagne", "alemania", "germania", "niemcy"],
    "GR": ["greece", "hellas", "ellada", "griechenland", "grece"],
    "HU": ["hungary", "magyarorszag", "ungarn", "hongrie"],
    "IE": ["ireland", "eire", "irland", "irlande", "republic of ireland"],
    "IT": ["italy", "italia", "italien", "italie"],
    "LV": ["latvia", "latvija", "lettland"],
    "LT": ["lithuania", "lietuva", "litauen"],
    "LU": ["luxembourg", "luxemburg"],
    "MT": ["malta"],
    "NL": ["netherlands", "the netherlands", "nederland", "holland", "niederlande", "pays-bas", "pays bas"],
    "PL": ["poland", "polska", "polen", "pologne"],
    "PT": ["portugal"],
    "RO": ["romania", "rumanien", "roumanie"],
    "SK": ["slovakia", "slovensko", "slowakei", "slovak republic"],
    "SI": ["slovenia", "slovenija", "slowenien"],
    "ES": ["spain", "espana", "spanien", "espagne", "spagna"],
    "SE": ["sweden", "sverige", "schweden", "suede"],
    "IS": ["iceland"],
    "LI": ["liechtenstein"],
    "NO": ["norway", "norge", "norwegen", "norvege"],
    "CH": ["switzerland", "schweiz", "suisse", "svizzera", "svizra", "confoederatio helvetica"],
    "GB": ["united kingdom", "great britain", "england", "scotland", "wales", "northern ireland", "britain", "u.k.", "uk"],
    "RS": ["serbia", "srbija", "serbien"],
    "MK": ["north macedonia", "macedonia", "makedonija", "nordmazedonien"],
    "BA": ["bosnia and herzegovina", "bosnia & herzegovina", "bosnia", "bih"],
    "ME": ["montenegro", "crna gora"],
    "AL": ["albania", "shqiperia"],
    "XK": ["kosovo"],
    "UA": ["ukraine", "ukraina"],
    "MD": ["moldova", "republic of moldova"],
    "TR": ["turkey", "turkiye", "turkei"],
}

_REGIONS = {
    "DE": ["bavaria", "bayern", "baden-wurttemberg", "baden wurttemberg", "nordrhein-westfalen", "north rhine-westphalia", "hessen", "hesse", "niedersachsen", "lower saxony", "sachsen", "saxony", "brandenburg", "rheinland-pfalz", "schleswig-holstein", "thuringen", "thuringia"],
    "NL": ["north holland", "noord-holland", "south holland", "zuid-holland", "noord-brabant", "north brabant", "utrecht province"],
    "FR": ["ile-de-france", "ile de france", "auvergne-rhone-alpes", "provence-alpes-cote d'azur", "occitanie", "nouvelle-aquitaine", "hauts-de-france", "grand est", "bretagne", "pays de la loire"],
    "ES": ["catalonia", "cataluna", "catalunya", "comunidad de madrid", "community of madrid", "andalusia", "andalucia", "basque country", "pais vasco", "comunitat valenciana"],
    "IT": ["lombardy", "lombardia", "lazio", "piedmont", "piemonte", "emilia-romagna", "veneto", "tuscany", "toscana", "campania"],
    "CH": ["canton of zurich", "kanton zurich", "vaud", "ticino", "aargau"],
    "PL": ["mazowieckie", "malopolskie", "dolnoslaskie", "pomorskie", "wielkopolskie", "masovian", "lesser poland", "lower silesian"],
    "AT": ["styria", "steiermark", "upper austria", "oberosterreich", "carinthia", "karnten", "tyrol", "tirol"],
    "GB": ["greater london"],
    "BE": ["flanders", "wallonia", "vlaanderen"],
    "RO": ["ilfov"],
}

_CITIES = {
    "AT": ["vienna", "wien", "graz", "linz", "salzburg", "innsbruck", "klagenfurt", "hagenberg", "villach", "st. polten", "sankt polten", "wels", "dornbirn", "leoben"],
    "BE": ["brussels", "bruxelles", "brussel", "antwerp", "antwerpen", "anvers", "ghent", "gent", "leuven", "louvain", "liege", "mechelen", "bruges", "brugge", "namur", "charleroi", "hasselt", "kortrijk", "zaventem", "diegem", "wavre", "mons"],
    "BG": ["sofia", "plovdiv", "varna", "burgas", "ruse"],
    "HR": ["zagreb", "split", "rijeka", "osijek", "zadar"],
    "CY": ["nicosia", "limassol", "larnaca", "paphos", "lefkosia"],
    "CZ": ["prague", "praha", "brno", "ostrava", "plzen", "pilsen", "olomouc", "liberec", "hradec kralove", "ceske budejovice", "zlin", "pardubice"],
    "DK": ["copenhagen", "kobenhavn", "aarhus", "arhus", "odense", "aalborg", "lyngby", "kongens lyngby", "billund", "ballerup", "kolding", "esbjerg"],
    "EE": ["tallinn", "tartu", "parnu"],
    "FI": ["helsinki", "espoo", "tampere", "oulu", "turku", "vantaa", "jyvaskyla", "lahti", "kuopio"],
    "FR": ["paris", "lyon", "marseille", "toulouse", "nice", "nantes", "strasbourg", "montpellier", "bordeaux", "lille", "rennes", "grenoble", "sophia antipolis", "sophia-antipolis", "valbonne", "biot", "la defense", "puteaux", "courbevoie", "issy-les-moulineaux", "boulogne-billancourt", "nanterre", "saint-denis", "rueil-malmaison", "levallois-perret", "neuilly-sur-seine", "massy", "palaiseau", "saclay", "velizy", "velizy-villacoublay", "elancourt", "guyancourt", "aix-en-provence", "brest", "toulon", "le mans", "angers", "tours", "dijon", "clermont-ferrand", "caen", "rouen", "nancy", "metz", "reims", "orleans", "limoges", "pau", "annecy", "sophia", "mougins", "meudon", "saint-cloud", "montrouge", "clichy", "cergy", "evry", "les ulis", "colombes", "gennevilliers", "suresnes", "chatillon", "malakoff", "vanves"],
    "DE": ["berlin", "munich", "munchen", "muenchen", "hamburg", "frankfurt", "frankfurt am main", "cologne", "koln", "koeln", "stuttgart", "dusseldorf", "duesseldorf", "dortmund", "essen", "leipzig", "bremen", "dresden", "hanover", "hannover", "nuremberg", "nurnberg", "nuernberg", "duisburg", "bochum", "wuppertal", "bielefeld", "bonn", "munster", "muenster", "karlsruhe", "mannheim", "augsburg", "wiesbaden", "gelsenkirchen", "monchengladbach", "braunschweig", "kiel", "aachen", "chemnitz", "halle", "magdeburg", "freiburg", "freiburg im breisgau", "krefeld", "lubeck", "mainz", "erfurt", "oberhausen", "rostock", "kassel", "hagen", "potsdam", "saarbrucken", "saarbruecken", "hamm", "ludwigshafen", "oldenburg", "mulheim", "osnabruck", "leverkusen", "heidelberg", "darmstadt", "solingen", "regensburg", "herne", "paderborn", "neuss", "ingolstadt", "offenbach", "furth", "wurzburg", "ulm", "heilbronn", "pforzheim", "wolfsburg", "gottingen", "goettingen", "bottrop", "reutlingen", "koblenz", "bremerhaven", "recklinghausen", "erlangen", "bergisch gladbach", "jena", "remscheid", "trier", "salzgitter", "moers", "siegen", "hildesheim", "cottbus", "kaiserslautern", "gutersloh", "schwerin", "witten", "gera", "iserlohn", "ludwigsburg", "esslingen", "zwickau", "duren", "ratingen", "flensburg", "lunen", "villingen-schwenningen", "konstanz", "marl", "worms", "velbert", "minden", "dessau", "neumunster", "norderstedt", "delmenhorst", "bamberg", "viersen", "marburg", "rheine", "gladbeck", "troisdorf", "wilhelmshaven", "bayreuth", "landshut", "passau", "rosenheim", "garching", "unterschleissheim", "unterschleißheim", "ottobrunn", "taufkirchen", "eschborn", "walldorf", "sindelfingen", "boblingen", "boeblingen", "gerlingen", "renningen", "weissach", "herzogenaurach", "friedrichshafen", "ravensburg", "tubingen", "tuebingen", "neckarsulm", "offenburg", "lahr", "baden-baden", "schweinfurt", "aschaffenburg", "fulda", "giessen", "wetzlar", "hanau", "ruesselsheim", "russelsheim", "bad homburg", "oberkochen", "jena", "weimar", "eisenach", "lingen", "emden", "aurich", "lueneburg", "luneburg", "celle", "stade", "itzehoe", "wedel", "pinneberg", "elmshorn", "ahrensburg", "dachau", "freising", "erding", "starnberg", "germering", "kempten", "memmingen", "kaufbeuren", "neu-ulm", "heidenheim", "aalen", "schwabisch hall", "crailsheim", "kunzelsau", "biberach", "weingarten", "lindau", "singen", "rottweil", "tuttlingen", "dortmund", "hamelin", "hameln", "peine", "gifhorn", "wolfenbuttel", "goslar", "nordhorn", "vechta", "cloppenburg", "leer", "papenburg", "bocholt", "borken", "coesfeld", "ahaus", "gronau", "steinfurt", "warendorf", "ahlen", "beckum", "lippstadt", "soest", "arnsberg", "meschede", "brilon", "olpe", "lennestadt", "gummersbach", "wipperfurth", "siegburg", "sankt augustin", "konigswinter", "euskirchen", "bruhl", "hurth", "kerpen", "frechen", "pulheim", "dormagen", "grevenbroich", "kaarst", "meerbusch", "hilden", "langenfeld", "monheim", "mettmann", "erkrath", "haan", "wesel", "dinslaken", "voerde", "kleve", "goch", "emmerich", "geldern", "kevelaer", "dulmen", "haltern", "dorsten"],
    "GR": ["athens", "athina", "thessaloniki", "patras", "heraklion", "piraeus", "marousi", "chalandri"],
    "HU": ["budapest", "debrecen", "szeged", "pecs", "gyor", "miskolc", "kecskemet", "szekesfehervar"],
    "IE": ["dublin", "cork", "galway", "limerick", "waterford", "athlone", "shannon", "dun laoghaire", "sandyford", "leixlip", "maynooth", "drogheda", "dundalk", "kilkenny", "sligo", "letterkenny", "tralee", "ennis", "carlow", "naas", "swords", "blanchardstown", "cherrywood", "ballsbridge"],
    "IT": ["rome", "roma", "milan", "milano", "turin", "torino", "naples", "napoli", "bologna", "florence", "firenze", "genoa", "genova", "venice", "venezia", "verona", "padua", "padova", "trieste", "bari", "palermo", "catania", "pisa", "trento", "bergamo", "brescia", "modena", "parma", "reggio emilia", "ancona", "perugia", "cagliari", "pavia", "lecce", "salerno", "ivrea", "vicenza", "treviso", "udine", "bolzano", "como", "monza", "varese", "lucca", "siena", "pescara", "cosenza", "messina", "sassari", "novara", "alessandria", "piacenza", "ferrara", "rimini", "ravenna", "cesena", "forli", "segrate", "assago", "sesto san giovanni", "vimercate", "agrate brianza", "pomezia", "frascati", "pozzuoli"],
    "LV": ["riga", "daugavpils", "jelgava"],
    "LT": ["vilnius", "kaunas", "klaipeda", "siauliai", "panevezys"],
    "LU": ["luxembourg city", "esch-sur-alzette", "belval", "kirchberg", "differdange", "bertrange", "strassen", "munsbach", "capellen", "contern", "leudelange"],
    "MT": ["valletta", "sliema", "st julian's", "st. julian's", "san giljan", "birkirkara", "mosta", "msida", "gzira", "ta' xbiex", "san gwann", "qormi"],
    "NL": ["amsterdam", "rotterdam", "the hague", "den haag", "'s-gravenhage", "utrecht", "eindhoven", "groningen", "tilburg", "almere", "breda", "nijmegen", "enschede", "haarlem", "arnhem", "zaandam", "amersfoort", "apeldoorn", "hoofddorp", "maastricht", "leiden", "dordrecht", "zoetermeer", "zwolle", "delft", "veldhoven", "schiphol", "amstelveen", "hilversum", "diemen", "den bosch", "'s-hertogenbosch", "s-hertogenbosch", "deventer", "helmond", "venlo", "heerlen", "sittard", "geleen", "leeuwarden", "alkmaar", "hengelo", "capelle aan den ijssel", "rijswijk", "nieuwegein", "houten", "zeist", "wageningen", "ede", "harderwijk", "naarden", "best", "vlaardingen", "schiedam", "barendrecht", "noordwijk", "harlingen", "gorinchem", "katwijk", "den helder", "badhoevedorp", "badhoevedorp"],
    "PL": ["warsaw", "warszawa", "krakow", "cracow", "wroclaw", "gdansk", "gdynia", "sopot", "poznan", "lodz", "katowice", "lublin", "szczecin", "bydgoszcz", "bialystok", "rzeszow", "torun", "gliwice", "kielce", "olsztyn", "opole", "zielona gora", "bielsko-biala", "czestochowa", "radom", "sosnowiec", "tychy", "rybnik", "zabrze", "chorzow", "legnica", "tarnow", "plock", "elblag", "koszalin", "kalisz", "nowy sacz"],
    "PT": ["lisbon", "lisboa", "porto", "oporto", "braga", "coimbra", "aveiro", "faro", "funchal", "setubal", "guimaraes", "leiria", "viseu", "evora", "matosinhos", "maia", "vila nova de gaia", "oeiras", "cascais", "sintra", "amadora", "almada", "covilha", "fundao", "castelo branco", "porto salvo", "carnaxide"],
    "RO": ["bucharest", "bucuresti", "cluj-napoca", "cluj napoca", "cluj", "iasi", "timisoara", "brasov", "constanta", "craiova", "sibiu", "oradea", "galati", "ploiesti", "arad", "pitesti", "bacau", "targu mures", "baia mare", "buzau", "suceava", "satu mare", "alba iulia", "otopeni", "voluntari"],
    "SK": ["bratislava", "kosice", "zilina", "presov", "banska bystrica", "nitra", "trnava", "trencin", "martin"],
    "SI": ["ljubljana", "maribor", "celje", "kranj", "koper", "nova gorica"],
    "ES": ["madrid", "barcelona", "valencia", "seville", "sevilla", "malaga", "zaragoza", "bilbao", "palma", "palma de mallorca", "las palmas", "alicante", "murcia", "valladolid", "vigo", "gijon", "oviedo", "a coruna", "la coruna", "granada", "san sebastian", "donostia", "pamplona", "santander", "salamanca", "cordoba", "cadiz", "tarragona", "girona", "lleida", "castellon", "vitoria", "vitoria-gasteiz", "logrono", "badajoz", "caceres", "huelva", "jaen", "almeria", "leon", "burgos", "santiago de compostela", "elche", "cartagena", "sant cugat", "sant cugat del valles", "terrassa", "sabadell", "badalona", "l'hospitalet", "hospitalet de llobregat", "getafe", "alcobendas", "las rozas", "pozuelo de alarcon", "tres cantos", "leganes", "mostoles", "alcala de henares", "boadilla del monte", "majadahonda", "san sebastian de los reyes", "rivas-vaciamadrid", "torrejon de ardoz", "santa cruz de tenerife", "tenerife"],
    "SE": ["stockholm", "gothenburg", "goteborg", "malmo", "uppsala", "linkoping", "lund", "vasteras", "orebro", "norrkoping", "helsingborg", "jonkoping", "umea", "kista", "solna", "sundbyberg", "lulea", "karlstad", "sundsvall", "gavle", "boras", "sodertalje", "vaxjo", "halmstad", "eskilstuna", "karlskrona", "ostersund", "trollhattan", "skovde"],
    "IS": ["reykjavik", "kopavogur", "hafnarfjordur", "akureyri"],
    "LI": ["vaduz", "schaan"],
    "NO": ["oslo", "bergen", "trondheim", "stavanger", "drammen", "fredrikstad", "kristiansand", "tromso", "sandnes", "asker", "baerum", "fornebu", "lysaker", "lillestrom", "kongsberg", "horten", "sandvika", "alesund", "bodo", "haugesund", "moss", "skien", "porsgrunn", "hamar", "gjovik", "molde", "arendal", "tonsberg", "sarpsborg", "larvik", "halden", "harstad", "narvik"],
    "CH": ["zurich", "zuerich", "geneva", "geneve", "genf", "ginevra", "basel", "bale", "bern", "berne", "lausanne", "lucerne", "luzern", "lugano", "winterthur", "st. gallen", "st gallen", "sankt gallen", "biel", "bienne", "thun", "zug", "baar", "schlieren", "rotkreuz", "baden", "aarau", "fribourg", "freiburg im uchtland", "neuchatel", "sion", "chur", "schaffhausen", "rapperswil", "dubendorf", "kloten", "opfikon", "wallisellen", "dietikon", "uster", "horgen", "adliswil", "wadenswil", "cham", "steinhausen", "allschwil", "pratteln", "muttenz", "liestal", "olten", "solothurn", "burgdorf", "nyon", "vevey", "montreux", "renens", "ecublens", "yverdon", "yverdon-les-bains", "martigny", "monthey", "bellinzona", "locarno", "mendrisio", "manno", "kriens", "emmen", "horw", "wil", "gossau", "frauenfeld", "kreuzlingen", "romanshorn", "arbon", "buchs", "widnau", "heerbrugg", "landquart", "davos", "visp", "brig", "villigen", "wurenlingen", "meyrin", "plan-les-ouates", "carouge", "lancy", "vernier", "onex", "thalwil", "kusnacht", "meilen", "stafa", "pfaffikon", "regensdorf", "bulach", "embrach", "glattbrugg", "hinwil", "wetzikon", "bubikon"],
    "GB": ["london", "manchester", "edinburgh", "glasgow", "birmingham", "bristol", "leeds", "liverpool", "cambridge", "oxford", "belfast", "cardiff", "newcastle", "newcastle upon tyne", "sheffield", "nottingham", "leicester", "reading", "southampton", "brighton", "coventry", "bath", "york", "exeter", "aberdeen", "dundee", "swansea", "milton keynes", "guildford", "basingstoke", "slough", "bracknell", "farnborough", "crawley", "chelmsford", "colchester", "norwich", "ipswich", "peterborough", "luton", "watford", "stevenage", "st albans", "hemel hempstead", "maidenhead", "woking", "staines", "uxbridge", "harlow", "croydon", "canary wharf", "stratford", "kingston upon thames", "richmond upon thames", "warrington", "chester", "stockport", "salford", "bolton", "preston", "lancaster", "derby", "stoke-on-trent", "wolverhampton", "telford", "worcester", "gloucester", "cheltenham", "swindon", "plymouth", "bournemouth", "poole", "portsmouth", "winchester", "salisbury", "taunton", "hull", "bradford", "huddersfield", "harrogate", "durham", "sunderland", "middlesbrough", "darlington", "carlisle", "inverness", "stirling", "livingston", "dunfermline", "derry", "lisburn", "newport", "wrexham", "bangor", "tewkesbury", "malvern", "bedford", "northampton", "lincoln", "solihull", "leamington spa", "warwick", "rugby", "loughborough", "harwell", "didcot", "abingdon"],
    "RS": ["belgrade", "beograd", "novi sad", "nis", "kragujevac", "subotica", "cacak"],
    "MK": ["skopje", "bitola", "ohrid", "kumanovo", "prilep", "tetovo", "veles", "stip", "strumica"],
    "BA": ["sarajevo", "banja luka", "mostar", "tuzla", "zenica"],
    "ME": ["podgorica", "budva", "niksic", "herceg novi", "bar"],
    "AL": ["tirana", "tirane", "durres", "vlore", "shkoder"],
    "XK": ["pristina", "prishtina", "prizren"],
    "UA": ["kyiv", "kiev", "lviv", "kharkiv", "odesa", "odessa", "dnipro", "zaporizhzhia", "vinnytsia", "ivano-frankivsk", "ternopil", "chernivtsi", "uzhhorod", "lutsk", "rivne", "khmelnytskyi", "poltava", "chernihiv", "sumy", "zhytomyr", "mykolaiv", "kherson", "cherkasy", "kropyvnytskyi"],
    "MD": ["chisinau", "chisinau", "balti"],
    "TR": ["istanbul", "ankara", "izmir", "bursa", "antalya", "kocaeli", "gebze", "eskisehir", "konya", "adana", "kayseri", "gaziantep", "mersin", "trabzon", "samsun", "denizli", "sakarya"],
}

_NON_EUROPE = [
    "united states", "usa", "u.s.a", "u.s.", "america", "canada", "india", "china", "japan", "singapore",
    "australia", "brazil", "brasil", "mexico", "israel", "korea", "taiwan", "hong kong", "philippines",
    "vietnam", "egypt", "south africa", "united arab emirates", "uae", "dubai", "abu dhabi", "saudi arabia",
    "qatar", "argentina", "chile", "colombia", "new zealand", "malaysia", "indonesia", "thailand", "pakistan",
    "nigeria", "kenya", "morocco", "tunisia", "costa rica", "peru", "uruguay", "bangladesh", "sri lanka",
    "russia", "belarus", "kazakhstan", "armenia", "georgia", "azerbaijan", "uzbekistan", "jordan", "lebanon",
    "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai", "gurgaon", "gurugram", "noida",
    "new delhi", "delhi", "beijing", "shanghai", "shenzhen", "hangzhou", "tokyo", "osaka", "seoul", "taipei",
    "hsinchu", "sydney", "melbourne", "toronto", "vancouver", "montreal", "ottawa", "waterloo, on",
    "sao paulo", "tel aviv", "haifa", "herzliya", "manila", "ho chi minh", "hanoi", "kuala lumpur",
    "jakarta", "bangkok", "cairo", "johannesburg", "cape town", "lagos", "nairobi", "buenos aires",
    "santiago, chile", "bogota", "lima", "guadalajara", "monterrey", "penang", "san francisco", "new york",
    "seattle", "boston", "austin", "chicago", "los angeles", "mountain view", "palo alto", "sunnyvale",
    "san jose", "redmond", "atlanta", "denver", "san diego", "pittsburgh", "dallas", "houston", "washington, d",
    "philadelphia", "miami", "salt lake", "raleigh", "detroit", "minneapolis", "phoenix", "portland, or",
]

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND",
    "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
CA_PROVINCES = {"ON", "BC", "QC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"}

_EUROPE_REMOTE = re.compile(
    r"\b(emea|europe|european union|european economic area|eea|eu remote|remote eu|remote \(eu\)|remote - eu|europa|cet timezone|cet time zone)\b"
)
_EU_TOKEN = re.compile(r"(^|[\s,(\-/])EU($|[\s,)\-/])")


def fold(text: str) -> str:
    text = (text or "").replace("ß", "ss").replace("ł", "l").replace("Ł", "L").replace("ø", "o").replace("Ø", "O").replace("æ", "ae").replace("đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def _compile(table: dict[str, list[str]]) -> list[tuple[re.Pattern, str]]:
    pairs = []
    for code, names in table.items():
        for name in names:
            key = fold(name)
            pairs.append((key, code))
    pairs.sort(key=lambda p: -len(p[0]))
    return [(re.compile(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])"), c) for k, c in pairs]


_COUNTRY_PATTERNS = _compile(_COUNTRY_ALIASES)
_REGION_PATTERNS = _compile(_REGIONS)
_RISKY_CITIES = {"best", "martin", "bar", "wil", "leer", "ede", "moss", "hamm", "marl", "leon", "baden", "cham", "biel", "buchs", "emmen", "halle", "mons", "bath", "york", "reading", "derby", "newport", "lincoln", "stratford", "richmond upon thames", "nis", "split", "martigny", "horw", "kriens", "olpe", "goch", "singen", "lahr", "celle", "stade", "lund", "boras", "moers", "witten", "worms", "aurich", "emden", "peine", "soest", "haan", "wesel", "kleve", "borken", "rheine", "minden", "viersen", "gronau"}
_CITY_PATTERNS = _compile({c: [n for n in names if fold(n) not in _RISKY_CITIES] for c, names in _CITIES.items()})
_FALSE_FRIENDS = [
    (re.compile(r"(?<![a-z])new south wales(?![a-z])"), " australia "),
    (re.compile(r"(?<![a-z])(rhode island|new england|new jersey|new hampshire|new york|new mexico|new hampshire|west virginia)(?![a-z])"), " usa "),
]
_CITY_EXACT = {fold(name): code for code, names in _CITIES.items() for name in names}
_NON_EU_PATTERNS = [re.compile(r"(?<![a-z])" + re.escape(fold(n)) + r"(?![a-z])") for n in sorted(_NON_EUROPE, key=len, reverse=True)]
_TRAILING_CODE = re.compile(r",\s*([A-Z]{2})\s*(?:,|$|\s*\+|\s*\()")
_US_TOKEN = re.compile(r"(^|[\s,(\-/])(US|USA|U\.S\.)($|[\s,)\-/])")

ISO_ALIASES = {"UK": "GB", "EL": "GR"}


def _scan(patterns: list[tuple[re.Pattern, str]], text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for pat, code in patterns:
        for m in pat.finditer(text):
            span = m.span()
            if any(not (span[1] <= a or span[0] >= b) for a, b in taken):
                continue
            taken.append(span)
            found.append((span[0], code))
    found.sort()
    return found


def _uniq(codes) -> list[str]:
    out: list[str] = []
    for c in codes:
        if c not in out:
            out.append(c)
    return out


def _chunk_countries(raw: str, allow: set[str]) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    n = fold(raw)
    n = re.sub(r"\s*\+\s*\d+\s*(more)?\s*$", "", n)
    for pat, repl in _FALSE_FRIENDS:
        n = pat.sub(repl, n)

    countries = [c for _, c in _scan(_COUNTRY_PATTERNS, n)]
    if "GB" in countries and "IE" in countries and "northern ireland" in n and "republic of ireland" not in n:
        countries = [c for c in countries if c != "IE" or n.count("ireland") > 1]
    if countries:
        return _uniq(c for c in countries if c in allow)

    if _US_TOKEN.search(raw) or any(p.search(n) for p in _NON_EU_PATTERNS):
        return []

    trailing = _TRAILING_CODE.search(raw + ",")
    code = trailing.group(1) if trailing else None
    if code:
        code = ISO_ALIASES.get(code, code)

    regions = [c for _, c in _scan(_REGION_PATTERNS, n)]
    n_cities = n
    for pat, _ in _REGION_PATTERNS:
        n_cities = pat.sub(" ", n_cities)

    first_seg = fold(raw.split(",")[0])
    first_seg = re.sub(r"\s*\+\s*\d+\s*(more)?\s*$", "", first_seg)
    city_code = _CITY_EXACT.get(first_seg)
    cities = [c for _, c in _scan(_CITY_PATTERNS, n_cities)]
    if city_code is not None and city_code not in cities:
        cities.insert(0, city_code)
    if city_code is None and cities:
        city_code = cities[0]

    if code:
        if code in CA_PROVINCES and code not in EUROPE_CODES:
            return []
        if code in US_STATES:
            if city_code == code and code in allow:
                return [code]
            return []
        if code in EUROPE_CODES:
            return [code] if code in allow else []

    if cities:
        return _uniq(c for c in cities if c in allow)

    if regions:
        return _uniq(c for c in regions if c in allow)

    if _EUROPE_REMOTE.search(n) or _EU_TOKEN.search(raw):
        return ["EU"]
    return []


_SPLIT = re.compile(r";|\||\n|•|\s/\s|\s+or\s+|\s+and\s+(?=[A-Z])|\s+&\s+(?=[A-Z])")


def europe_countries(text: str, include_tr: bool = False) -> list[str]:
    if not text:
        return []
    allow = set(EUROPE_CODES) | {"EU"}
    if not include_tr:
        allow.discard("TR")
    out: list[str] = []
    for chunk in _SPLIT.split(text):
        for code in _chunk_countries(chunk, allow):
            if code not in out:
                out.append(code)
    return out


def europe_country(text: str, include_tr: bool = False) -> str | None:
    codes = europe_countries(text, include_tr)
    return codes[0] if codes else None


def countries_from_names(text: str, include_tr: bool = True) -> list[str]:
    out: list[str] = []
    for part in re.split(r",|;|/", text or ""):
        part = part.strip()
        if not part:
            continue
        up = part.upper()
        if up in ISO_ALIASES:
            out.append(ISO_ALIASES[up])
            continue
        if len(up) == 2 and up in EUROPE_CODES:
            out.append(up)
            continue
        codes = europe_countries(part, include_tr=include_tr)
        out.extend(c for c in codes if c not in out)
    return _uniq(out)


def clean_locations(locs: list[str]) -> str:
    items = []
    for l in locs:
        l = re.sub(r"\s+", " ", (l or "").strip())
        if l and l not in items:
            items.append(l)
    keys = [fold(x) for x in items]
    keep = []
    for i, (item, key) in enumerate(zip(items, keys)):
        tokens = set(re.split(r"[,\s/()-]+", key)) - {""}
        dominated = False
        for j, other in enumerate(keys):
            if i == j:
                continue
            other_tokens = set(re.split(r"[,\s/()-]+", other)) - {""}
            if not tokens or not tokens <= other_tokens:
                continue
            if tokens < other_tokens or j < i:
                dominated = True
                break
        if not dominated:
            keep.append(item)
    return "; ".join(keep)
