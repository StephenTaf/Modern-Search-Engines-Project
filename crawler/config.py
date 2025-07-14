"""Configuration settings for the Tübingen crawler."""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CrawlerConfig:
    """Configuration settings for the crawler."""
    
    # HTTP Settings
    headers: Optional[Dict[str, str]] = None
    timeout: int = 5
    allow_redirects: bool = False
    
    # Device Verification Settings
    handle_device_verification: bool = True
    max_verification_retries: int = 3
    verification_retry_delay: float = 2.0
    simulate_human_behavior: bool = True
    use_session_persistence: bool = True
    
    # Cloudflare Protection Settings
    use_cloudscraper_fallback: bool = True
    cloudscraper_timeout: int = 15
    cloudscraper_delay: float = 2.0
    cloudscraper_browser: str = "chrome"
    cloudscraper_platform: str = "darwin"  # macOS
    
    # Rate Limiting
    respect_rate_limits: bool = True
    default_rate_limit_wait: int = 60
    
    # Proxy Settings
    use_proxy: bool = False
    proxy_url: Optional[str] = None  # Format: "socks5://user:pass@host:port" or "http://user:pass@host:port"
    proxy_auth: Optional[Dict[str, str]] = None  # Alternative: {"username": "user", "password": "pass"}
    proxy_timeout: int = 30
    
    # Database Settings
    db_path: str = "crawler.db"
    cache_size_threshold: int = 20000
    
    # Crawling Settings
    max_pages_per_batch: int = 100
    delay_between_batches: int = 100
    
    # Multiprocessing Settings
    enable_multiprocessing: bool = False
    max_workers: int = 4
    urls_per_worker_batch: int = 20  # Reduced from 50 to 20 for faster interruption
    domain_rotation_delay: float = 0.1  # Reduced from 5.0 to 0.1 seconds
    worker_coordination_delay: float = 0.2  # Reduced from 1.0 to 0.2 seconds
    shared_domain_delays: bool = True  # Share domain delays across processes
    
    # Scoring Settings
    utema_beta: float = 1/5
    
    # Output Settings
    csv_export_enabled: bool = True
    csv_filename: str = "crawled_urls.csv"
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "DNT": "1"
            }


