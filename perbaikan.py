import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import urlparse, urljoin, urlunparse
from dateutil import parser as dateparse
import streamlit as st

# Koneksi MongoDB
MONGO_URI = st.secrets["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["kanker_db"]
collection = db["perbaikan_uts"]
collection.create_index([("link", 1)], unique=True)

# Fungsi bantu
def ambil_sumber(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "tidak diketahui"

def normalisasi_judul(link, soup):
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    return urlparse(link).path.split("/")[-1].replace("-", " ").capitalize()

def ambil_isi_artikel(link):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(link, headers=headers, timeout=10)

        if r.status_code != 200:
            print(f"❌ Status bukan 200 dari {link}")
            return "", datetime.now(), None

        soup = BeautifulSoup(r.content, 'html.parser')

        paragraphs = soup.find_all('p')
        isi = ' '.join([p.get_text() for p in paragraphs if len(p.get_text()) > 50])

        tanggal = None

        if 'liputan6.com' in link or 'idntimes.com' in link:
            tag = soup.find('time')
            if tag and tag.has_attr('datetime'):
                tanggal = tag['datetime']
        elif 'kompas.com' in link:
            tag = soup.find('div', class_='date')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif 'cnnindonesia.com' in link:
            tag = soup.find('span', class_='date')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif 'tribunnews.com' in link or 'suara.com' in link or 'kemkes.go.id' in link:
            tag = soup.find('div', class_='date') or soup.find('time')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif 'jpnn.com' in link or 'doktersehat.com' in link:
            tag = soup.find('span', class_='date') or soup.find('time')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif any(domain in link for domain in ['alodokter.com', 'klikdokter.com', 'halodoc.com', 'hellosehat.com']):
            tag = soup.find('time') or soup.find('span', class_='date')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif 'siloamhospitals.com' in link:
            tag = soup.find('div', class_='article-date')
            if tag:
                tanggal = tag.get_text(strip=True)
        elif 'merdeka.com' in link:
            tag = soup.find('time')
            if tag:
                tanggal = tag.get_text(strip=True)

        if tanggal:
            try:
                tanggal = dateparser.parse(tanggal, fuzzy=True)
            except:
                tanggal = datetime.now()
        else:
            tanggal = datetime.now()

        return isi.strip(), tanggal, soup

    except Exception as e:
        print(f"❌ Gagal ambil isi dari {link}: {e}")
        return "", datetime.now(), None

def link_valid(link):
    if not link.startswith("http"):
        return False
    blacklist = ['#', 'javascript:void', '.jpg', '.png', '.svg', '.css', '.ico']
    return not any(bad in link.lower() for bad in blacklist)

def normalisasi_url(link):
    parsed = urlparse(link)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

def crawl_artikel():
    sumber_urls = {
        "Liputan6": "https://www.liputan6.com/health",
        "IDN Times": "https://www.idntimes.com/health",
        "Kompas": "https://health.kompas.com/",
        "CNN Indonesia": "https://www.cnnindonesia.com/gaya-hidup/kesehatan",
        "Tribun News": "https://www.tribunnews.com/kesehatan",
        "Suara": "https://www.suara.com/health",
        "Merdeka": "https://www.merdeka.com/sehat/",
        "JPNN": "https://www.jpnn.com/tag/kesehatan",
        "Kemenkes": "https://kemkes.go.id/id/category/rilis-berita",
        "Alodokter": "https://www.alodokter.com/kesehatan",
        "Dokter Sehat": "https://www.doktersehat.com",
        "Klikdokter": "https://www.klikdokter.com",
        "Hello Sehat": "https://hellosehat.com/kanker/",
        "Halodoc": "https://www.halodoc.com/artikel",
        "Siloam": "https://www.siloamhospitals.com/informasi-siloam/artikel"
    }

    keyword_filter = ['kanker', 'kanker payudara']

    for sumber, url in sumber_urls.items():
        print(f"\n🔍 Mengambil artikel dari {sumber} ({url})")

        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.content, 'html.parser')
            artikel_links = soup.find_all('a', href=True)

            for tag in artikel_links:
                href = tag['href']
                full_url = urljoin(url, href)
                full_url = normalisasi_url(full_url)

                if not link_valid(full_url):
                    continue

                if collection.find_one({"link": full_url}):
                    continue  # sudah ada

                isi, tgl, detail_soup = ambil_isi_artikel(full_url)
                if not isi or len(isi) < 100:
                    continue

                # Hanya ambil artikel jika mengandung kata "kanker" atau "kanker payudara"
                isi_lower = isi.lower()
                if not any(keyword in isi_lower for keyword in keyword_filter):
                    continue

                judul = tag.get_text(strip=True)
                if not judul or len(judul) < 10:
                    judul = normalisasi_judul(full_url, detail_soup)

                data = {
                    "judul": judul,
                    "link": full_url,
                    "tanggal_publish": tgl,
                    "ringkasan": "",
                    "isi": isi,
                    "sumber": sumber,
                    "waktu_scraping": datetime.now()
                }

                try:
                    collection.insert_one(data)
                    print(f"✅ Disimpan: {judul}")
                except Exception as e:
                    if 'duplicate key error' in str(e).lower():
                        print(f"⚠️ Duplikat: {full_url}")
                    else:
                        print(f"❌ Gagal simpan {judul}: {e}")

        except Exception as e:
            print(f"❌ Gagal akses {url}: {e}")

if __name__ == "__main__":
    crawl_artikel()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_articles = collection.count_documents({'waktu_scraping': {'$gte': today}})
    print(f"\n🔁 Total artikel tentang kanker yang disimpan hari ini: {total_articles}")
