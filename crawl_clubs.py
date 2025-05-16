import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode

# Lista top 50 gradova u Engleskoj
TOP_50_CITIES = [
    "london", "manchester", "birmingham", "leeds", "liverpool", "newcastle", 
    "sheffield", "bristol", "nottingham", "southampton", "portsmouth", "brighton", 
    "leicester", "coventry", "hull", "stoke", "plymouth", "wolverhampton", "derby", 
    "swansea", "cardiff", "middlesbrough", "sunderland", "oxford", "cambridge", 
    "york", "bath", "exeter", "norwich", "canterbury", "gloucester", "peterborough", 
    "preston", "blackpool", "bournemouth", "reading", "milton keynes", "blackburn", 
    "bolton", "luton", "northampton", "norwich", "preston", "swindon", "southend", 
    "wigan", "warrington", "huddersfield", "ipswich", "colchester"
]

async def extract_club_links(city):
    """
    Ekstrahovati linkove klubova za određeni grad, sa pravilnom paginacijom
    """
    # Konfiguracija pretraživača
    browser_config = BrowserConfig(
        browser_type="chromium", 
        headless=True,  # Za produkciju koristimo "headless" mod
        viewport_width=1280,
        viewport_height=800,
        verbose=True     # Povećano logovanje
    )
    
    # CSS selektor za klubove
    club_selector = "section.flex.w-full.flex-col.gap-4.rounded-2xl"
    
    # Konfiguracija za ekstrakciju podataka pomoću CSS selektora
    extraction_strategy = JsonCssExtractionStrategy(
        schema={
            "name": "Club Links",
            "baseSelector": club_selector,
            "fields": [
                {
                    "name": "club_name",
                    "selector": "h3.text-base.font-bold",
                    "type": "text"
                },
                {
                    "name": "club_link",
                    "selector": "a",
                    "type": "attribute",
                    "attribute": "href"
                }
            ]
        }
    )
    
    # URL za pretragu klubova
    url = f"https://playtomic.com/search?q={city}"
    
    print(f"Pretraživanje klubova u gradu: {city}")
    
    all_clubs = []
    seen_club_ids = set()  # Za praćenje već viđenih klubova po ID-u
    page_num = 1
    session_id = f"search_{city}"
    
    # Koristimo kontekst menadžer za pravilno upravljanje resursima
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Konfiguracija za prvu stranicu
        crawler_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            page_timeout=20000,  # 20 sekundi za učitavanje
            session_id=session_id
        )
        
        # Pretraži prvu stranicu
        print(f"Pretraživanje stranice {page_num}...")
        result = await crawler.arun(url=url, config=crawler_config)
        
        # Proveri da li ima rezultata
        if result and hasattr(result, 'extracted_content'):
            clubs = json.loads(result.extracted_content)
            
            # Dodaj klubove u listu
            for club in clubs:
                club_link = club.get('club_link', '')
                club_id = club_link.split('/')[-1] if club_link else None
                if club_id and club_id not in seen_club_ids:
                    seen_club_ids.add(club_id)
                    all_clubs.append(club)
            
            print(f"Pronađeno {len(clubs)} klubova na stranici {page_num}, dodato {len(all_clubs)} jedinstvenih")
            
            # Proveri da li postoji dugme "Next page"
            has_next_page = 'Next page</button>' in result.html
            print(f"Postoji sledeća stranica: {has_next_page}")
            
            # Ako postoje sledeće stranice, obradi ih
            page_limit = 5  # Najviše 5 stranica po gradu
            
            while has_next_page and page_num < page_limit:
                page_num += 1
                print(f"\nPrelazak na stranicu {page_num}...")
                
                # JavaScript za klik na dugme "Next page"
                js_click = """
                // Skroluj do dna stranice gde se nalazi Next page dugme
                window.scrollTo(0, document.body.scrollHeight);
                
                // Daj malo vremena da se dugme učita ako je potrebno
                setTimeout(() => {
                    // Nađi sva dugmad na stranici
                    const buttons = document.querySelectorAll('button');
                    console.log('Pronađeno dugmadi:', buttons.length);
                    
                    // Traži dugme koje sadrži 'Next page'
                    for (let i = 0; i < buttons.length; i++) {
                        if (buttons[i].textContent.includes('Next page')) {
                            console.log('Pronađeno Next page dugme:', buttons[i]);
                            buttons[i].scrollIntoView();
                            buttons[i].click();
                            console.log('Kliknuto na Next page dugme');
                            break;
                        }
                    }
                }, 1000);
                """
                
                # Konfiguracija za klik na sledeću stranu
                next_config = CrawlerRunConfig(
                    js_code=js_click,
                    js_only=True,
                    session_id=session_id,
                    page_timeout=30000
                )
                
                # Klikni na dugme za sledeću stranu
                await crawler.arun(url=url, config=next_config)
                
                # Sačekaj da se nova stranica učita
                await asyncio.sleep(3)
                
                # Ekstrakcija podataka sa nove stranice
                extract_config = CrawlerRunConfig(
                    extraction_strategy=extraction_strategy,
                    js_only=True,
                    session_id=session_id,
                    cache_mode=CacheMode.BYPASS
                )
                
                next_result = await crawler.arun(url=url, config=extract_config)
                
                if next_result and hasattr(next_result, 'extracted_content'):
                    next_clubs = json.loads(next_result.extracted_content)
                    print(f"Pronađeno {len(next_clubs)} klubova na stranici {page_num}")
                    
                    old_count = len(all_clubs)
                    
                    # Dodaj samo nove klubove
                    for club in next_clubs:
                        club_link = club.get('club_link', '')
                        club_id = club_link.split('/')[-1] if club_link else None
                        if club_id and club_id not in seen_club_ids:
                            seen_club_ids.add(club_id)
                            all_clubs.append(club)
                    
                    new_added = len(all_clubs) - old_count
                    print(f"Dodato {new_added} novih klubova (ukupno {len(all_clubs)} jedinstvenih)")
                    
                    # Proveri da li su dodati novi klubovi
                    if new_added == 0:
                        print("Nema novih klubova na ovoj stranici. Prekidam paginaciju.")
                        break
                    
                    # Proveri da li ima još stranica
                    has_next_page = 'Next page</button>' in next_result.html
                    print(f"Postoji još stranica: {has_next_page}")
                else:
                    print("Nema ekstrahovanih podataka sa nove stranice. Prekidam paginaciju.")
                    break
                    
            # Oslobodi resurse zatvaranjem sesije
            try:
                await crawler.crawler_strategy.kill_session(session_id)
                print(f"Zatvorena sesija za grad: {city}")
            except Exception as e:
                print(f"Greška pri zatvaranju sesije: {str(e)}")
        else:
            print(f"Nema pronađenih klubova u gradu {city}")
    
    # Prikaži rezultate
    if all_clubs:
        print(f"\nPronađeno ukupno {len(all_clubs)} jedinstvenih klubova u gradu {city} kroz {page_num} stranica:")
        for club in all_clubs:
            print(f"- {club.get('club_name')}: https://playtomic.com{club.get('club_link')}")
        return all_clubs
    else:
        print(f"Nema pronađenih klubova u gradu {city}")
        return []

async def main():
    all_results = {}
    
    # Pretraži sve gradove
    for city in TOP_50_CITIES:
        try:
            clubs = await extract_club_links(city)
            all_results[city] = clubs
            
            # Kratka pauza između gradova
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Greška pri obradi grada {city}: {str(e)}")
            all_results[city] = []
    
    # Sačuvaj rezultate u JSON fajl
    with open("club_links.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print("\nSvi rezultati su sačuvani u fajl 'club_links.json'")
    
    # Statistika rezultata
    total_clubs = sum(len(clubs) for clubs in all_results.values())
    cities_with_clubs = sum(1 for clubs in all_results.values() if clubs)
    print(f"\nUkupna statistika:")
    print(f"- Broj obrađenih gradova: {len(TOP_50_CITIES)}")
    print(f"- Broj gradova sa klubovima: {cities_with_clubs}")
    print(f"- Ukupan broj pronađenih klubova: {total_clubs}")

    return all_results  # Vraćamo sve rezultate

if __name__ == "__main__":
    asyncio.run(main())
