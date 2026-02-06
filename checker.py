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
conn = sqlite3.connect('exam_final_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scores (student_id TEXT, score INTEGER, total INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# --- INITIALIZE STATE ---
if 'master_key' not in st.session_state: st.session_state.master_key = {}

st.set_page_config(page_title="Pro OMR Scanner 2026", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 45px; height: 45px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 26px; font-weight: bold; color: #D32F2F; border-bottom: 3px solid #D32F2F; margin-bottom: 15px; }
    .stCamera { border: 5px solid #D32F2F; border-radius: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. GENERATOR (CIRCLE STYLE) ---
def generate_pro_sheet(student_id, student_name, num_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    w_pdf, h_pdf = LETTER
    
    # Fiducial Markers (Para sa Alignment)
    p.rect(0.5*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(w_pdf-0.75*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, h_pdf-0.8*inch, "PRO OMR SYSTEM 2026")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, h_pdf-1.2*inch, f"STUDENT: {student_name.upper()}")
    p.drawString(1*inch, h_pdf-1.4*inch, f"ID: {student_id}")
    
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
    buffer.seek(0)
    return buffer

# --- MAIN UI ---
menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Scanner (Camera)", "Records"])

# --- ENROLLMENT ---
if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Enrollment</div>", unsafe_allow_html=True)
    with st.form("enroll", clear_on_submit=True):
        s_id, s_name = st.text_input("ID Number"), st.text_input("Full Name")
        if st.form_submit_button("Save Student"):
            if s_id and s_name:
                c.execute("INSERT INTO students VALUES (?, ?)", (s_id, s_name))
                conn.commit()
                st.success("Enrolled!")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

# --- MASTER KEY ---
elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Set Master Key</div>", unsafe_allow_html=True)
    num_q = st.number_input("Total Items", 5, 50, 20)
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

# --- GENERATE PAPERS ---
elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Generate Answer Sheets</div>", unsafe_allow_html=True)
    st_df = pd.read_sql("SELECT * FROM students", conn)
    if not st_df.empty:
        sel_name = st.selectbox("Select Student", st_df['name'])
        sel_id = st_df[st_df['name'] == sel_name]['id'].values[0]
        q_count = len(st.session_state.master_key) if st.session_state.master_key else 20
        pdf = generate_pro_sheet(sel_id, sel_name, q_count)
        st.download_button(f"Download PDF for {sel_name}", pdf, f"{sel_id}.pdf", width='stretch')

# --- AUTO-SCANNER (THE COMPUTER VISION PART) ---
elif menu == "Auto-Scanner (Camera)":
    st.markdown("<div class='main-header'>📸 Professional Bubble Scanner</div>", unsafe_allow_html=True)
    
    st_df = pd.read_sql("SELECT * FROM students", conn)
    if st_df.empty:
        st.warning("Enroll students first!")
    else:
        selected_student = st.selectbox("Identify Student Manually:", st_df['name'])
        s_id = st_df[st_df['name'] == selected_student]['id'].values[0]

        img_file = st.camera_input("Focus on the Shaded Circles")
        
        if img_file:
            # OpenCV Processing
            file_bytes = np.frombuffer(img_file.getvalue(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            # Pre-processing para ma-detect ang shade
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            # Thresholding: Ang gi-shade-an mahimong WHITE pixels
            thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            
            # I-pakita ang "AI View" para makita nimo kung nakuha ba ang shade
            st.image(thresh, caption="AI Detection View (Binary)", width=400)
            

            total_q = len(st.session_state.master_key)
            if total_q == 0:
                st.warning("Set Master Key first!")
            else:
                # Diri na mo-ihap sa pixels (Simulated for Now)
                # In actual: we slice the 'thresh' image into circle zones and count non-zero pixels
                score = 0
                for i in range(1, total_q + 1):
                    # Logic: If pixel_count > threshold: student_ans = X
                    pass
                
                detected_score = 18 # Placeholder 
                st.metric(f"Score for {selected_student}", f"{detected_score} / {total_q}")
                
                if st.button("SAVE SCORE TO DATABASE", width='stretch'):
                    c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", 
                              (s_id, detected_score, total_q))
                    conn.commit()
                    st.balloons()
                    st.success("Record Saved!")

# --- RECORDS ---
elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Records</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')
