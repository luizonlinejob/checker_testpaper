import streamlit as st
import pandas as pd
import sqlite3
import cv2
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
import io
import os

# --- DATABASE SETUP ---
conn = sqlite3.connect('exam_final_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scores (student_id TEXT, score INTEGER, total INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
# Bag-ong table para sa Master Key aron dili na gyud mawala
c.execute('''CREATE TABLE IF NOT EXISTS master_key_db (item INTEGER PRIMARY KEY, answer TEXT)''')
conn.commit()

# --- INITIALIZE STATE ---
if 'master_key' not in st.session_state:
    # Load gikan sa Database kung naa nay sulod
    saved_key = pd.read_sql("SELECT * FROM master_key_db", conn)
    if not saved_key.empty:
        st.session_state.master_key = dict(zip(saved_key['item'], saved_key['answer']))
    else:
        st.session_state.master_key = {}

st.set_page_config(page_title="Final OMR 2026", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 45px; height: 45px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 26px; font-weight: bold; color: #D32F2F; border-bottom: 3px solid #D32F2F; margin-bottom: 15px; }
    .stCamera { border: 5px solid #D32F2F; border-radius: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- PDF GENERATOR ---
def generate_pro_sheet(student_id, student_name, num_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    w_pdf, h_pdf = LETTER
    p.rect(0.5*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(w_pdf-0.75*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, h_pdf-0.8*inch, "OMR ANSWER SHEET")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, h_pdf-1.2*inch, f"STUDENT: {student_name.upper()}")
    y = h_pdf - 2.0*inch
    for i in range(1, num_q + 1):
        p.drawString(1.2*inch, y, f"{i:02d}.   ( A )   ( B )   ( C )   ( D )")
        y -= 0.35*inch
    p.save()
    buffer.seek(0)
    return buffer

# --- MAIN NAVIGATION ---
menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Scanner (Camera)", "Records"])

# 1. ENROLLMENT (As is - focus ra ta)
if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Enrollment</div>", unsafe_allow_html=True)
    with st.form("enroll", clear_on_submit=True):
        s_id, s_name = st.text_input("ID Number"), st.text_input("Full Name")
        if st.form_submit_button("Save Student"):
            if s_id and s_name:
                c.execute("INSERT OR REPLACE INTO students VALUES (?, ?)", (s_id, s_name))
                conn.commit()
                st.success("Enrolled!")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

# 2. MASTER KEY (With Database Saving)
elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Master Answer Key</div>", unsafe_allow_html=True)
    num_q = st.number_input("Total Items", 5, 50, 20)
    
    # Clickable Bubbles
    cols = st.columns(3)
    for i in range(1, num_q + 1):
        with cols[(i-1)%3]:
            sub = st.columns([0.8, 1, 1, 1, 1])
            sub[0].write(f"**{i}**")
            for j, label in enumerate(['A', 'B', 'C', 'D']):
                active = st.session_state.master_key.get(i) == label
                if sub[j+1].button(label, key=f"m_{i}_{j}", type="primary" if active else "secondary"):
                    st.session_state.master_key[i] = label
                    st.rerun()

    st.divider()
    # KANI ANG BUTTON NGA MAG-SAVE SA DB
    if st.button("🔒 LOCK & SAVE MASTER KEY TO DATABASE", width='stretch'):
        if len(st.session_state.master_key) > 0:
            c.execute("DELETE FROM master_key_db") # Clear old key
            for item, ans in st.session_state.master_key.items():
                c.execute("INSERT INTO master_key_db VALUES (?, ?)", (item, ans))
            conn.commit()
            st.success("✅ Master Key permanently saved to Database!")
        else:
            st.error("Pilia una ang mga tubag!")

# 3. GENERATE PAPERS
elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Generate Sheets</div>", unsafe_allow_html=True)
    st_df = pd.read_sql("SELECT * FROM students", conn)
    if not st_df.empty:
        sel_name = st.selectbox("Select Student", st_df['name'])
        sel_id = st_df[st_df['name'] == sel_name]['id'].values[0]
        q_count = len(st.session_state.master_key) if st.session_state.master_key else 20
        pdf = generate_pro_sheet(sel_id, sel_name, q_count)
        st.download_button(f"Download PDF for {sel_name}", pdf, f"{sel_id}.pdf", width='stretch')

# 4. AUTO-SCANNER
elif menu == "Auto-Scanner (Camera)":
    st.markdown("<div class='main-header'>📸 Professional Scanner</div>", unsafe_allow_html=True)
    
    # I-check kung naay sulod ang Master Key gikan sa DB
    saved_key = pd.read_sql("SELECT * FROM master_key_db", conn)
    if saved_key.empty:
        st.error("⚠️ Wala pay Master Key! Balhin sa 'Set Master Key' tab unya i-click ang LOCK & SAVE.")
    else:
        st_df = pd.read_sql("SELECT * FROM students", conn)
        selected_student = st.selectbox("Identify Student:", st_df['name'])
        s_id = st_df[st_df['name'] == selected_student]['id'].values[0]

        img_file = st.camera_input("Focus on the Shaded Circles")
        
        if img_file:
            # OpenCV Processing (Binary View)
            file_bytes = np.frombuffer(img_file.getvalue(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(cv2.GaussianBlur(gray, (5,5), 0), 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            st.image(thresh, caption="AI Detection View", width=400)
            

            # Logic Computation
            score = 18 # Placeholder score simulation
            st.metric(f"Detected Score", f"{score} / {len(saved_key)}")
            
            if st.button("💾 SAVE SCORE", width='stretch'):
                c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", 
                          (s_id, score, len(saved_key)))
                conn.commit()
                st.success("Record Saved!")

# 5. RECORDS
elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Records</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')
