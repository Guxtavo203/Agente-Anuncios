#!/usr/bin/env python3
import requests, json, base64, os, re
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GH_PAT          = os.environ["GH_PAT"]
GITHUB_REPO     = "Guxtavo203/Agente-Anuncios"
META_TOKEN      = os.environ.get("META_ADS_TOKEN", "")
MEMORY_FILE     = "sent_ads.json"
TODAY           = datetime.now().strftime("%d/%m/%Y")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

KEYWORDS = [
    "produto digital renda online brasil anuncio instagram 2026",
    "IAS inteligencia artificial afiliado anuncio viral brasil 2026",
    "afiliado produto digital renda extra anuncio facebook brasil",
    "metodo renda online produto digital video anuncio brasil 2026",
    "ganhar dinheiro online produto digital anuncio viral instagram brasil",
]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False}
    r = requests.post(url, json=data, timeout=30)
    print(f"Telegram: {r.status_code}")
    return r.ok

def get_memory():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}"
    r = requests.get(url, headers={"Authorization": f"token {GH_PAT}"}, timeout=30)
    if r.status_code == 404:
        return [], None
    data = r.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    return content, data["sha"]

def update_memory(ads_list, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}"
    content = base64.b64encode(json.dumps(ads_list, ensure_ascii=False, indent=2).encode()).decode()
    body = {"message": f"Update sent ads {datetime.now().strftime('%Y-%m-%d')}", "content": content}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers={"Authorization": f"token {GH_PAT}", "Content-Type": "application/json"}, json=body, timeout=30)
    return r.status_code in [200, 201]

def search_meta_api(keyword):
    if not META_TOKEN:
        return []
    url = "https://graph.facebook.com/v19.0/ads_archive"
    params = {
        "access_token": META_TOKEN,
        "search_terms": keyword,
        "ad_type": "ALL",
        "ad_reached_countries": "BR",
        "fields": "id,ad_creative_body,page_name,ad_delivery_start_time",
        "limit": 10,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        ads = []
        for ad in r.json().get("data", []):
            ads.append({
                "url": f"https://www.facebook.com/ads/library/?id={ad.get('id','')}",
                "advertiser": ad.get("page_name", "Desconhecido"),
                "body": ad.get("ad_creative_body", "")[:300],
                "start": ad.get("ad_delivery_start_time", ""),
                "source": "Meta API oficial",
            })
        return ads
    except Exception as e:
        print(f"Meta API erro: {e}")
        return []

def search_duckduckgo(query):
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}&kl=br-pt"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for result in soup.find_all("div", class_="result__body")[:6]:
            title_el = result.find("a", class_="result__a")
            snippet_el = result.find("a", class_="result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "body": snippet_el.get_text(strip=True) if snippet_el else "",
                    "source": "Google/Web",
                })
        return results
    except Exception as e:
        print(f"DuckDuckGo erro: {e}")
        return []

def analyze_ad(ad):
    body = ad.get("body", "") or ad.get("title", "")
    hook = body[:120].strip() if body else "Ver no link"
    bl = body.lower()
    parts = []
    if any(w in bl for w in ["problema","cansado","frustrado","dificil","nao consegue"]):
        parts.append("Problema")
    if any(w in bl for w in ["solucao","metodo","sistema","descubra","aprenda","segredo"]):
        parts.append("Solucao")
    if any(w in bl for w in ["clique","acesse","saiba mais","compre","garanta","link na bio"]):
        parts.append("CTA")
    structure = " → ".join(parts) if parts else "Hook direto → Beneficio → CTA"
    return hook, structure

def main():
    print(f"Buscando anuncios virais - {TODAY}")
    sent_ads, sha = get_memory()
    sent_urls = {a["url"] for a in sent_ads}
    print(f"Ja enviados: {len(sent_urls)}")

    all_ads = []

    if META_TOKEN:
        print("Buscando via Meta Ads API...")
        for kw in ["produto digital", "IAS inteligencia artificial", "renda online afiliado"]:
            all_ads.extend(search_meta_api(kw))

    print("Buscando via DuckDuckGo...")
    for kw in KEYWORDS:
        all_ads.extend(search_duckduckgo(kw))

    seen, new_ads = set(), []
    for ad in all_ads:
        url = ad.get("url", "")
        if url and url not in sent_urls and url not in seen:
            seen.add(url)
            new_ads.append(ad)

    print(f"Novos encontrados: {len(new_ads)}")

    if not new_ads:
        send_telegram(
            f"📊 <b>Analise do dia — {TODAY}</b>\n\n"
            "Nenhum anuncio novo encontrado hoje.\n"
            "Os conteudos em circulacao sao os mesmos de dias anteriores.\n"
            "Voltamos amanha as 9h! ✅"
        )
        return

    send_telegram(
        f"🔥 <b>ANUNCIOS VIRAIS DO DIA — {TODAY}</b>\n\n"
        f"Encontrei {len(new_ads[:8])} novos anuncios no nicho produto digital / IAS / renda online Brasil 🇧🇷"
    )

    new_entries = []
    for i, ad in enumerate(new_ads[:8], 1):
        hook, structure = analyze_ad(ad)
        title = ad.get("advertiser") or ad.get("title", "Anunciante desconhecido")
        url = ad.get("url", "")
        source = ad.get("source", "Web")
        msg = (
            f"📌 <b>ANUNCIO {i}</b>\n"
            f"👤 {title}\n"
            f"🎯 Hook: {hook}\n"
            f"📋 Estrutura: {structure}\n"
            f"📡 Fonte: {source}\n"
        )
        if url:
            msg += f'🔗 <a href="{url}">Ver anuncio</a>'
        send_telegram(msg)
        if url:
            new_entries.append({"url": url, "date_sent": datetime.now().strftime("%Y-%m-%d")})

    updated = (sent_ads + new_entries)[-500:]
    if update_memory(updated, sha):
        print("Memoria atualizada com sucesso")
    else:
        print("Erro ao atualizar memoria")

if __name__ == "__main__":
    main()