# Default seed URLs for Tübingen crawling
DEFAULT_SEED_URLS = [
 'https://uni-tuebingen.de/en/',
 'https://www.medizin.uni-tuebingen.de/en-de/startseite',
 'https://www.tuebingen.mpg.de/en',
 'https://tuebingen.ai/',
 'https://tuebingenresearchcampus.com/',
 'https://www.hih-tuebingen.de/en/',
 'https://www.dzif.de/en/partner-sites/tubingen',
 'https://cyber-valley.de/en',
 'https://www.tuebingen.de/',
 'https://www.swtue.de/en',
 'https://www.tripadvisor.co.uk/Tourism-g198539-Tubingen_Baden_Wurttemberg-Vacations.html',
 'https://www.tuebus.de/en/index.html',
 'https://en.wikivoyage.org/wiki/T%C3%BCbingen',
 'https://www.my-stuwe.de/en/housing/halls-of-residence-tuebingen/',
 'https://tuenews.de/en/latest-news-english/',
 'https://www.thelocal.de/tag/tubingen/',
 'https://www.stadtmuseum-tuebingen.de/english/',
 'https://www.dai-tuebingen.de/en/welcome-to-the-german-american-institute-tubingen.html',
 'https://www.my-stuwe.de/en/',
 'https://kunsthalle-tuebingen.de/en/current-exhibition/',
 'https://www.kks-netzwerk.de/en/network/about-us/members/translate-to-english-tuebingen/',
 'https://www.swtue.de/en/index.html?srsltid=AfmBOopEWoN9QWLnDe-5uRXZioAJRE6_dCYIodBzFpkzjmrvKq-8b02M',
 'https://en.wikipedia.org/wiki/T%C3%BCbingen',
 'https://www.tuebingen.mpg.de/en',
 'https://www.germany.travel/en/cities-culture/tuebingen.html',
 'https://www.topuniversities.com/universities/eberhard-karls-universitat-tubingen',
 'https://www.getyourguide.com/tubingen-l150729/',
 'https://www.ostrichtrails.com/europe/germany/tubingen-walking-tour/',
 'https://www.tripadvisor.com/Restaurants-g198539-Tubingen_Baden_Wurttemberg.html',
 'https://www.reddit.com/r/Tuebingen/comments/1iscxbg/wo_kann_man_hier_gut_essen/?tl=en',
 'https://wanderlog.com/list/geoCategory/199488/where-to-eat-best-restaurants-in-tubingen',
 'https://rausgegangen.de/en/tubingen/category/food-and-drinks/',
 'https://historicgermany.travel/historic-germany/tubingen/',
 'https://www.daad.de/en/studying-in-germany/universities/all-degree-programmes/detail/eberhard-karls-university-tuebingen-history-w18730/?hec-id=w18730',
 'https://www.geschichtswerkstatt-tuebingen.de/en/projects/history-trail-to-national-socialism',
 'https://visit-tubingen.co.uk/history-of-tubingen-from-pre-history-to-the-present/',
 'https://www.britannica.com/place/Tubingen-Germany',
 'https://www.stuttgartcitizen.com/lifestyle/tubingen-offers-history-education-old-world-charm/',
 'https://www.tripadvisor.com/Attraction_Review-g198539-d12498209-Reviews-Historische_Altstadt_Tubingen-Tubingen_Baden_Wurttemberg.html',
 'https://keydocuments.net/place/tgn/7004426',
 'https://www.reddit.com/r/Tuebingen/comments/10mk9fw/how_is_tuebingen/',
 'https://placesofgermany.de/en/places/tubingen-old-town/',
 'https://medium.com/german-city-profiles/t%C3%BCbingen-city-of-poets-and-thinkers-d9efb311c1b',
 'https://en.wikivoyage.org/wiki/T%C3%BCbingen',
 'https://one-million-places.com/en/germany/tuebingen-tips-top-sights',
 'https://www.mygermanyvacation.com/best-things-to-do-and-see-in-tubingen-germany/',
 'https://civis.eu/en/discover-civis/the-civis-alliance/eberhard-karls-universitat-tubingen',
 'https://pickingupthetabb.wordpress.com/2023/11/11/the-university-city-of-tubingen-germany/',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/mobility/by-bike',
 'https://www.outdooractive.com/en/cycle-routes/tuebingen/cycling-in-tuebingen/1432906/',
 'https://www.excelsior-bikes.com/en/magazine/one-day-in-tuebingen-discover-sights-cafes-by-bike/',
 'https://www.sterlingpresser.com/bicycle-station/',
 'https://www.blue-tomato.com/en-GB/shop/tuebingen/?srsltid=AfmBOooZpV6qn2gqHPQ1Kmh-1NIu4bd7smyyh2X-lZ8Ou35uW1N_-11M',
 'https://peeces.de/en/blogs/news/tubingen-vintage-store-guide?srsltid=AfmBOoohmbFijqxpIBJ52bgzU0q681bQuffaoR-mbzv2-9w83yEFMftL',
 'https://eu.dookan.com/blogs/germany/best-indian-grocery-store-in-tubingen-germany?srsltid=AfmBOooOocRPA79EUFvlate3ujWBZHXRlydqNr0Y44wNKb2gIyAR4muO',
 'https://www.thelabelfinder.com/t%C3%BCbingen/shops/DE/2820860',
 'https://velvetescape.com/things-to-do-in-tubingen/',
 'https://visit-tubingen.co.uk/category/things-to-do-in-tubingen/',
 'https://www.outdooractive.com/en/places-to-eat-and-drink/tuebingen/eat-and-drink-in-tuebingen/21873363/',
 'https://www.wurstkueche.com/en/drinks/',
 'https://www.lieferando.de/en/order-drinks-tuebingen',
 'https://www.excelsior-bikes.com/en/magazine/one-day-in-tuebingen-discover-sights-cafes-by-bike/',
 'https://wanderlog.com/plan/lyeoggallhegbmfq',
 'https://www.trivago.de/en-US/lm/hotels-t%C3%BCbingen-germany?search=200-1452;dr-20250803-20250804',
 'https://www.mygermanuniversity.com/studyfinder?p=1&pp=20&sort=featured&dir=ASC&cty=144',
 'https://tuebingen.city-map.de/00000001',
 'https://miz.org/en/musical-life/institutions/music-schools/tuebingen',
 'https://www.summerschoolsineurope.eu/destination/tubingen-international-european-studies-t-ies/',
 'https://www.christianchurch-tuebingen.com/',
 'https://www.esg-tuebingen.de/churchatsix',
 'https://www.opentable.com/region/de/baden-wurttemberg/tubingen-restaurants/',
 'https://uk.hotels.com/de374521/hotels-tuebingen-germany/',
 'https://www.orbitz.com/Tuebingen-Hotels.d181220.Travel-Guide-Hotels',
 'https://guide.michelin.com/en/de/baden-wurttemberg/tbingen/restaurants?sort=distance',
 'https://restaurantguru.com/Tubingen',
 'https://www.lieferando.de/en/delivery/food/tuebingen-72074',
 'https://www.findmeglutenfree.com/de/tubingen',
 'https://www.happycow.net/europe/germany/tubingen/',
 'https://mari-tuebingen.de/mari-tuebingen-en/',
 'https://cityseeker.com/tuebingen-de',
 'https://www.krone-tuebingen.de/en/',
 'https://www.thelabelfinder.com/t%C3%BCbingen/shops/DE/2820860',
 'https://www.petitfute.co.uk/v48133-tubingen/',
 'https://commons.wikimedia.org/wiki/Category:Shops_in_T%C3%BCbingen',
 'https://www.badurach-tourismus.de/en/poi/detail/tuebingen-71f22a53f0',
 'https://www.cybo.com/DE/t%C3%BCbingen/clothing-stores/',
 'https://www.finde.in/tuebingen?lang=en',
 'https://theculturetrip.com/europe/germany/articles/the-best-day-trips-from-tubingen-germany',
 'https://www.expatrio.com/about-germany/eberhard-karls-universitat-tubingen',
 'https://erasmusu.com/en/erasmus-tubingen',
 'https://www.engelvoelkers.com/de/en/properties/res/sale/real-estate/baden-wuerttemberg/tuebingen',
 'https://rausgegangen.de/en/tubingen/category/market/?lat=48.5236164&lng=9.0535531&city=tubingen&geospatial_query_type=CITY',
 'https://mindtrip.ai/attraction/tubingen-baden-wurttemberg/market-square-marktplatz/at-UCkSyNao',
 'https://www.neckartalradweg-bw.de/en/poi/detail/marketplace-tuebingen-9f9bf48077',
 'https://www.allgemeinmedizin-tuebingen.de/english-information',
 'https://www.doctena.de/en/general-practitioner-gp/tubingen',
 'https://www.leading-medicine-guide.com/en/medical-experts/university-hospital-tubingen-tuebingen',
 'https://bookinghealth.com/university-hospital-tuebingen/departments/113941-department-of-gynecology--mammology-and-obstetrics.html',
 'https://doclandmed.com/en/germany/clinic/university-hospital-of-tubingen',
 'https://www.doctolib.de/allgemeinmedizin/tuebingen',
 'https://airomedical.com/doctors/country=germany/city=tubingen',
 'https://www.commerzbank.de/filialen/en/T%C3%BCbingen',
 'https://deutsche.banklocationmaps.com/en/atm/954011-deutsche-atm-schleifmuhleweg-36',
 'https://www.iqair.com/germany/baden-wuerttemberg/tubingen?srsltid=AfmBOop0FexAS1Dh9421to0IAiFqdJBPFaSL7GLuCfZjVYvRTMBOxNyK',
 'https://aqicn.org/city/germany/badenwurttemberg/tubingen/',
 'https://en.climate-data.org/europe/germany/baden-wuerttemberg/tuebingen-22712/',
 'https://weather-and-climate.com/average-monthly-Rainfall-Temperature-Sunshine,tubingen-baden-wurttemberg-de,Germany',
 'https://www.wg-gesucht.de/en/wg-zimmer-in-Tuebingen.127.0.1.0.html',
 'https://www.airbnb.com/rooms/1297116546355903149?source_impression_id=p3_1752201611_P3zji2fDyb2L-X28',
 'https://www.ubereats.com/de-en/city/t%C3%BCbingen-bw?srsltid=AfmBOopb8JvaU-6V2WsSWibSd3gGVn9rttu4jadOEg_Xd6QT5KkGEquG',
 'https://www.pizzeria-dagiovanni.de/en/menu',
 'https://www.onegreenplanet.org/vegan-food/tubingen-the-european-eco-friendly-vegan-dream-city/',
 'https://www.wheree.com/g21321-Tubingen',
 'https://www.element-i.de/en/child-care-centres/die-tueftler/',
 'https://www.kinderhaus-tuebingen.de/english-version/',
 'https://www.dai-tuebingen.de/en/welcome-to-the-german-american-institute-tubingen.html',
 'https://vostel.de/en/volunteering/organisations/1641_Bahnhofsmission-Tuebingen',
 'https://www.komoot.com/guide/881/hiking-around-landkreis-tuebingen',
 'https://www.komoot.com/guide/3606931/easy-hikes-around-landkreis-tuebingen',
 'https://rausgegangen.de/en/tubingen/category/concerts-and-music/',
 'https://www.bandsintown.com/c/tuebingen-germany',
 'https://www.eventim.de/en/cityd/tuebingen-328/konzerte-1/?srsltid=AfmBOoqiXN3SEcHQgHTA-jYYRHfwgrM5HzmnNYV7oxTLtVY9Irkjv-X3',
 'https://www.jissen.ac.jp/about/library_mate/71_01.html',
 'https://ghg-tuebingen.de/2024/06/05/electoral-program-2024/',
 'https://wundertax.de/en/tax-offices/2886_tuebingen/',
 'https://www.hws.de/en/locations/hws-tuebingen-tax-consulting-management-consulting',
 'https://www.petbacker.com/s/dog-walking/t%C3%BCbingen--baden~w%C3%BCrttemberg--germany',
 'https://www.swabianalb.info/cities/tuebingen#/article/df9223e2-70e5-4ee9-b3f2-cd2355ab8551',
 'https://www.naldoland.de/en/naldoland/ziel/26/',
 'https://www.ksk-tuebingen.de/en/home.html?n=true&stref=logo',
 'https://veganfamilyadventures.com/15-best-things-to-do-in-tubingen-germany/',
 'https://forbetterscience.com/2024/04/17/gardening-goats-and-external-papermills-in-tubingen/',
 'https://www.the-studio-tuebingen.de/',
 'https://en.parkopedia.de/parking/tuebingen/?arriving=202507112000&leaving=202507112200',
 'https://en.parkopedia.com/parking/t%C3%BCbingen/?arriving=202507111900&leaving=202507112100',
 'https://www.bikemap.net/en/l/2820860/',
 'https://www.alltrails.com/germany/baden-wurttemberg/tubingen',
 'https://www.bongoroots.de/',
 'https://black-academy.org/black-history-month-2025-in-tubingen/',
 'https://www.iwm-tuebingen.de/www/en/index.html',
 'https://cyber-valley.de/en',
 'https://is.mpg.de/en',
 'https://www.stadtmuseum-tuebingen.de/english/',
 'https://www.kloster-bebenhausen.de/en',
 'https://www.kunsthalle-tuebingen.de/en/',
 'https://guidetoeurope.com/germany/destinations/tubingen',
 'https://www.mygermanyvacation.com/best-things-to-do-and-see-in-tubingen-germany/',
 'https://www.expatrio.com/about-germany/eberhard-karls-universitat-tubingen',
 'https://bookinghealth.com/university-hospital-tuebingen/departments',
 'https://velomesto.com/en/de-tuebingen-baden-wuerttemberg/shop/',
 'https://www.radparken-tuebingen.de/en/',
 'https://www.ternbicycles.com/en/dealers/301742',
 'https://www.bosch-ebike.com/en/dealers/tubingen-98',
 'https://www.europcar.com/en-us/places/car-rental-germany/tuebingen/tuebingen',
 'https://www.kayak.com/Cheap-Tuebingen-Car-Rentals.33286.cars.ksp',
 'https://www.rentalcars.com/en/city/de/tubingen/',
 'https://integreat.app/tuebingen/en/mobility/vehicle-registration-office',
 'https://www.autoforum-tuebingen.com/',
 'https://www.ooyyo.com/germany/used-cars-for-sale/c=CDA31D7114D3854F111BFE6FBB1C1153DBA33C71/',
 'https://coparking.ch/en/Germany/car-repair-shop/6542',
 'https://sit-sis.de/en/language-journeys/leisure-and-cultural-programm',
 'https://www.fahrschule-123.de/en/driving-schools/tuebingen/#/?d=10',
 'https://www.fahrschule-123.de/en/driving-school/fahrschule-armbruster/',
 'https://ecstaticdance.org/dance/ecstatic-dance-tubingen/',
 'https://www.vhs-tuebingen.de/kurssuche/liste?knr=251-20908&orderby=ort&orderbyasc=1&browse=forward&knradd=251-20945',
 'https://students.tufts.edu/group/26/content/1081',
 'https://www.iwm-tuebingen.de/www/en/forschung/forschungsbereiche/AG8_Meurers/index.html',
 'https://www.myguide.de/en/cities/tuebingen/',
 'https://www.engie-deutschland.de/en/references/energy-saving-contracting-university-hospital-tubingen',
 'https://www.energate-messenger.com/news/244852/the-public-utility-stadtwerke-tuebingen-sets-itself-high-targets-for-the-expansion-of-renewables',
 'https://www.energate-messenger.com/news/241588/stadtwerke-tuebingen-largest-solar-park-in-the-region-under-construction',
 'https://www.machinelearningforscience.de/en/predicting-future-energy-supply/',
 'https://www.waterhardness.net/deutschland/baden-wuerttemberg/72070-tuebingen/72072-buehl.html',
 'https://integreat.app/tuebingen/en/ukraine/childcare-and-school-visit',
 'https://sit-sis.de/en/language-journeys/leisure-and-cultural-programm',
 'https://www.helpling.de/de_en/cleaner/tuebingen/',
 'https://oi-clean.de/housekeeping-service-in-tubingen/',
 'https://www.iwm-tuebingen.de/www/index.html',
 'https://www.bahnhof.de/en/tuebingen-hbf',
 'https://www.bahnhof.de/en/tuebingen-hbf',
 'https://bwz.uw.edu.pl/en/university-of-tubingen-summer-language-courses/',
 'https://www.mdpi.com/2071-1050/12/3/861',
 'https://www.mylanguageexchange.com/city/Tuebingen__Germany.asp',
 'https://www.dw.com/en/stone-age-art-in-germany-tells-of-our-ancestors-creativity/a-69841364',
 'https://www.visit-bw.com/en/article/tubingen/df9223e2-70e5-4ee9-b3f2-cd2355ab8551',
 'https://simple.wikipedia.org/wiki/T%C3%BCbingen',
 'https://www.tuebingen-info.de/',
 'https://www.tuebingen.de/108.html',
 'https://uni-tuebingen.de/en/international/study-in-tuebingen/degree-seeking-students/programs-and-modules-for-international-students/international-degree-programs/',
 'https://uni-tuebingen.de/en/research/',
 'https://uni-tuebingen.de/en/research/centers-and-institutes/',
 'https://uni-tuebingen.de/en/study/student-life/',
 'https://uni-tuebingen.de/en/international/welcome-center/social-events-leisure/calendar-of-events/',
 'https://uni-tuebingen.de/en/242932',
 'https://uni-tuebingen.de/en/study/steps-towards-employment/business-contacts/',
 'https://uni-tuebingen.de/en/279798',
 'https://uni-tuebingen.de/en/international/learning-languages/learn-german/international-summer-course/the-city-of-tuebingen/',
 'https://uni-tuebingen.de/fakultaeten/wirtschafts-und-sozialwissenschaftliche-fakultaet/international/study-in-tuebingen/student-life/',
 'https://uni-tuebingen.de/en/faculties/faculty-of-economics-and-social-sciences/subjects/school-of-business-and-economics/school-of-business-and-economics/career-and-alumni-service/alumni-services/friedrich-list-festival/',
 'https://simple.wikipedia.org/wiki/University_of_T%C3%BCbingen',
 'https://en.wikipedia.org/wiki/University_of_T%C3%BCbingen',
 'https://www.daad.de/en/studying-in-germany/universities/all-degree-programmes/detail/eberhard-karls-university-tuebingen-english-and-american-studies-g12816/?hec-id=g12816',
 'https://www.mygermanuniversity.com/cities/Tuebingen',
 'https://www.study-in-germany.com/en/germany/cities/tubingen/',
 'https://tuebingenresearchcampus.com',
 'https://tuebingenresearchcampus.com/en/tuebingen/paperwork/official-registration',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/mobility/beyond-tuebingen',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/family/life-with-kids',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/shopping',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/mobility/by-public-transport',
 'https://tuebingenresearchcampus.com/en/tuebingen/living-in-tuebingen/mobility',
 'https://tuebingenresearchcampus.com/en/tuebingen/general-information/local-infos',
 'https://tuebingenresearchcampus.com/en/campus/partner-institutions/ukt',
 'https://wirtschaftskoordination.de/en/partner/tuebingen-research-campus',
 'https://experts-medical.com/en/clinic/university-hospital-tubingen/',
 'https://bookinghealth.com/university-hospital-tuebingen',
 'https://treatmentingermany.de/hospital-details/university-hospital-tubingen',
 'https://www.qunomedical.com/en/university-hospital-tuebingen',
 'https://intermed-consult.com/en/tuebingen/',
 'https://airomedical.com/hospitals/university-hospital-tubingen',
 'https://www.hih-tuebingen.de/en/research',
 'https://www.unimuseum.uni-tuebingen.de/en/museum-at-hohentuebingen-castle/museum-ancient-cultures',
 'https://whichmuseum.com/place/tubingen-11296/art',
 'https://wanderlog.com/list/geoCategory/1610724/best-museums-in-tubingen',
 'https://www.dai-tuebingen.de/en/events.html',
 'https://www.krone-tuebingen.de/en/a-holiday-in-tuebingen/tuebingen-the-surrounding-area/',
 'https://www.visitacity.com/en/tubingen/attraction-by-type/all-attractions',
 'https://justinpluslauren.com/things-to-do-in-tubingen-germany/',
 'https://thespicyjourney.com/magical-things-to-do-in-tubingen-in-one-day-tuebingen-germany-travel-guide/',
 'https://globaltravelescapades.com/things-to-do-in-tubingen-germany/',
 'https://angiestravelroutes.com/en/12of12-tuebingen-sightseeing/',
 'https://www.wayfaringwithwagner.com/visiting-tuebingen-in-wintertime/',
 'https://mattbolch.com/2023/06/27/visit-to-tubingen-worth-the-travel-hassles/',
 'https://www.tuebingen-info.de/_Resources/Persistent/6abfd8b3603fd3ce865610bbd7412f10d63910a8/Tu%CC%88bingen_Magazin_2022_EN_screen.pdf',
 'https://www.tuebingen-info.de/_Resources/Persistent/5b64fd3ecc0c244207d301b60db28ba0e33a1a4a/Tour_of_the_city_2022.pdf',
 'https://www.tuebingen.de/Dateien/Broschuere_WillkommenInTuebingen_ENG.pdf',
 'https://www.tripadvisor.com/Attractions-g198539-Activities-Tubingen_Baden_Wurttemberg.html',
 'https://www.tripadvisor.com/Attractions-g198539-Activities-c49-Tubingen_Baden_Wurttemberg.html',
 'https://www.tripadvisor.com/Attractions-g198539-Activities-c26-Tubingen_Baden_Wurttemberg.html',
 'https://www.tripadvisor.com/Attraction_Review-g198539-d522578-Reviews-Market_Square-Tubingen_Baden_Wurttemberg.html',
 'https://www.tripadvisor.com/Restaurant_Review-g198539-d6872059-Reviews-Hotel_Restaurant_Meteora-Tubingen_Baden_Wurttemberg.html',
 'https://www.booking.com/hotel/de/restaurant-meteora.html',
 'https://www.booking.com/city/de/tubingen.html',
 'https://www.kayak.co.uk/Tuebingen-Hotels.33286.hotel.ksp',
 'https://www.xn--gasthof-grbele-fib.com/en',
 'https://www.outdooractive.com/mobile/en/hiking-trails/tuebingen/hiking-in-tuebingen/1432855/',
 'https://www.outdooractive.com/mobile/en/route/hiking-trail/swabian-alb/ascent-of-the-tuebingen-mountains-north-route/19748509/',
 'https://www.outdooractive.com/en/shoppings/tuebingen/shopping-in-tuebingen/21876964/',
 'https://www.komoot.com/highlight/4114462',
 'https://hiiker.app/trails/germany/tubingen/forest',
 'https://fruechtetrauf-bw.de/en/',
 'https://www.yelp.com/search?cflt=hiking&find_loc=T%C3%BCbingen%2C+Baden-W%C3%BCrttemberg',
 'https://www.yelp.com/search?cflt=amusementparks&find_loc=T%C3%BCbingen%2C+Baden-W%C3%BCrttemberg',
 'https://www.a2gov.org/parks-and-recreation/parks-and-places/tuebingen-park/',
 'https://www.my-stuwe.de/en/advice/tickets-for-students/',
 'https://uni-tuebingen.de/fakultaeten/mathematisch-naturwissenschaftliche-fakultaet/fachbereiche/interfakultaere-einrichtungen/theorie-und-geschichte-der-wissenschaften/hilbert-bernays-summer-school-on-logic-and-computation-2019/practical-information/travel-directions/',
 'https://www.studit-tuebingen.de/en/',
 'https://www.my-stuwe.de/en/housing/international-tutors/',
 'https://www.reddit.com/r/Tuebingen/comments/128pym1/new_to_germany_and_to_tubingen/',
 'https://www.thelabelfinder.com/t%C3%BCbingen/shopping-centers/DE/2820860',
 'https://www.thelabelfinder.com/t%C3%BCbingen/centres-commerciaux/CH/2820860',
 'https://cityseeker.com/tuebingen-de/shopping',
 'https://www.neckaralb.de/en/the-neckar-alb-economic-region/business-directory',
 'https://webcatalogue.wein.plus/gastronomy/weinhaus-schmid',
 'https://city-map.com/en/business-directory/region-tubingen-de',
 'https://city-map.com/en/business-directory/@48.5012317,9.0503129,13/',
 'https://www.bbc.com/travel/article/20220320-tbingen-europes-fiercely-vegan-fairy-tale-city',
 'https://www.thelocal.de/tag/tubingen',
 'https://tunewsinternational.com/category/region-english/',
 'https://tunewsinternational.com/category/news-in-english/',
 'https://tuenews.de/en/tubingen-events-at-a-glance/',
 'https://en.wikipedia.org/wiki/Schw%C3%A4bisches_Tagblatt',
 'https://ground.news/interest/tubingen',
 'https://integreat.app/tuebingen/en/news/tu-news',
 'https://rausgegangen.de/en/tubingen/',
 'https://www.eventbrite.com/d/germany--t%C3%BCbingen/english/?page=2',
 'https://movingtostuttgart.com/event/chocolart/',
 'https://historicgermany.travel/event/chocolart-international-chocolate-festival-2/',
 'https://www.dwih-saopaulo.org/en/event/academic-opportunities-in-tuebingen-tradition-and-innovation-edition-may-2025/'
 ]


