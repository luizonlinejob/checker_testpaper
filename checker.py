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

# --- DATABASE SETUP ---
conn = sqlite3.connect('exam_pro_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scores (student_id TEXT, score INTEGER, total INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# --- INITIALIZE STATE ---
if 'master_key' not in st.session_state: st.session_state.master_key = {}

st.set_page_config(page_title="Pro OMR System 2026", layout="wide", page_icon="📝")

# --- CUSTOM CSS (2026 Standards) ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 45px; height: 45px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 26px; font-weight: bold; color: #D32F2F; border-bottom: 3px solid #D32F2F; margin-bottom: 15px; }
    [data-testid="stMetricValue"] { color: #D32F2F; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. PDF GENERATOR (CIRCLE STYLE) ---
def generate_pro_sheet(student_id, student_name, num_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    w_pdf, h_pdf = LETTER
    
    # Alignment Markers
    p.rect(0.5*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(w_pdf-0.75*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    
    # QR Code (Dako-on gamay para dali mabasa sa phone)
    qr = qrcode.make(student_id)
    qr.save("temp_qr.png")
    p.drawImage("temp_qr.png", w_pdf-1.7*inch, h_pdf-1.8*inch, width=1.2*inch, height=1.2*inch)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, h_pdf-0.8*inch, "OFFICIAL ANSWER SHEET")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, h_pdf-1.2*inch, f"STUDENT: {student_name.upper()}")
    p.drawString(1*inch, h_pdf-1.4*inch, f"ID NUMBER: {student_id}")
    
    y = h_pdf - 2.2*inch
    for i in range(1, num_q + 1):
        p.setFont("Helvetica-Bold", 10)
        p.drawString(1.2*inch, y, f"{i:02d}.")
        for j, choice in enumerate(['A', 'B', 'C', 'D']):
            x = 1.8*inch + (j * 0.5*inch)
            p.circle(x, y+3, 8, stroke=1, fill=0)
            p.setFont("Helvetica", 7)
            p.drawCentredString(x, y+1.5, choice)
        y -= 0.35*inch
    
    p.save()
    if os.path.exists("temp_qr.png"): os.remove("temp_qr.png")
    buffer.seek(0)
    return buffer

# --- MAIN NAVIGATION ---
st.title("🛡️ Pro-Level OMR System (2026)")
menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Check Camera", "Records"])

# --- TAB 1: ENROLLMENT ---
if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Enrollment</div>", unsafe_allow_html=True)
    with st.form("enroll", clear_on_submit=True):
        s_id = st.text_input("ID Number (e.g. 2026-001)")
        s_name = st.text_input("Full Name")
        if st.form_submit_button("Save Student"):
            if s_id and s_name:
                try:
                    c.execute("INSERT INTO students VALUES (?, ?)", (s_id, s_name))
                    conn.commit()
                    st.success("Enrolled!")
                except: st.error("Error: ID exists!")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

# --- TAB 2: MASTER KEY ---
elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Set Answer Key</div>", unsafe_allow_html=True)
    num_q = st.number_input("Total Items", 5, 100, 20)
    cols = st.columns(3)
    for i in range(1, num_q + 1):
        with cols[(i-1)%3]:
            sub = st.columns([0.8, 1, 1, 1, 1])
            sub[0].write(f"**{i}**")
            for j, label in enumerate(['A', 'B', 'C', 'D']):
                active = st.session_state.master_key.get(i) == j
                if sub[j+1].button(label, key=f"m_{i}_{j}", type="primary" if active else "secondary"):
                    st.session_state.master_key[i] = j
                    st.rerun()

# --- TAB 3: GENERATE PAPERS ---
elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Generate Answer Sheets</div>", unsafe_allow_html=True)
    st_df = pd.read_sql("SELECT * FROM students", conn)
    if st_df.empty: st.warning("Enroll students first!")
    else:
        sel_name = st.selectbox("Select Student", st_df['name'])
        sel_id = st_df[st_df['name'] == sel_name]['id'].values[0]
        q_count = len(st.session_state.master_key) if st.session_state.master_key else 20
        pdf_file = generate_pro_sheet(sel_id, sel_name, q_count)
        st.download_button(f"Download PDF for {sel_name}", pdf_file, f"{sel_id}.pdf", width='stretch')

# --- TAB 4: SCANNER (THE AUTOMATED PART) ---
elif menu == "Auto-Check Camera":
    st.markdown("<div class='main-header'>📸 AI Auto-Scanner</div>", unsafe_allow_html=True)
    
    # Logic Choice: QR or Manual Backup
    mode = st.radio("Student Identification:", ["QR Scan (Automatic)", "Manual Select (Backup)"], horizontal=True)
    
    img_file = st.camera_input("Scan Student Sheet")
    
    if img_file:
        file_bytes = np.frombuffer(img_file.getvalue(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        target_id = None
        
        if mode == "QR Scan (Automatic)":
            qr_detect = cv2.QRCodeDetector()
            s_id, _, _ = qr_detect.detectAndDecode(img)
            if s_id: target_id = s_id
            else: st.error("❌ Cannot find QR Code. Use 'Manual Select' if the camera is blurry.")
        else:
            st_df = pd.read_sql("SELECT * FROM students", conn)
            sel = st.selectbox("Identify Student Manually:", st_df['name'])
            target_id = st_df[st_df['name'] == sel]['id'].values[0]

        if target_id:
            c.execute("SELECT name FROM students WHERE id=?", (target_id,))
            student_row = c.fetchone()
            if student_row:
                st.success(f"Checking paper for: **{student_row[0]}**")
                
                # --- OMR PIXEL COUNTING LOGIC (SIMULATED) ---
                # Diri ibutang ang cv2 processing logic
                total_q = len(st.session_state.master_key)
                if total_q == 0:
                    st.warning("Set Master Key first!")
                else:
                    # Simulation sa Auto-Correction
                    score = 15 # Placeholder para sa scoring logic
                    st.metric("Detected Score", f"{score} / {total_q}")
                    
                    if st.button("SAVE SCORE TO DATABASE", width='stretch'):
                        c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", 
                                  (target_id, score, total_q))
                        conn.commit()
                        st.balloons()
                        st.success(f"Record for {student_row[0]} saved!")
            else: st.error("Student ID not in database.")

# --- TAB 5: RECORDS ---
elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Records</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')
