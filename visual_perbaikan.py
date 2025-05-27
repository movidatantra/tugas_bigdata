import streamlit as st
from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import nltk
from nltk.corpus import stopwords
import re
import matplotlib.dates as mdates

nltk.download('stopwords')
stop_words = set(stopwords.words('indonesian'))

# Koneksi MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["kanker_db"]
collection = db["perbaikan_uts"]

# Fungsi preprocessing
def preprocessing(text):
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = text.lower()
    tokens = text.split()
    tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    return ' '.join(tokens)

# Ambil data
data = list(collection.find())
df = pd.DataFrame(data)

# Cek data kosong
if df.empty:
    st.warning("Tidak ada data tersedia. Jalankan `scraper.py` terlebih dahulu.")
    st.stop()

# Pastikan kolom datetime
df['tanggal_publish'] = pd.to_datetime(df['tanggal_publish'])
df['waktu_scraping'] = pd.to_datetime(df['waktu_scraping'])

# Preprocessing
df['isi_clean'] = df['isi'].apply(preprocessing)

# ==============================================
# FILTER
# ==============================================
st.sidebar.header("🔍 Filter Data")

# Filter berdasarkan sumber
unique_sumber = df['sumber'].unique().tolist()
selected_sumber = st.sidebar.multiselect("Pilih Sumber Artikel:", unique_sumber, default=unique_sumber)

# Filter berdasarkan rentang tanggal
min_date = df['tanggal_publish'].min().date()
max_date = df['tanggal_publish'].max().date()
start_date, end_date = st.sidebar.date_input("Pilih Rentang Tanggal:", [min_date, max_date])

# Filter berdasarkan kata kunci
keyword = st.sidebar.text_input("Cari kata kunci (di judul atau isi):", "")

# Terapkan filter
filtered_df = df[
    (df['sumber'].isin(selected_sumber)) &
    (df['tanggal_publish'].dt.date >= start_date) &
    (df['tanggal_publish'].dt.date <= end_date)
].copy()

if keyword:
    keyword_lower = keyword.lower()
    filtered_df = filtered_df[
        filtered_df['judul'].str.lower().str.contains(keyword_lower) |
        filtered_df['isi_clean'].str.contains(keyword_lower)
    ]

# Tampilkan judul
st.title("📊 Visualisasi Artikel Kesehatan: Kanker")

# Tampilkan jumlah artikel terfilter
st.info(f"Menampilkan {len(filtered_df)} artikel setelah difilter.")

# ==============================================
# DIAGRAM 1 - Distribusi Artikel per Sumber
# ==============================================
st.subheader("1. 📌 Distribusi Artikel per Sumber")
fig1, ax1 = plt.subplots()
sns.countplot(data=filtered_df, y='sumber', order=filtered_df['sumber'].value_counts().index, ax=ax1)
ax1.set_xlabel("Jumlah Artikel")
st.pyplot(fig1)

# ==============================================
# DIAGRAM 2 - Kata yang Paling Sering Muncul
# ==============================================
st.subheader("2. ☁️ Kata yang Paling Sering Muncul")
all_text = ' '.join(filtered_df['isi_clean'].tolist())
if all_text.strip():
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(all_text)
    fig2, ax2 = plt.subplots()
    ax2.imshow(wordcloud, interpolation='bilinear')
    ax2.axis("off")
    st.pyplot(fig2)
else:
    st.warning("Tidak ada teks untuk membuat wordcloud.")

# ==============================================
# DIAGRAM 3 - Jumlah Artikel per Tanggal Scraping
# ==============================================
st.subheader("3. 📅 Jumlah Artikel yang Diambil per Tanggal Scraping")

tanggal_scrape = filtered_df['waktu_scraping'].dt.date
scrape_counts = tanggal_scrape.value_counts().sort_index()

fig3, ax3 = plt.subplots(figsize=(10, 6))
scrape_counts.plot(kind='line', marker='o', color='green', ax=ax3)
ax3.set_title('Jumlah Artikel per Tanggal Scraping')
ax3.set_xlabel('Tanggal')
ax3.set_ylabel('Jumlah Artikel')

# Atur agar label tanggal tidak terlalu rapat
ax3.xaxis.set_major_locator(mdates.DayLocator(interval=1))
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

plt.xticks(rotation=45)
plt.tight_layout()
st.pyplot(fig3)

# ==============================================
# DIAGRAM 4 - Jumlah Artikel per Bulan Terbit
# ==============================================
st.subheader("4. 📆 Jumlah Artikel Berdasarkan Bulan Terbit")
filtered_df['bulan'] = filtered_df['tanggal_publish'].dt.to_period('M')
monthly_counts = filtered_df['bulan'].value_counts().sort_index()
fig4, ax4 = plt.subplots(figsize=(10, 6))
monthly_counts.plot(kind='bar', color='orange', ax=ax4)
ax4.set_title('Jumlah Artikel per Bulan Terbit')
ax4.set_xlabel('Bulan')
ax4.set_ylabel('Jumlah Artikel')
ax4.set_xticklabels([str(b) for b in monthly_counts.index], rotation=45)
st.pyplot(fig4)

# ==============================================
# TABEL DATA
# ==============================================
st.subheader("📄 Tabel Artikel")
st.dataframe(filtered_df[['judul', 'sumber', 'tanggal_publish', 'waktu_scraping']])
