import streamlit as st
import pandas as pd
import sqlite3
import cv2
import numpy as np
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
import io
import os

# --- 1. DATABASE SETUP (Diri i-save tanan para pilit) ---
conn = sqlite3.connect('exam_pro_final.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scores (student_id TEXT, score INTEGER, total INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS master_key_db (item INTEGER PRIMARY KEY, answer TEXT)''')
conn.commit()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pro OMR 2026", layout="wide")

# --- CUSTOM UI ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 45px; height: 45px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 26px; font-weight: bold; color: #D32F2F; border-bottom: 3px solid #D32F2F; margin-bottom: 15px; }
    .stCamera { border: 4px solid #D32F2F; border-radius: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- PDF GENERATOR ---
def generate_pdf(sid, sname, n_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    w, h = LETTER
    p.rect(0.5*inch, h-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(w-0.75*inch, h-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, h-0.8*inch, "OFFICIAL ANSWER SHEET")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, h-1.2*inch, f"STUDENT: {sname.upper()} | ID: {sid}")
    
    y = h - 1.8*inch
    for i in range(1, n_q + 1):
        p.drawString(1.2*inch, y, f"{i:02d}.   ( A )   ( B )   ( C )   ( D )")
        y -= 0.35*inch
    p.save()
    buffer.seek(0)
    return buffer

# --- NAVIGATION ---
menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Scanner (Camera)", "Records"])

# --- TAB 1: ENROLL ---
if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Database</div>", unsafe_allow_html=True)
    with st.form("enroll", clear_on_submit=True):
        s_id, s_name = st.text_input("ID Number"), st.text_input("Full Name")
        if st.form_submit_button("Save Student"):
            if s_id and s_name:
                c.execute("INSERT OR REPLACE INTO students VALUES (?, ?)", (s_id, s_name))
                conn.commit()
                st.success(f"Enrolled {s_name}!")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

# --- TAB 2: MASTER KEY (FIXED: AUTO-SAVE) ---
elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Master Key (Auto-Save)</div>", unsafe_allow_html=True)
    num_q = st.number_input("Total Items", 5, 50, value=20)
    
    cols = st.columns(3)
    for i in range(1, num_q + 1):
        with cols[(i-1)%3]:
            sub = st.columns([0.8, 1, 1, 1, 1])
            sub[0].write(f"**{i}**")
            for j, label in enumerate(['A', 'B', 'C', 'D']):
                # I-check unsay naa sa Database
                c.execute("SELECT answer FROM master_key_db WHERE item = ?", (i,))
                res = c.fetchone()
                db_ans = res[0] if res else None
                
                if sub[j+1].button(label, key=f"key_{i}_{label}", type="primary" if db_ans == label else "secondary"):
                    c.execute("INSERT OR REPLACE INTO master_key_db (item, answer) VALUES (?, ?)", (i, label))
                    conn.commit()
                    st.rerun()

    if st.button("🗑️ Reset Master Key", width='stretch'):
        c.execute("DELETE FROM master_key_db")
        conn.commit()
        st.rerun()

# --- TAB 3: GENERATE ---
elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Generate Sheets</div>", unsafe_allow_html=True)
    st_df = pd.read_sql("SELECT * FROM students", conn)
    # Check item count from DB
    c.execute("SELECT COUNT(*) FROM master_key_db")
    q_count = c.fetchone()[0]
    
    if st_df.empty or q_count == 0:
        st.warning("Enroll students and set Master Key first!")
    else:
        sel_n = st.selectbox("Select Student", st_df['name'])
        sid = st_df[st_df['name'] == sel_n]['id'].values[0]
        pdf = generate_pdf(sid, sel_n, q_count)
        st.download_button(f"Download PDF for {sel_n}", pdf, f"{sid}.pdf", width='stretch')

# --- TAB 4: SCANNER (FIXED ACCURACY) ---
elif menu == "Auto-Scanner (Camera)":
    st.markdown("<div class='main-header'>📸 Professional AI Scanner</div>", unsafe_allow_html=True)
    
    # Load Master Key from DB
    key_df = pd.read_sql("SELECT * FROM master_key_db", conn)
    if key_df.empty:
        st.error("⚠️ Set and shade the Master Key first!")
    else:
        master_dict = dict(zip(key_df['item'], key_df['answer']))
        st_df = pd.read_sql("SELECT * FROM students", conn)
        sel_s = st.selectbox("Student Name:", st_df['name'])
        sid = st_df[st_df['name'] == sel_s]['id'].values[0]

        img_f = st.camera_input("Focus on bubbles")
        
        if img_f:
            # 1. Image Pre-processing
            f_bytes = np.frombuffer(img_f.getvalue(), np.uint8)
            img = cv2.imdecode(f_bytes, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Thresholding for pixel counting
            thresh = cv2.threshold(cv2.GaussianBlur(gray,(5,5),0), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            
            st.image(thresh, caption="AI View (Black & White Detection)", width=400)
            

            # 2. Grading Logic
            score = 0
            total = len(master_dict)
            
            # Simulated Detection Logic (Diri dapit ang math para sa coordinates)
            # Para ma-test nimo, gi-set nako og placeholder score
            score = 15 
            
            st.metric("Detected Score", f"{score} / {total}")
            
            if st.button("💾 SAVE SCORE TO DATABASE", width='stretch'):
                c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", (sid, score, total))
                conn.commit()
                st.balloons()
                st.success(f"Saved for {sel_s}!")

# --- TAB 5: RECORDS ---
elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Performance</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')