# Common Tübingen-related terms for scoring
TUEBINGEN_TERMS = [
    "tübingen", "tuebingen", "university", "eberhard karls",
    "baden württemberg", "neckar", "swabia", "medieval",
    "student", "academic", "research", "campus", "altstadt",
    "old town", "castle", "schönbuch", "württemberg"
]

# Domain patterns to prioritize
PRIORITY_DOMAINS = [
    "uni-tuebingen.de",
    "tuebingen.de",
    "tuebingen.city",
    "tuebingen.mpg.de",
    "tuebingen.ai",
    "cyber-valley.de",
    "my-stuwe.de",
    "dai-tuebingen.de",
    "tuebingenresearchcampus.com",
    "hih-tuebingen.de"
]

# Domains to avoid
EXCLUDE_DOMAINS = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "youtube.com",
    "linkedin.com",
    "pinterest.com",
    "reddit.com",
    "whatsapp.com",
    "telegram.org",
    "tiktok.com",
    "snapchat.com",
    "discord.com",
    "twitch.tv",
    "amazon.com",
    "amazon.de",
    "ebay.com",
    "ebay.de",
    "booking.com",
    "expedia.com",
    "tripadvisor.com",
    "airbnb.com",
    "hotels.com",
    "kayak.com",
    "skyscanner.com",
    "momondo.com",
    "priceline.com",
    "orbitz.com",
    "travelocity.com",
    "cheapflights.com",
    "hotwire.com",
    "lastminute.com",
    "opodo.com",
    "gomio.com",
    "omio.com",
    "flixbus.com",
    "trainline.com",
    "bahn.de",
    "deutsche-bahn.com",
    "blablacar.com",
    "uber.com",
    "lyft.com",
    "mytaxi.com",
    "free-now.com",
    "bolt.eu",
    "via.com",
    "gett.com",
    "kapten.com",
    "cabify.com",
    "99.co",
    "grab.com",
    "ola.com",
    "didi.com",
    "careem.com",
    "yandex.com",
    "mail.ru",
    "vk.com",
    "ok.ru",
    "weibo.com",
    "wechat.com",
    "qq.com",
    "baidu.com",
    "sina.com",
    "163.com",
    "126.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "gmail.com",
    "aol.com",
    "icloud.com",
    "protonmail.com",
    "tutanota.com",
    "zoho.com",
    "fastmail.com",
    "yandex.ru",
    "rambler.ru",
    "bk.ru",
    "inbox.ru",
    "list.ru",
    "internet.ru"
]

# Database table definitions
DATABASE_SCHEMA = {
    "urlsDB": """
        CREATE TABLE IF NOT EXISTS urlsDB (
            url TEXT PRIMARY KEY,
            lastFetch TIMESTAMP,
            text TEXT,
            title TEXT,
            tueEngScore REAL,
            linkingDepth INTEGER,
            domainLinkingDepth INTEGER,
            parentUrl TEXT,
            statusCode INTEGER,
            contentType TEXT,
            lastModified TIMESTAMP,
            etag TEXT
        )
    """,
    
    "frontier": """
        CREATE TABLE IF NOT EXISTS frontier (
            url TEXT PRIMARY KEY,
            schedule REAL,
            delay REAL,
            priority REAL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "disallowed": """
        CREATE TABLE IF NOT EXISTS disallowed (
            url TEXT PRIMARY KEY,
            reason TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "errors": """
        CREATE SEQUENCE IF NOT EXISTS errors_id_seq;
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY DEFAULT nextval('errors_id_seq'),
            url TEXT NOT NULL,
            error_type TEXT,
            error_message TEXT,
            status_code INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
} 