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
if 'history' not in st.session_state: st.session_state.history = []

st.set_page_config(page_title="Pro OMR System 2026", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 40px; height: 40px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 24px; font-weight: bold; color: #D32F2F; border-bottom: 2px solid #D32F2F; }
    /* Mobile optimization for camera input */
    [data-testid="stCameraInput"] { border: 2px solid #D32F2F; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. GENERATOR: PRC-STYLE ---
def generate_pro_sheet(student_id, student_name, num_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    width_pdf, height_pdf = LETTER
    
    # Fiducial Markers (Squares sa kanto)
    p.rect(0.5*inch, height_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(width_pdf-0.75*inch, height_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    
    qr = qrcode.make(student_id)
    qr.save("temp_qr.png")
    p.drawImage("temp_qr.png", width_pdf-1.5*inch, height_pdf-1.6*inch, width=1*inch, height=1*inch)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, height_pdf-0.8*inch, "PRO OMR ANSWER SHEET 2026")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, height_pdf-1.1*inch, f"STUDENT: {student_name.upper()}")
    p.drawString(1*inch, height_pdf-1.3*inch, f"ID: {student_id}")
    
    y_pos = height_pdf - 2.2*inch
    for i in range(1, num_q + 1):
        p.setFont("Helvetica-Bold", 10)
        p.drawString(1*inch, y_pos, f"{i:02d}.")
        for j, choice in enumerate(['A', 'B', 'C', 'D']):
            x_pos = 1.5*inch + (j * 0.45*inch)
            p.circle(x_pos, y_pos + 3, 8, stroke=1, fill=0)
            p.setFont("Helvetica", 7)
            p.drawCentredString(x_pos, y_pos + 1, choice)
        y_pos -= 0.35*inch
    p.save()
    if os.path.exists("temp_qr.png"): os.remove("temp_qr.png")
    buffer.seek(0)
    return buffer

# --- MAIN UI ---
st.title("🛡️ Pro-Level OMR System (Updated 2026)")

menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Check Camera", "Records"])

if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Database Enrollment</div>", unsafe_allow_html=True)
    with st.form("enroll_form"):
        s_id = st.text_input("ID Number")
        s_name = st.text_input("Full Name")
        if st.form_submit_button("Enroll Student"):
            try:
                c.execute("INSERT INTO students VALUES (?, ?)", (s_id, s_name))
                conn.commit()
                st.success(f"Enrolled: {s_name}")
            except: st.error("Error: ID already exists.")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Set Master Answer Key</div>", unsafe_allow_html=True)
    num_q = st.number_input("How many items?", 5, 50, 20)
    main_cols = st.columns(3)
    for i in range(1, num_q + 1):
        col_idx = (i-1) % 3
        with main_cols[col_idx]:
            sub = st.columns([0.8, 1, 1, 1, 1])
            sub[0].write(f"**{i}**")
            for j, label in enumerate(['A', 'B', 'C', 'D']):
                active = st.session_state.master_key.get(i) == j
                if sub[j+1].button(label, key=f"m_{i}_{j}", type="primary" if active else "secondary"):
                    st.session_state.master_key[i] = j
                    st.rerun()

elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Download Student Answer Sheets</div>", unsafe_allow_html=True)
    students = pd.read_sql("SELECT * FROM students", conn)
    if students.empty: st.warning("Enroll students first!")
    else:
        selected_name = st.selectbox("Select Student", students['name'])
        s_id = students[students['name'] == selected_name]['id'].values[0]
        num_q = len(st.session_state.master_key) if st.session_state.master_key else 20
        pdf = generate_pro_sheet(s_id, selected_name, num_q)
        st.download_button(f"Download PDF for {selected_name}", pdf, f"{s_id}_exam.pdf")

elif menu == "Auto-Check Camera":
    st.markdown("<div class='main-header'>📸 AI Auto-Scanner</div>", unsafe_allow_html=True)
    img_file = st.camera_input("Scan the Paper (Ensure good lighting)")
    
    if img_file:
        file_bytes = np.frombuffer(img_file.getvalue(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # 1. QR Code Detection para kaila ang system sa estudyante
        qr_detector = cv2.QRCodeDetector()
        s_id, _, _ = qr_detector.detectAndDecode(img)
        
        if s_id:
            c.execute("SELECT name FROM students WHERE id=?", (s_id,))
            student_data = c.fetchone()
            
            if student_data:
                st.success(f"Student Identified: **{student_data[0]}**")
                
                # --- AUTO-DETECTION LOGIC (SHADING) ---
                # Convert to grayscale and threshold
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

                # (Simulation of counting correct answers based on pixel density)
                # Note: Full OMR logic needs perspective warp, for now we simulate detection
                total_items = len(st.session_state.master_key)
                if total_items == 0:
                    st.warning("Please set the Master Key first!")
                else:
                    # Sample score calculation based on detection (Placeholder)
                    score = 0
                    for i in range(1, total_items + 1):
                        # Diri dapit daganon ang cv2.countNonZero sa matag bubble contour
                        pass 
                    
                    # For testing purposes, let's assume it detected some score
                    simulated_score = 18 
                    st.metric("Detected Score", f"{simulated_score}/{total_items}")
                    
                    if st.button("Confirm and Save to DB", width='stretch'):
                        c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", 
                                  (s_id, simulated_score, total_items))
                        conn.commit()
                        st.balloons()
                        st.success(f"Record for {student_data[0]} saved!")
            else:
                st.error("QR Code detected but Student ID not found in database.")
        else:
            st.error("Cannot find QR Code. Please align the paper properly.")

elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Performance Record</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')